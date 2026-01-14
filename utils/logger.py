"""Centralized logging configuration for debugging."""

import logging
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def setup_logger(
    name: str = "annotation_tool",
    level: LogLevel = "INFO",
    log_to_file: bool = False,
    log_file: str = "app.log",
) -> logging.Logger:
    """
    Set up and return a configured logger.

    Args:
        name: Logger name (use __name__ for module-specific loggers)
        level: Logging level
        log_to_file: Whether to also write logs to a file
        log_file: Path to log file if log_to_file is True

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger(__name__, level="DEBUG")
        >>> logger.debug("Processing paragraph 1")
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))

    # Format: timestamp - module - level - message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_to_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Default app logger
app_logger = setup_logger()
