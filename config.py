"""
Configuration constants for Annotation Tool.
All paths and constants in one place for easy modification.
"""
from pathlib import Path
import os

# Determine environment
IS_DOCKER = os.path.exists('/.dockerenv')

# Base paths
if IS_DOCKER:
    BASE_DIR = Path("/app")
    DATA_DIR = Path("/app/data")
    BOOKS_DIR = Path("/app/books")
    EXPORTS_DIR = Path("/app/exports")
    LOGS_DIR = Path("/app/logs")
else:
    BASE_DIR = Path("/root/annotation_tool")
    DATA_DIR = BASE_DIR / "data"
    BOOKS_DIR = BASE_DIR / "books"
    EXPORTS_DIR = BASE_DIR / "exports"
    LOGS_DIR = BASE_DIR / "logs"

# Versions subdirectory
VERSIONS_DIR = DATA_DIR / "versions"

# Ensure directories exist
for d in [DATA_DIR, BOOKS_DIR, EXPORTS_DIR, LOGS_DIR, VERSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Timing (seconds)
AUTO_SAVE_INTERVAL = 30  # Auto-save every 30 seconds
CACHE_TTL = 3600  # Cache TTL for expensive operations (1 hour)
LOCK_TIMEOUT_HOURS = 2  # Release locks after 2 hours of inactivity

# Versioning
VERSION_KEEP_COUNT = 10  # Keep last 10 versions per book

# Grouping token ranges
GROUP_TOKEN_MIN = 512  # Minimum tokens for a group
GROUP_TOKEN_TARGET = 650  # Target tokens for a group
GROUP_TOKEN_MAX = 800  # Maximum tokens for a group

# UI defaults
DEFAULT_COLLAPSED = True  # Collapse paragraphs by default
MAX_SLUG_LENGTH = 50  # Maximum length for book slugs

# Auth
AUTH_CONFIG_FILE = DATA_DIR / "users.yaml"

# Export formats
EXPORT_INDENT = 2  # JSON indentation for exports

# IST Timezone (India Standard Time - UTC+5:30)
from datetime import datetime, timedelta
IST_OFFSET = timedelta(hours=5, minutes=30)

def get_ist_now():
    """Get current datetime in IST timezone."""
    return datetime.utcnow() + IST_OFFSET
