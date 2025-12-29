"""
Text Highlighter Utility
Formats text with color-coded highlights for Quran and Hadith references.
"""

import re
from typing import List, Dict, Any, Tuple


def get_highlight_css() -> str:
    """Return CSS styles for highlights."""
    return """
    <style>
    div.paragraph-box {
        background-color: #3a3a3a !important;
        color: #ffffff !important;
        padding: 20px !important;
        border-radius: 8px !important;
        margin: 10px 0 !important;
        border-left: 4px solid #9e9e9e !important;
        line-height: 1.8 !important;
        min-height: 80px !important;
        font-size: 1.05em !important;
    }
    div.paragraph-box * {
        color: #ffffff !important;
    }
    div.paragraph-box.reviewed {
        border-left-color: #4caf50 !important;
        background-color: #2d4a32 !important;
    }
    div.paragraph-box span.highlight-quran {
        background-color: #4caf50 !important;
        color: #ffffff !important;
        padding: 2px 6px !important;
        border-radius: 3px !important;
    }
    div.paragraph-box span.highlight-hadith {
        background-color: #2196f3 !important;
        color: #ffffff !important;
        padding: 2px 6px !important;
        border-radius: 3px !important;
    }
    div.paragraph-box span.highlight-keyword {
        background-color: #ff9800 !important;
        color: #000000 !important;
        padding: 2px 4px !important;
        border-radius: 3px !important;
        font-weight: 500 !important;
    }
    div.paragraph-box span.highlight-number {
        background-color: #9c27b0 !important;
        color: #ffffff !important;
        padding: 1px 4px !important;
        border-radius: 3px !important;
    }
    div.paragraph-box span.highlight-year {
        background-color: #00bcd4 !important;
        color: #000000 !important;
        padding: 1px 4px !important;
        border-radius: 3px !important;
        font-weight: 500 !important;
    }
    .ref-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.85em;
        margin: 2px;
    }
    .ref-tag.quran {
        background-color: #4caf50;
        color: white;
    }
    .ref-tag.hadith {
        background-color: #2196f3;
        color: white;
    }
    .detection-badge {
        font-size: 0.75em;
        padding: 1px 6px;
        border-radius: 8px;
        margin-left: 5px;
    }
    .detection-badge.auto {
        background-color: #ff9800;
        color: white;
    }
    .detection-badge.manual {
        background-color: #9c27b0;
        color: white;
    }
    /* Structure type styles */
    div.paragraph-box.type-chapter_heading {
        background-color: #1a237e !important;
        border-left-color: #3f51b5 !important;
        font-size: 1.3em !important;
        font-weight: bold !important;
        text-align: center !important;
        padding: 25px !important;
    }
    div.paragraph-box.type-subheading {
        background-color: #283593 !important;
        border-left-color: #5c6bc0 !important;
        font-size: 1.15em !important;
        font-weight: bold !important;
        padding: 18px !important;
    }
    div.paragraph-box.type-quote {
        background-color: #424242 !important;
        border-left-color: #ff9800 !important;
        font-style: italic !important;
        padding-left: 30px !important;
        margin-left: 20px !important;
        border-left-width: 3px !important;
    }
    div.paragraph-box.type-quote.quote-quran {
        border-left-color: #4caf50 !important;
        background-color: #1b3320 !important;
    }
    div.paragraph-box.type-quote.quote-hadith {
        border-left-color: #2196f3 !important;
        background-color: #1a2d40 !important;
    }
    /* Structure type badge */
    .structure-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75em;
        margin-left: 8px;
        font-weight: normal;
    }
    .structure-badge.chapter_heading {
        background-color: #3f51b5;
        color: white;
    }
    .structure-badge.subheading {
        background-color: #5c6bc0;
        color: white;
    }
    .structure-badge.quote {
        background-color: #ff9800;
        color: black;
    }
    .structure-badge.paragraph {
        background-color: #757575;
        color: white;
    }
    </style>
    """


# Default keywords to highlight
DEFAULT_KEYWORDS = [
    "Quran", "Qur'an", "Hadith", "Prophet", "Surah", "Ayah", "Verse",
    "Allah", "Muhammad", "Sunnah", "Sahih", "Bukhari", "Muslim"
]


def find_keyword_positions(text: str, keywords: List[str]) -> List[Tuple[int, int, str]]:
    """
    Find positions of keywords in text.

    Returns list of (start, end, type) tuples.
    """
    positions = []

    # Find keywords (case-insensitive)
    for keyword in keywords:
        if not keyword.strip():
            continue
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        for match in pattern.finditer(text):
            positions.append((match.start(), match.end(), 'keyword'))

    return positions


def find_number_positions(text: str) -> List[Tuple[int, int, str]]:
    """
    Find positions of numbers/numerical references in text.

    Returns list of (start, end, type) tuples.
    """
    positions = []

    # Pattern for numbers: standalone numbers, X:Y format, ranges
    patterns = [
        r'\b\d{1,3}:\d{1,3}(?:-\d{1,3})?\b',  # 3:195 or 4:11-12
        r'\b\d+\b',  # standalone numbers
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            positions.append((match.start(), match.end(), 'number'))

    return positions


def find_year_positions(text: str) -> List[Tuple[int, int, str]]:
    """
    Find positions of year/time references in text.
    Detects: AD, BC, CE, BCE, AH (Islamic calendar), century, year patterns.

    Returns list of (start, end, type) tuples.
    """
    positions = []

    # Patterns for year/time references
    year_patterns = [
        # Year followed by AD/BC/CE/BCE/AH
        r'\b(\d{1,4})\s*(AD|BC|CE|BCE|AH|A\.D\.|B\.C\.|C\.E\.|B\.C\.E\.|A\.H\.)\b',
        # AD/BC/CE/BCE/AH followed by year
        r'\b(AD|BC|CE|BCE|AH|A\.D\.|B\.C\.|C\.E\.|B\.C\.E\.|A\.H\.)\s*(\d{1,4})\b',
        # Century patterns: 7th century, 21st century, etc.
        r'\b(\d{1,2})(st|nd|rd|th)\s+century\b',
        # "century" alone with number before
        r'\b(\d{1,2})\s+century\b',
        # Year in parentheses like (1400) or (d. 1453)
        r'\((?:d\.\s*|b\.\s*|r\.\s*)?(\d{3,4})\)',
        # Standalone 4-digit years that look like dates (1000-2100 range)
        r'\b(1[0-9]{3}|20[0-2][0-9])\b',
        # Hijri year patterns
        r'\b(\d{1,4})\s*(?:Hijri|hijri|H\.)\b',
    ]

    for pattern in year_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            positions.append((match.start(), match.end(), 'year'))

    return positions


def highlight_text(
    text: str,
    quran_refs: List[Dict[str, Any]],
    hadith_refs: List[Dict[str, Any]]
) -> str:
    """
    Apply color-coded highlights to text based on detected references.

    Args:
        text: The original text
        quran_refs: List of Quran reference dictionaries with start_pos and end_pos
        hadith_refs: List of Hadith reference dictionaries with start_pos and end_pos

    Returns:
        HTML string with highlighted references
    """
    if not quran_refs and not hadith_refs:
        return _escape_html(text)

    # Combine all references with their type
    all_refs = []
    for ref in quran_refs:
        if 'start_pos' in ref and 'end_pos' in ref:
            all_refs.append((ref['start_pos'], ref['end_pos'], 'quran', ref))
    for ref in hadith_refs:
        if 'start_pos' in ref and 'end_pos' in ref:
            all_refs.append((ref['start_pos'], ref['end_pos'], 'hadith', ref))

    # Sort by start position (descending to replace from end first)
    all_refs.sort(key=lambda x: x[0], reverse=True)

    # Apply highlights from end to start to preserve positions
    result = text
    for start, end, ref_type, ref in all_refs:
        matched_text = result[start:end]
        css_class = f"highlight-{ref_type}"
        highlighted = f'<span class="{css_class}">{_escape_html(matched_text)}</span>'
        result = result[:start] + highlighted + result[end:]

    # Escape remaining HTML but preserve our highlights
    # We already escaped the matched text, now escape the rest
    # This is a simplified approach - the text between highlights needs escaping
    return result


def highlight_text_simple(
    text: str,
    quran_refs: List[Dict[str, Any]],
    hadith_refs: List[Dict[str, Any]],
    keywords: List[str] = None,
    highlight_numbers: bool = False,
    highlight_years: bool = False
) -> str:
    """
    Apply highlights using a simpler approach that handles overlapping better.
    Builds the result character by character.

    Args:
        text: The text to highlight
        quran_refs: Quran reference positions
        hadith_refs: Hadith reference positions
        keywords: List of keywords to highlight (optional)
        highlight_numbers: Whether to highlight numbers (optional)
        highlight_years: Whether to highlight year/time references (optional)
    """
    # Collect all highlight ranges with priority
    # Priority: quran > hadith > year > keyword > number
    ranges = []  # (start, end, type, priority)

    for ref in quran_refs:
        if 'start_pos' in ref and 'end_pos' in ref:
            ranges.append((ref['start_pos'], ref['end_pos'], 'quran', 1))

    for ref in hadith_refs:
        if 'start_pos' in ref and 'end_pos' in ref:
            ranges.append((ref['start_pos'], ref['end_pos'], 'hadith', 2))

    if highlight_years:
        for start, end, htype in find_year_positions(text):
            ranges.append((start, end, htype, 3))

    if keywords:
        for start, end, htype in find_keyword_positions(text, keywords):
            ranges.append((start, end, htype, 4))

    if highlight_numbers:
        for start, end, htype in find_number_positions(text):
            ranges.append((start, end, htype, 5))

    if not ranges:
        return _escape_html(text)

    # Sort by start position, then by priority (lower = higher priority)
    ranges.sort(key=lambda x: (x[0], x[3]))

    # Remove overlapping ranges (keep higher priority)
    filtered_ranges = []
    for r in ranges:
        start, end, htype, priority = r
        overlaps = False
        for fr in filtered_ranges:
            fstart, fend, _, _ = fr
            # Check if current range overlaps with an existing one
            if start < fend and end > fstart:
                overlaps = True
                break
        if not overlaps:
            filtered_ranges.append(r)

    # Sort by start position for processing
    filtered_ranges.sort(key=lambda x: x[0])

    # Build result
    result = []
    last_end = 0

    for start, end, htype, _ in filtered_ranges:
        # Add text before this highlight
        if start > last_end:
            result.append(_escape_html(text[last_end:start]))

        # Add highlighted text
        result.append(f'<span class="highlight-{htype}">')
        result.append(_escape_html(text[start:end]))
        result.append('</span>')

        last_end = end

    # Add remaining text
    if last_end < len(text):
        result.append(_escape_html(text[last_end:]))

    return ''.join(result)


def format_paragraph_html(
    paragraph: Dict[str, Any],
    quran_refs: List[Dict[str, Any]],
    hadith_refs: List[Dict[str, Any]]
) -> str:
    """
    Format a complete paragraph box with highlights.

    Args:
        paragraph: Paragraph dictionary
        quran_refs: Detected Quran references
        hadith_refs: Detected Hadith references

    Returns:
        Complete HTML for the paragraph display
    """
    text = paragraph.get('text', '')
    reviewed = paragraph.get('reviewed', False)

    highlighted_text = highlight_text_simple(text, quran_refs, hadith_refs)

    reviewed_class = 'reviewed' if reviewed else ''

    return f'''
    <div class="paragraph-box {reviewed_class}">
        {highlighted_text}
    </div>
    '''


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def create_ref_tag(ref_type: str, text: str, detection: str = 'auto') -> str:
    """Create an HTML tag for displaying a reference."""
    badge_class = 'auto' if detection == 'auto' else 'manual'
    return f'''
    <span class="ref-tag {ref_type}">
        {_escape_html(text)}
        <span class="detection-badge {badge_class}">{detection}</span>
    </span>
    '''
