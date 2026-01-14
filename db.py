"""
Database/Persistence layer for Annotation Tool.
All file I/O operations happen here.

Pure functions that don't depend on Streamlit session state.
"""
import json
import logging
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

from config import (
    DATA_DIR,
    BOOKS_DIR,
    VERSIONS_DIR,
    VERSION_KEEP_COUNT,
    LOCK_TIMEOUT_HOURS,
    get_ist_now
)
from helpers import slugify

logger = logging.getLogger(__name__)

# ===== PROGRESS FILE OPERATIONS =====

def get_progress_path(book_folder: str, user: str) -> Path:
    """Get path to progress file."""
    # Use book_folder directly as slug (already clean)
    filename = f"{book_folder}_{user}_progress.json"
    return Path(DATA_DIR) / filename


def progress_exists(book_folder: str, user: str) -> bool:
    """Check if progress file exists."""
    return get_progress_path(book_folder, user).exists()


def save_progress(data: dict, book_folder: str, user: str) -> bool:
    """
    Save progress to disk with atomic write.

    Args:
        data: Progress data to save
        book_folder: Book folder name (slug)
        user: Username

    Returns:
        True if save successful, False otherwise
    """
    path = get_progress_path(book_folder, user)
    temp_path = path.with_suffix('.tmp')

    try:
        # Add save metadata
        data['last_saved'] = get_ist_now().isoformat()
        data['last_saved_by'] = user
        data['current_book_folder'] = book_folder

        # Atomic write: write to temp, then rename
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        temp_path.rename(path)

        file_size_kb = path.stat().st_size / 1024
        logger.info(f"[SAVE] book={book_folder} user={user} size={file_size_kb:.1f}KB")

        return True
    except Exception as e:
        logger.error(f"[SAVE] FAILED: {e}")
        if temp_path.exists():
            temp_path.unlink()
        return False


def load_progress(book_folder: str, user: str) -> Optional[dict]:
    """
    Load progress from disk.

    Args:
        book_folder: Book folder name (slug)
        user: Username

    Returns:
        Progress data dict or None if not found
    """
    path = get_progress_path(book_folder, user)

    if not path.exists():
        logger.warning(f"[LOAD] not found: {path}")
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"[LOAD] book={book_folder} user={user}")
        return data
    except Exception as e:
        logger.error(f"[LOAD] FAILED: {e}")
        return None


