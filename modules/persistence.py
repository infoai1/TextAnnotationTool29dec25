"""
BookLibrary - Book persistence and library management.

Handles save/load workflows, book locking, library operations.
Provides clean interface between UI and database.
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger("annotation_tool")


class BookLibrary:
    """
    Handle book persistence and library operations.

    **Purpose**: Clean interface between UI (Streamlit) and database (db.py).
    All persistence operations go through this class.

    **Key Methods**:
    - save_progress(): Save current annotation state
    - load_book(): Load book from library
    - get_library_books(): List all books
    - lock_book() / release_lock(): Concurrency control
    """

    def __init__(self, db_module):
        """
        Initialize BookLibrary.

        Args:
            db_module: Reference to db module (for database operations)
        """
        self.db = db_module


    # ============= Book Library Operations =============

    def get_library_books(self) -> List[Dict]:
        """
        List all books in library.

        Returns:
            List of book metadata dicts
        """
        logger.debug("Getting library books")
        return self.db.get_library_books()


    def get_saved_books(self) -> List[str]:
        """
        Get list of saved book paths.

        Returns:
            List of file paths
        """
        return self.db.get_saved_books()


    # ============= Book Locking =============

    def can_lock_book(self, book_folder: str, username: str) -> bool:
        """
        Check if book can be locked by user.

        Args:
            book_folder: Book folder path
            username: User requesting lock

        Returns:
            True if book can be locked
        """
        return self.db.can_lock_book(book_folder, username)


    def lock_book(self, book_folder: str, username: str) -> bool:
        """
        Acquire exclusive lock on book.

        Args:
            book_folder: Book folder path
            username: User acquiring lock

        Returns:
            True if lock acquired successfully
        """
        logger.info(f"User {username} locking book: {book_folder}")
        return self.db.lock_book(book_folder, username)


    def release_lock(self, book_folder: str) -> bool:
        """
        Release lock on book.

        Args:
            book_folder: Book folder path

        Returns:
            True if released successfully
        """
        logger.info(f"Releasing lock on book: {book_folder}")
        return self.db.release_lock(book_folder)


    # ============= Metadata Operations =============

    def load_meta(self, book_folder: str) -> Dict:
        """
        Load book metadata.

        Args:
            book_folder: Book folder path

        Returns:
            Metadata dict
        """
        return self.db.load_meta(book_folder)


    def save_meta(self, book_folder: str, meta: Dict):
        """
        Save book metadata.

        Args:
            book_folder: Book folder path
            meta: Metadata dict
        """
        logger.debug(f"Saving metadata for: {book_folder}")
        self.db.save_meta(book_folder, meta)


    # ============= Progress Operations =============

    def load_last_read_position(self, book_folder: str, username: str) -> Optional[str]:
        """
        Get user's last read position in book.

        Args:
            book_folder: Book folder path
            username: User name

        Returns:
            Last paragraph ID or None
        """
        return self.db.load_last_read_position(book_folder, username)


    def save_progress(self, book_folder: str, data: Dict, username: str):
        """
        Save annotation progress.

        Args:
            book_folder: Book folder path
            data: Progress data (paragraphs, groups, etc.)
            username: User name
        """
        logger.info(f"Saving progress for: {book_folder} (user: {username})")
        try:
            self.db.save_progress(book_folder, data, username)
            logger.info(f"✓ Progress saved successfully")
        except Exception as e:
            logger.error(f"✗ Failed to save progress: {e}")
            raise


    def load_progress(self, book_folder: str) -> Dict:
        """
        Load annotation progress.

        Args:
            book_folder: Book folder path

        Returns:
            Progress data dict
        """
        logger.debug(f"Loading progress for: {book_folder}")
        return self.db.load_progress(book_folder)


    # ============= Workflow Operations =============

    def submit_for_review(self, book_folder: str):
        """
        Submit book for review (workflow transition).

        Args:
            book_folder: Book folder path
        """
        logger.info(f"Submitting for review: {book_folder}")
        meta = self.load_meta(book_folder)
        meta['status'] = 'pending_review'
        meta['submitted_at'] = datetime.now().isoformat()
        self.save_meta(book_folder, meta)


    def approve_book(self, book_folder: str):
        """
        Approve book (workflow transition).

        Args:
            book_folder: Book folder path
        """
        logger.info(f"Approving book: {book_folder}")
        meta = self.load_meta(book_folder)
        meta['status'] = 'approved'
        meta['approved_at'] = datetime.now().isoformat()
        self.save_meta(book_folder, meta)


    def delete_book(self, book_folder: str):
        """
        Delete book and all associated data.

        Args:
            book_folder: Book folder path
        """
        logger.warning(f"Deleting book: {book_folder}")
        self.db.delete_book(book_folder)
