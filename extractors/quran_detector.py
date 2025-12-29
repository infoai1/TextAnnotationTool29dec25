"""
Quran Reference Detector Module
Auto-detects Quran references in text using regex patterns.
"""

import re
from typing import List, Dict, Any, Tuple


# Quran detection patterns
QURAN_PATTERNS = [
    # (3:195) or (4:11-12) - parenthetical format
    (r'\((\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\)', 'parenthetical'),
    # Surah Al-Baqarah 2:153 or Surah An-Nisa 4:11
    (r'Surah\s+([\w\-\']+(?:\s+[\w\-\']+)?)\s+(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?', 'surah_name'),
    # verse 3:195 or Verse 4:11-12
    (r'[Vv]erse\s+(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?', 'verse'),
    # Quran 3:195 or Qur'an 4:11
    (r"[Qq]ur['\u2019]?an\s+(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?", 'quran_prefix'),
    # Al-Quran 3:195
    (r"Al-[Qq]ur['\u2019]?an\s+(\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?", 'alquran_prefix'),
]


def detect_quran_refs(text: str) -> List[Dict[str, Any]]:
    """
    Detect Quran references in the given text.

    Args:
        text: The text to search for Quran references

    Returns:
        List of detected Quran references with details
    """
    refs = []
    seen_positions = set()  # Track positions to avoid duplicates

    for pattern, pattern_type in QURAN_PATTERNS:
        for match in re.finditer(pattern, text):
            start_pos = match.start()

            # Skip if we already found a reference at this position
            if start_pos in seen_positions:
                continue

            ref = _parse_quran_match(match, pattern_type, text)
            if ref and _is_valid_quran_ref(ref):
                ref['start_pos'] = start_pos
                ref['end_pos'] = match.end()
                ref['matched_text'] = match.group(0)
                refs.append(ref)
                seen_positions.add(start_pos)

    # Sort by position in text
    refs.sort(key=lambda x: x['start_pos'])

    return refs


def _parse_quran_match(match: re.Match, pattern_type: str, text: str) -> Dict[str, Any]:
    """Parse a regex match into a Quran reference dictionary."""
    groups = match.groups()

    if pattern_type == 'parenthetical':
        # Groups: (surah, ayah_start, ayah_end_optional)
        return {
            'surah': int(groups[0]),
            'ayah_start': int(groups[1]),
            'ayah_end': int(groups[2]) if groups[2] else None,
            'detection': 'auto',
            'verified': False,
            'quoted_text': _extract_quoted_text(text, match.end())
        }

    elif pattern_type == 'surah_name':
        # Groups: (surah_name, surah_num, ayah_start, ayah_end_optional)
        return {
            'surah': int(groups[1]),
            'ayah_start': int(groups[2]),
            'ayah_end': int(groups[3]) if groups[3] else None,
            'surah_name': groups[0],
            'detection': 'auto',
            'verified': False,
            'quoted_text': _extract_quoted_text(text, match.end())
        }

    elif pattern_type in ('verse', 'quran_prefix', 'alquran_prefix'):
        # Groups: (surah, ayah_start, ayah_end_optional)
        return {
            'surah': int(groups[0]),
            'ayah_start': int(groups[1]),
            'ayah_end': int(groups[2]) if groups[2] else None,
            'detection': 'auto',
            'verified': False,
            'quoted_text': _extract_quoted_text(text, match.end())
        }

    return None


def _extract_quoted_text(text: str, ref_end_pos: int, max_chars: int = 100) -> str:
    """
    Try to extract quoted text that might follow a reference.
    Looks for text in quotes or parentheses after the reference.
    """
    remaining = text[ref_end_pos:ref_end_pos + max_chars + 50]

    # Look for quoted text: "..." or '...' or "..."
    quote_patterns = [
        r'^\s*[:\-]?\s*["\u201c]([^"\u201d]+)["\u201d]',  # "text" or "text"
        r"^\s*[:\-]?\s*'([^']+)'",  # 'text'
    ]

    for pattern in quote_patterns:
        match = re.search(pattern, remaining)
        if match:
            return match.group(1)[:max_chars]

    return ""


def _is_valid_quran_ref(ref: Dict[str, Any]) -> bool:
    """
    Validate that a Quran reference is within valid bounds.
    Quran has 114 surahs, with varying number of ayahs.
    """
    surah = ref.get('surah', 0)
    ayah_start = ref.get('ayah_start', 0)

    # Basic validation: surah must be 1-114
    if not (1 <= surah <= 114):
        return False

    # Ayah must be positive
    if ayah_start < 1:
        return False

    # If ayah_end exists, it must be >= ayah_start
    ayah_end = ref.get('ayah_end')
    if ayah_end is not None and ayah_end < ayah_start:
        return False

    return True


def format_quran_ref(ref: Dict[str, Any]) -> str:
    """Format a Quran reference for display."""
    surah = ref['surah']
    ayah_start = ref['ayah_start']
    ayah_end = ref.get('ayah_end')

    if ayah_end:
        return f"Quran {surah}:{ayah_start}-{ayah_end}"
    else:
        return f"Quran {surah}:{ayah_start}"
