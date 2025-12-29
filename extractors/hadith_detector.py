"""
Hadith Reference Detector Module
Auto-detects Hadith references in text using regex patterns.
"""

import re
from typing import List, Dict, Any


# Hadith collections
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
    "Abu Dawood",
    "Nasa'i",
    "Ibn Majah",
]

# Build pattern for collection names (case-insensitive)
COLLECTION_PATTERN = '|'.join(re.escape(c) for c in HADITH_COLLECTIONS)


def detect_hadith_refs(text: str) -> List[Dict[str, Any]]:
    """
    Detect Hadith references in the given text.

    Args:
        text: The text to search for Hadith references

    Returns:
        List of detected Hadith references with details
    """
    refs = []
    seen_positions = set()

    # Pattern 1: *Collection Name*, Hadith No. 1234 or (Collection Name, Hadith No. 1234)
    pattern1 = rf'\*({COLLECTION_PATTERN})\*[,\s]*[Hh]adith\s*[Nn]o\.?\s*(\d+)'
    for match in re.finditer(pattern1, text, re.IGNORECASE):
        if match.start() not in seen_positions:
            refs.append(_create_hadith_ref(
                collection=match.group(1),
                number=int(match.group(2)),
                match=match
            ))
            seen_positions.add(match.start())

    # Pattern 2: Collection Name, Hadith No. 1234 (without asterisks)
    pattern2 = rf'({COLLECTION_PATTERN})[,\s]+[Hh]adith\s*[Nn]o\.?\s*(\d+)'
    for match in re.finditer(pattern2, text, re.IGNORECASE):
        if match.start() not in seen_positions:
            refs.append(_create_hadith_ref(
                collection=match.group(1),
                number=int(match.group(2)),
                match=match
            ))
            seen_positions.add(match.start())

    # Pattern 3: Collection Name: 1234 or Collection Name #1234
    pattern3 = rf'({COLLECTION_PATTERN})[:\s#]+(\d+)'
    for match in re.finditer(pattern3, text, re.IGNORECASE):
        if match.start() not in seen_positions:
            refs.append(_create_hadith_ref(
                collection=match.group(1),
                number=int(match.group(2)),
                match=match
            ))
            seen_positions.add(match.start())

    # Pattern 4: Hadith No. 1234 (without collection - generic)
    pattern4 = r'[Hh]adith\s*[Nn]o\.?\s*(\d+)'
    for match in re.finditer(pattern4, text):
        if match.start() not in seen_positions:
            refs.append(_create_hadith_ref(
                collection=None,
                number=int(match.group(1)),
                match=match
            ))
            seen_positions.add(match.start())

    # Pattern 5: Narrated by/from patterns (common hadith indicator)
    pattern5 = r'[Nn]arrated\s+(?:by|from)\s+([\w\s]+?)(?:\s*[:,]|\s+that)'
    for match in re.finditer(pattern5, text):
        if match.start() not in seen_positions:
            narrator = match.group(1).strip()
            # Only include if narrator looks like a name (not too long)
            if len(narrator) < 50 and narrator:
                refs.append({
                    'collection': None,
                    'number': None,
                    'narrator': narrator,
                    'detection': 'auto',
                    'verified': False,
                    'start_pos': match.start(),
                    'end_pos': match.end(),
                    'matched_text': match.group(0)
                })
                seen_positions.add(match.start())

    # Sort by position in text
    refs.sort(key=lambda x: x['start_pos'])

    return refs


def _create_hadith_ref(collection: str, number: int, match: re.Match) -> Dict[str, Any]:
    """Create a hadith reference dictionary from a match."""
    return {
        'collection': _normalize_collection_name(collection) if collection else None,
        'number': number,
        'narrator': None,
        'detection': 'auto',
        'verified': False,
        'start_pos': match.start(),
        'end_pos': match.end(),
        'matched_text': match.group(0)
    }


def _normalize_collection_name(name: str) -> str:
    """Normalize collection name to standard form."""
    name_lower = name.lower().strip()

    # Map shortened names to full names
    name_map = {
        'bukhari': 'Sahih al-Bukhari',
        'muslim': 'Sahih Muslim',
        'tirmidhi': 'Sunan at-Tirmidhi',
        'abu dawood': 'Sunan Abi Dawood',
        "nasa'i": "Sunan an-Nasa'i",
        'ibn majah': 'Sunan Ibn Majah',
    }

    for short, full in name_map.items():
        if short in name_lower:
            return full

    # Return original with proper capitalization if no mapping found
    return name.strip()


def format_hadith_ref(ref: Dict[str, Any]) -> str:
    """Format a Hadith reference for display."""
    parts = []

    if ref.get('collection'):
        parts.append(ref['collection'])

    if ref.get('number'):
        parts.append(f"Hadith No. {ref['number']}")

    if ref.get('narrator') and not parts:
        return f"Narrated by {ref['narrator']}"

    return ', '.join(parts) if parts else "Hadith reference"


def get_collection_list() -> List[str]:
    """Return the list of known hadith collections."""
    return [
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
        "Other"
    ]
