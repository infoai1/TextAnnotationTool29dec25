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
    .highlight-quran {
        background-color: #c8e6c9;
        padding: 2px 4px;
        border-radius: 3px;
        border-bottom: 2px solid #4caf50;
    }
    .highlight-hadith {
        background-color: #bbdefb;
        padding: 2px 4px;
        border-radius: 3px;
        border-bottom: 2px solid #2196f3;
    }
    .paragraph-box {
        background-color: #f5f5f5;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #9e9e9e;
        line-height: 1.6;
    }
    .paragraph-box.reviewed {
        border-left-color: #4caf50;
        background-color: #f1f8e9;
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
    </style>
    """


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
    hadith_refs: List[Dict[str, Any]]
) -> str:
    """
    Apply highlights using a simpler approach that handles overlapping better.
    Builds the result character by character.
    """
    if not quran_refs and not hadith_refs:
        return _escape_html(text)

    # Create a map of positions to highlight type
    highlight_map = {}  # position -> (type, 'start'/'end')

    for ref in quran_refs:
        if 'start_pos' in ref and 'end_pos' in ref:
            start, end = ref['start_pos'], ref['end_pos']
            highlight_map[start] = ('quran', 'start')
            highlight_map[end] = ('quran', 'end')

    for ref in hadith_refs:
        if 'start_pos' in ref and 'end_pos' in ref:
            start, end = ref['start_pos'], ref['end_pos']
            if start not in highlight_map:
                highlight_map[start] = ('hadith', 'start')
            if end not in highlight_map:
                highlight_map[end] = ('hadith', 'end')

    # Build result
    result = []
    for i, char in enumerate(text):
        if i in highlight_map:
            ref_type, action = highlight_map[i]
            if action == 'start':
                result.append(f'<span class="highlight-{ref_type}">')
            elif action == 'end':
                result.append('</span>')
        result.append(_escape_html(char))

    # Handle any trailing end tags
    final_pos = len(text)
    if final_pos in highlight_map:
        ref_type, action = highlight_map[final_pos]
        if action == 'end':
            result.append('</span>')

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
