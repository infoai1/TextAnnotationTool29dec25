#!/usr/bin/env python3
"""Migrate progress files from old naming (with title spaces) to new naming (with folder names)"""

import os
import json
import logging
from pathlib import Path

LOG_DIR = Path("/root/annotation_tool/logs")
DATA_DIR = Path("/root/annotation_tool/data")
BOOKS_DIR = Path("/root/annotation_tool/books")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'migration.log'),
        logging.StreamHandler()
    ]
)

def find_book_folder_for_title(title):
    """Find book folder that matches title (fuzzy match)"""
    title_clean = title.strip().lower()

    for book_folder in BOOKS_DIR.iterdir():
        if not book_folder.is_dir():
            continue

        meta_file = book_folder / 'meta.json'
        if meta_file.exists():
            with open(meta_file) as f:
                meta = json.load(f)
                if meta.get('title', '').strip().lower() == title_clean:
                    return book_folder.name

    return None

def migrate_progress_files():
    """Rename all progress files from old pattern to new pattern"""
    renamed = 0
    skipped = 0

    for progress_file in DATA_DIR.glob('*_progress.json'):
        filename = progress_file.name

        # Skip if already in new format (no leading underscores)
        if not filename.startswith('_'):
            logging.info(f"SKIP (already new format): {filename}")
            skipped += 1
            continue

        # Parse: _____women_in_islam___admin_progress.json
        # Extract username (last part before _progress.json)
        parts = filename.replace('_progress.json', '').split('_')
        username = parts[-1] if parts else 'guest'

        # Load file to get book_title
        with open(progress_file) as f:
            data = json.load(f)
            book_title = data.get('book_title')

        if not book_title:
            logging.warning(f"SKIP (no book_title in file): {filename}")
            skipped += 1
            continue

        # Find matching book folder
        book_folder = find_book_folder_for_title(book_title)

        if not book_folder:
            logging.warning(f"SKIP (no matching folder): {filename} title={book_title}")
            skipped += 1
            continue

        # New filename
        new_filename = f"{book_folder}_{username}_progress.json"
        new_path = DATA_DIR / new_filename

        # Check if new file already exists
        if new_path.exists():
            logging.warning(f"SKIP (new file exists): {filename} → {new_filename}")
            skipped += 1
            continue

        # Rename
        progress_file.rename(new_path)
        logging.info(f"RENAMED: {filename} → {new_filename}")
        renamed += 1

    logging.info(f"\nMigration complete: {renamed} renamed, {skipped} skipped")

if __name__ == '__main__':
    migrate_progress_files()
