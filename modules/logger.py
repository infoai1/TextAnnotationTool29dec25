"""
Structured logging for annotation tool.

Provides debugging support with file-based logs and optional UI display.
"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_logging(debug_mode: bool = False, log_file: str = None) -> logging.Logger:
    """
    Configure structured logging for debugging.

    Creates rotating log files (10MB max, 5 backups) with detailed formatting.

    Args:
        debug_mode: If True, log DEBUG level; otherwise INFO
        log_file: Custom log file path (default: /root/annotation_tool/logs/annotation_tool.log)

    Returns:
        Configured logger instance

    Usage:
        from modules.logger import setup_logging
        logger = setup_logging(debug_mode=True)
        logger.info("Book loaded successfully")
        logger.debug(f"Loaded {len(paragraphs)} paragraphs")
        logger.error(f"Failed to save: {error}")
    """
    log_dir = Path("/root/annotation_tool/logs")
    log_dir.mkdir(exist_ok=True)

    if log_file is None:
        log_file = log_dir / "annotation_tool.log"

    level = logging.DEBUG if debug_mode else logging.INFO

    # File handler with rotation
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10_000_000,  # 10MB
        backupCount=5
    )

    # Detailed formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)-20s:%(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # Configure logger
    logger = logging.getLogger("annotation_tool")
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    logger.addHandler(handler)

    # Also log to console
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)  # Only warnings/errors to console
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger


def get_logger() -> logging.Logger:
    """
    Get existing logger instance.

    Returns:
        Logger instance (creates default if doesn't exist)

    Usage:
        from modules.logger import get_logger
        logger = get_logger()
        logger.info("Using existing logger")
    """
    logger = logging.getLogger("annotation_tool")
    if not logger.handlers:
        return setup_logging()
    return logger


def read_recent_logs(num_lines: int = 50) -> str:
    """
    Read recent log entries (for UI display).

    Args:
        num_lines: Number of recent lines to read

    Returns:
        String with recent log entries

    Usage in Streamlit:
        if st.checkbox("Debug Mode"):
            st.code(read_recent_logs(100))
    """
    log_file = Path("/root/annotation_tool/logs/annotation_tool.log")
    if not log_file.exists():
        return "No logs yet"

    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            return ''.join(lines[-num_lines:])
    except Exception as e:
        return f"Error reading logs: {e}"
