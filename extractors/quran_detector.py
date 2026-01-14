"""Quran reference detector with pre-compiled regex patterns."""

import re
from dataclasses import dataclass


@dataclass
class QuranReference:
    """Represents a detected Quran reference."""
    surah: int
    ayah_start: int
    ayah_end: int | None
    matched_text: str
    start_pos: int
    end_pos: int


# Pre-compiled patterns for performance (compiled once at module load)
_PATTERNS = [
    # (3:195) or (4:11-12) - parenthesized format
    re.compile(r'\((\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\)'),
    # Surah Al-Baqarah 2:153 or Surah Baqarah 2:153
    re.compile(r'Surah\s+[\w\-]+\s+(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?', re.IGNORECASE),
    # verse 3:195 or Verse 3:195-196
    re.compile(r'verse\s+(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?', re.IGNORECASE),
    # Quran 3:195 or Qur'an 3:195-200
    re.compile(r"Qur['\u2019]?an\s+(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?", re.IGNORECASE),
    # [3:195] or [4:11-12] - bracketed format
    re.compile(r'\[(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\]'),
]


def detect_quran_refs(text: str) -> list[QuranReference]:
    """
    Detect all Quran references in text.

    Args:
        text: Input text to search

    Returns:
        List of QuranReference objects with positions
    """
    refs = []
    seen_positions = set()  # Avoid duplicate matches at same position

    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            # Skip if we already found a match at this position
            if match.start() in seen_positions:
                continue

            seen_positions.add(match.start())
            groups = match.groups()

            refs.append(QuranReference(
                surah=int(groups[0]),
                ayah_start=int(groups[1]),
                ayah_end=int(groups[2]) if groups[2] else None,
                matched_text=match.group(0),
                start_pos=match.start(),
                end_pos=match.end(),
            ))

    # Sort by position in text
    refs.sort(key=lambda r: r.start_pos)
    return refs


def detect_quran_refs_batch(paragraphs: list[str]) -> list[list[QuranReference]]:
    """
    Detect Quran references in multiple paragraphs.

    Args:
        paragraphs: List of paragraph texts

    Returns:
        List of reference lists, one per paragraph
    """
    return [detect_quran_refs(p) for p in paragraphs]