def list_saved_books(user: str, role: str = 'annotator') -> List[dict]:
    """
    List all saved books accessible to user.

    Args:
        user: Username
        role: User role (admin, annotator, reviewer)

    Returns:
        List of book info dicts
    """
    saved = []

    if not os.path.exists(DATA_DIR):
        return saved

    for fname in os.listdir(DATA_DIR):
        if not fname.endswith('_progress.json'):
            continue

        fpath = os.path.join(DATA_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            saved_by = data.get('last_saved_by', 'unknown')
            status = data.get('book_status', 'pending')

            # Filter based on role
            show = False
            if role == 'admin':
                show = True
            elif role == 'annotator' and saved_by == user:
                show = True
            elif role == 'reviewer' and status == 'annotated':
                show = True

            if show:
                saved.append({
                    'file': fpath,
                    'title': data.get('book_title', 'Unknown'),
                    'last_saved': data.get('last_saved', ''),
                    'para_count': len(data.get('paragraphs', [])),
                    'status': status,
                    'saved_by': saved_by
                })
        except Exception as e:
            logger.warning(f"[LIST] Failed to read {fname}: {e}")
            continue

    # Sort by last saved (most recent first)
    saved.sort(key=lambda x: x.get('last_saved', ''), reverse=True)
    return saved


# ===== VERSION SNAPSHOTS =====

def get_versions_dir(book_folder: str, user: str) -> Path:
    """Get versions directory for book."""
    path = Path(VERSIONS_DIR) / f"{book_folder}_{user}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_version(book_folder: str, user: str, data: dict) -> Optional[str]:
    """
    Create version snapshot.

    Args:
        book_folder: Book folder name
        user: Username
        data: Data to snapshot

    Returns:
        Version timestamp string or None if failed
    """
    versions_dir = get_versions_dir(book_folder, user)
    timestamp = get_ist_now().strftime("%Y-%m-%dT%H:%M:%S")
    version_path = versions_dir / f"v_{timestamp}.json"

    try:
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        file_size_kb = version_path.stat().st_size / 1024
        logger.info(f"[VERSION] created {timestamp} size={file_size_kb:.1f}KB")

        # Cleanup old versions
        cleanup_old_versions(book_folder, user)

        return timestamp
    except Exception as e:
        logger.error(f"[VERSION] FAILED: {e}")
        return None


def list_versions(book_folder: str, user: str) -> List[dict]:
    """
    List available versions for book.

    Args:
        book_folder: Book folder name
        user: Username

    Returns:
        List of version dicts with id and path
    """
    versions_dir = get_versions_dir(book_folder, user)
    versions = []

    for path in sorted(versions_dir.glob("v_*.json"), reverse=True):
        timestamp_str = path.stem.replace("v_", "")
        versions.append({
            'id': timestamp_str,
            'path': str(path),
            'timestamp': timestamp_str
        })

    return versions


def rollback_to_version(book_folder: str, user: str, version_id: str) -> bool:
    """
    Restore from version snapshot.

    Args:
        book_folder: Book folder name
        user: Username
        version_id: Version timestamp ID

    Returns:
        True if rollback successful
    """
    versions_dir = get_versions_dir(book_folder, user)
    version_path = versions_dir / f"v_{version_id}.json"

    if not version_path.exists():
        logger.error(f"[ROLLBACK] version not found: {version_id}")
        return False

    try:
        with open(version_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Save as current progress
        success = save_progress(data, book_folder, user)
        if success:
            logger.info(f"[ROLLBACK] restored version {version_id}")
        return success
    except Exception as e:
        logger.error(f"[ROLLBACK] FAILED: {e}")
        return False


def cleanup_old_versions(book_folder: str, user: str):
    """Keep only last N versions, delete older ones."""
    versions = list_versions(book_folder, user)

    if len(versions) <= VERSION_KEEP_COUNT:
        return

    deleted_count = 0
    for old_version in versions[VERSION_KEEP_COUNT:]:
        try:
            Path(old_version['path']).unlink()
            deleted_count += 1
        except Exception as e:
            logger.warning(f"[VERSION_CLEANUP] Failed to delete: {e}")

    if deleted_count > 0:
        logger.info(f"[VERSION_CLEANUP] deleted {deleted_count} old versions")


# ===== BOOK METADATA =====

def get_meta_path(book_folder: str) -> Path:
    """Get path to book metadata file."""
    return Path(BOOKS_DIR) / book_folder / 'meta.json'


def load_meta(book_folder: str) -> dict:
    """
    Load book metadata.

    Args:
        book_folder: Book folder name

    Returns:
        Metadata dict (empty if not found)
    """
    meta_path = get_meta_path(book_folder)

    if not meta_path.exists():
        return {}

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[LOAD_META] FAILED: {e}")
        return {}


def save_meta(book_folder: str, meta: dict) -> bool:
    """
    Save book metadata.

    Args:
        book_folder: Book folder name
        meta: Metadata dict

    Returns:
        True if save successful
    """
    meta_path = get_meta_path(book_folder)

    try:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        logger.info(f"[SAVE_META] book={book_folder}")
        return True
    except Exception as e:
        logger.error(f"[SAVE_META] FAILED: {e}")
        return False


# ===== BOOK LOCKING =====

def can_lock_book(book_folder: str, username: str) -> bool:
    """
    Check if user can lock this book.

    Args:
        book_folder: Book folder name
        username: Username requesting lock

    Returns:
        True if user can lock the book
    """
    meta = load_meta(book_folder)

    # Already locked by this user
    if meta.get('locked_by') == username:
        return True

    # Not locked
    if meta.get('locked_by') is None:
        return True

    # Locked by someone else - check timeout
    if meta.get('locked_at'):
        try:
            locked_at = datetime.fromisoformat(meta['locked_at'])
            if get_ist_now() - locked_at > timedelta(hours=LOCK_TIMEOUT_HOURS):
                logger.info(f"[LOCK] expired lock for {book_folder}")
                return True  # Lock expired
        except Exception as e:
            logger.warning(f"[LOCK] invalid date, allowing lock: {e}")
            return True

    return False


def lock_book(book_folder: str, username: str) -> bool:
    """
    Lock book for user.

    Args:
        book_folder: Book folder name
        username: Username

    Returns:
        True if lock acquired
    """
    meta = load_meta(book_folder)
    meta['locked_by'] = username
    meta['locked_at'] = get_ist_now().isoformat()

    # Update status from pending to in_progress
    if meta.get('status') == 'pending':
        meta['status'] = 'in_progress'

    success = save_meta(book_folder, meta)
    if success:
        logger.info(f"[LOCK] book={book_folder} user={username}")
    return success


def release_lock(book_folder: str) -> bool:
    """
    Release book lock.

    Args:
        book_folder: Book folder name

    Returns:
        True if lock released
    """
    meta = load_meta(book_folder)
    locked_by = meta.get('locked_by')

    meta['locked_by'] = None
    meta['locked_at'] = None

    success = save_meta(book_folder, meta)
    if success:
        logger.info(f"[UNLOCK] book={book_folder} was_locked_by={locked_by}")
    return success


# ===== LIBRARY OPERATIONS =====

def get_library_books() -> List[dict]:
    """
    Get list of all books in library.

    Returns:
        List of book metadata dicts with folder info
    """
    books = []

    if not os.path.exists(BOOKS_DIR):
        return books

    for name in os.listdir(BOOKS_DIR):
        folder_path = os.path.join(BOOKS_DIR, name)
        if not os.path.isdir(folder_path):
            continue

        meta = load_meta(name)
        if meta:
            meta['folder'] = name
            # Check if files exist
            meta['has_docx'] = os.path.exists(os.path.join(folder_path, 'document.docx'))
            meta['has_pdf'] = os.path.exists(os.path.join(folder_path, 'document.pdf'))
            books.append(meta)

    # Sort by title
    books.sort(key=lambda x: x.get('title', ''))
    return books


def get_book_files(book_folder: str) -> dict:
    """
    Get paths to book files.

    Args:
        book_folder: Book folder name

    Returns:
        Dict with docx_path and pdf_path
    """
    folder_path = Path(BOOKS_DIR) / book_folder

    return {
        'docx_path': folder_path / 'document.docx',
        'pdf_path': folder_path / 'document.pdf',
        'folder_path': folder_path
    }
