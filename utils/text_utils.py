"""
Text Normalization Utilities

Shared text processing functions for consistent behavior across modules.
"""

import re


def normalize_text(text: str, remove_punctuation: bool = True) -> str:
    """
    Normalize text for comparison and matching.

    Args:
        text: Raw text with potential formatting issues
        remove_punctuation: If True, remove punctuation (better for fuzzy matching)
                          If False, keep punctuation (better for exact matching)

    Returns:
        Normalized lowercase text with collapsed whitespace
    """
    if not text:
        return ""

    # Collapse all whitespace to single space
    text = re.sub(r'\s+', ' ', text)

    # Optionally remove punctuation (helps with OCR errors and formatting variations)
    if remove_punctuation:
        text = re.sub(r'[^\w\s]', '', text)

    return text.lower().strip()
