"""Hadith reference detector with pre-compiled regex patterns."""

import re
from dataclasses import dataclass


@dataclass
class HadithReference:
    """Represents a detected Hadith reference."""
    collection: str | None
    hadith_number: int | None
    matched_text: str
    start_pos: int
    end_pos: int


# Hadith collection names
HADITH_COLLECTIONS = [
    "Sahih al-Bukhari",
    "Sahih Muslim",
    "Sunan at-Tirmidhi",
    "Sunan Abi Dawood",
    "Sunan an-Nasa'i",
    "Sunan Ibn Majah",
    "Musnad Ahmad",
    "Muwatta Malik",
    "Musnad Al-Bazzar",
    "Musnad Al-Shihab",
    "Al-Tabarani",
    "Bukhari",
    "Muslim",
    "Tirmidhi",
]

# Pre-compiled pattern for collection names (single alternation, case-insensitive)
_COLLECTION_PATTERN = re.compile(
    r'(' + '|'.join(re.escape(c) for c in HADITH_COLLECTIONS) + r')',
    re.IGNORECASE
)

# Pre-compiled patterns for hadith references
_PATTERNS = [
    # *Sahih al-Bukhari*, Hadith No. 5971 (markdown italics)
    re.compile(
        r'\*(' + '|'.join(re.escape(c) for c in HADITH_COLLECTIONS) + r')\*'
        r',?\s*Hadith\s*(?:No\.?|Number)?\s*(\d+)',
        re.IGNORECASE
    ),
    # Sahih al-Bukhari, Hadith No. 5971 (plain text)
    re.compile(
        r'(' + '|'.join(re.escape(c) for c in HADITH_COLLECTIONS) + r')'
        r',?\s*Hadith\s*(?:No\.?|Number)?\s*(\d+)',
        re.IGNORECASE
    ),
    # Hadith No. 236 (number only, no collection)
    re.compile(r'Hadith\s*(?:No\.?|Number)\s*(\d+)', re.IGNORECASE),
    # (Bukhari: 1234) or (Muslim: 5678) - parenthesized format
    re.compile(
        r'\((' + '|'.join(re.escape(c) for c in HADITH_COLLECTIONS) + r')'
        r'[:\s]+(\d+)\)',
        re.IGNORECASE
    ),
]


def detect_hadith_refs(text: str) -> list[HadithReference]:
    """
    Detect all Hadith references in text.

    Args:
        text: Input text to search

    Returns:
        List of HadithReference objects with positions
    """
    refs = []
    seen_positions = set()

    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            if match.start() in seen_positions:
                continue

            seen_positions.add(match.start())
            groups = match.groups()

            # Handle different pattern group structures
            if len(groups) == 2:
                collection, number = groups
            elif len(groups) == 1:
                collection, number = None, groups[0]
            else:
                continue

            refs.append(HadithReference(
                collection=collection,
                hadith_number=int(number) if number else None,
                matched_text=match.group(0),
                start_pos=match.start(),
                end_pos=match.end(),
            ))

    refs.sort(key=lambda r: r.start_pos)
    return refs


def detect_hadith_refs_batch(paragraphs: list[str]) -> list[list[HadithReference]]:
    """
    Detect Hadith references in multiple paragraphs.

    Args:
        paragraphs: List of paragraph texts

    Returns:
        List of reference lists, one per paragraph
    """
    return [detect_hadith_refs(p) for p in paragraphs]


def normalize_collection_name(name: str) -> str:
    """Normalize collection name to standard form."""
    name_lower = name.lower()
    for collection in HADITH_COLLECTIONS:
        if collection.lower() == name_lower:
            return collection
    return name
