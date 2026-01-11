"""
Pure utility functions. No Streamlit, no file I/O.
All functions here should be testable independently.
"""
import re
from datetime import datetime
from typing import Optional
from config import get_ist_now


def slugify(text: str, max_length: int = 50) -> str:
    """
    Convert text to URL-safe slug.

    Args:
        text: Input text to slugify
        max_length: Maximum length of slug (default 50)

    Returns:
        URL-safe slug string

    Example:
        >>> slugify("Peace in Kashmir")
        'peace-in-kashmir'
    """
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:max_length]


def humanize_time_ago(dt: Optional[datetime]) -> str:
    """
    Convert datetime to '2 hours ago' format.

    Args:
        dt: Datetime object to convert

    Returns:
        Human-readable time ago string

    Example:
        >>> from datetime import datetime, timedelta
        >>> humanize_time_ago(datetime.now() - timedelta(hours=2))
        '2 hours ago'
    """
    if not dt:
        return "Never"

    now = get_ist_now()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins} min ago" if mins == 1 else f"{mins} mins ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day ago" if days == 1 else f"{days} days ago"
    else:
        return dt.strftime("%b %d, %Y")


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using words * 1.3 heuristic.

    Args:
        text: Input text

    Returns:
        Estimated token count

    Example:
        >>> estimate_tokens("Hello world")
        2
    """
    if not text or not text.strip():
        return 0
    return int(len(text.split()) * 1.3)


def count_tokens(text: str) -> dict:
    """
    Count words and characters in text.

    Args:
        text: Input text

    Returns:
        Dictionary with 'words' and 'chars' counts

    Example:
        >>> count_tokens("Hello world")
        {'words': 2, 'chars': 11}
    """
    words = len(text.split())
    chars = len(text)
    return {'words': words, 'chars': chars}


def validate_para_id(para_id: str) -> bool:
    """
    Check if paragraph ID format is valid.

    Args:
        para_id: Paragraph ID to validate

    Returns:
        True if valid format (p_XXX where XXX is 3+ digits)

    Example:
        >>> validate_para_id("p_001")
        True
        >>> validate_para_id("invalid")
        False
    """
    return bool(re.match(r'^p_\d{3,}$', para_id))


def validate_group_id(group_id: str) -> bool:
    """
    Check if group ID format is valid.

    Args:
        group_id: Group ID to validate

    Returns:
        True if valid format (g_XXX where XXX is 3+ digits)

    Example:
        >>> validate_group_id("g_001")
        True
        >>> validate_group_id("invalid")
        False
    """
    return bool(re.match(r'^g_\d{3,}$', group_id))


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and normalizing.

    Args:
        text: Input text to clean

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.

    Args:
        text: Input text
        max_length: Maximum length before truncation
        suffix: Suffix to add if truncated (default "...")

    Returns:
        Truncated text

    Example:
        >>> truncate_text("This is a long text", 10)
        'This is a...'
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix
