"""
Footnote Reference Detector Module
Detects [1], [2] style footnote markers and links them to footnote content.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from docx import Document
from io import BytesIO


def detect_footnote_markers(text: str) -> List[Dict[str, Any]]:
    """
    Detect footnote markers like [1], [2], etc. in text.

    Args:
        text: The text to search for footnote markers

    Returns:
        List of detected footnote markers with positions
    """
    refs = []
    seen_positions = set()

    # Pattern: [1], [2], [12], etc. - but not [1:2] which is Quran format
    # Also matches superscript-style markers that may appear as [1] after OCR
    pattern = r'\[(\d{1,3})\](?!\s*:)'

    for match in re.finditer(pattern, text):
        start_pos = match.start()

        if start_pos in seen_positions:
            continue

        marker_num = int(match.group(1))

        refs.append({
            'marker': match.group(0),
            'number': marker_num,
            'start_pos': start_pos,
            'end_pos': match.end(),
            'detection': 'auto',
            'verified': False,
            'linked_footnote': None,  # Will be populated when footnotes are parsed
            'footnote_type': None,    # 'quran', 'hadith', 'book', 'other'
        })
        seen_positions.add(start_pos)

    # Sort by position
    refs.sort(key=lambda x: x['start_pos'])

    return refs


def extract_docx_footnotes(file_content: BytesIO) -> List[Dict[str, Any]]:
    """
    Extract footnotes from a DOCX file.
    Word stores footnotes in a separate XML part.

    Args:
        file_content: BytesIO object containing DOCX file content

    Returns:
        List of footnote dictionaries
    """
    file_content.seek(0)
    doc = Document(file_content)
    footnotes = []

    # Access the footnotes part if it exists
    try:
        # python-docx doesn't directly expose footnotes, but we can access via XML
        from docx.oxml.ns import qn

        # Check if document has footnotes part
        if hasattr(doc.part, '_rels'):
            for rel in doc.part._rels.values():
                if 'footnotes' in rel.reltype:
                    footnotes_part = rel.target_part
                    # Parse footnotes XML
                    footnotes_xml = footnotes_part._element

                    for fn in footnotes_xml.findall('.//' + qn('w:footnote')):
                        fn_id = fn.get(qn('w:id'))
                        if fn_id and int(fn_id) > 0:  # Skip separator footnotes (id 0, -1)
                            # Extract text from footnote
                            text_parts = []
                            for p in fn.findall('.//' + qn('w:t')):
                                if p.text:
                                    text_parts.append(p.text)

                            footnote_text = ''.join(text_parts).strip()
                            if footnote_text:
                                footnotes.append({
                                    'id': int(fn_id),
                                    'text': footnote_text,
                                    'type': classify_footnote(footnote_text),
                                    'verified': False
                                })
    except Exception as e:
        # Fallback: footnotes might not exist or format is different
        pass

    return sorted(footnotes, key=lambda x: x['id'])


def extract_endnotes_from_text(paragraphs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract endnotes that appear at the end of chapters/documents.
    Some books have endnotes as regular paragraphs like:
    [1] Sahih al-Bukhari, Book of Faith
    [2] Quran 3:195

    Args:
        paragraphs: List of paragraph dictionaries

    Returns:
        Tuple of (cleaned paragraphs, extracted endnotes)
    """
    endnotes = []
    cleaned_paragraphs = []
    in_endnotes_section = False
    endnote_pattern = r'^\s*\[(\d{1,3})\]\s*(.+)$'

    for para in paragraphs:
        text = para.get('text', '').strip()

        # Check if this is an endnote line
        match = re.match(endnote_pattern, text)

        if match:
            # This looks like an endnote
            note_num = int(match.group(1))
            note_text = match.group(2).strip()

            endnotes.append({
                'id': note_num,
                'text': note_text,
                'type': classify_footnote(note_text),
                'verified': False,
                'original_para_id': para.get('id')
            })
            in_endnotes_section = True
            # Mark paragraph as endnote (don't add to cleaned)
            para['is_endnote'] = True
            para['endnote_number'] = note_num
        else:
            # If we were in endnotes and hit a non-endnote, section ended
            # (Unless it's very short - might be continuation)
            if in_endnotes_section and len(text) > 100:
                in_endnotes_section = False

            cleaned_paragraphs.append(para)

    return cleaned_paragraphs, endnotes


def classify_footnote(text: str) -> str:
    """
    Classify a footnote as quran, hadith, book, or other.

    Args:
        text: The footnote text

    Returns:
        Classification string
    """
    text_lower = text.lower()

    # Quran patterns
    quran_patterns = [
        r'\d{1,3}:\d{1,3}',  # 3:195
        r'surah',
        r"qur['\u2019]?an",
        r'al-quran',
        r'verse\s+\d',
    ]
    for pattern in quran_patterns:
        if re.search(pattern, text_lower):
            return 'quran'

    # Hadith patterns
    hadith_patterns = [
        r'bukhari',
        r'muslim',
        r'tirmidhi',
        r'abu\s*da[wv]',
        r"nasa['\u2019]?i",
        r'ibn\s*majah',
        r'hadith',
        r'musnad',
        r'muwatta',
    ]
    for pattern in hadith_patterns:
        if re.search(pattern, text_lower):
            return 'hadith'

    # Book/publication patterns
    book_patterns = [
        r'p\.\s*\d+',
        r'page\s+\d+',
        r'vol\.\s*\d+',
        r'volume\s+\d+',
        r'chapter\s+\d+',
        r'ed\.\s*\d{4}',  # edition year
        r'published',
        r'press',
        r'britannica',
        r'encyclopedia',
    ]
    for pattern in book_patterns:
        if re.search(pattern, text_lower):
            return 'book'

    return 'other'


def link_markers_to_footnotes(
    markers: List[Dict[str, Any]],
    footnotes: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Link footnote markers [1], [2] to their corresponding footnote content.

    Args:
        markers: List of detected markers from text
        footnotes: List of extracted footnotes

    Returns:
        Updated markers with linked footnote content
    """
    # Build lookup by footnote number
    footnote_lookup = {fn['id']: fn for fn in footnotes}

    for marker in markers:
        marker_num = marker['number']
        if marker_num in footnote_lookup:
            fn = footnote_lookup[marker_num]
            marker['linked_footnote'] = fn['text']
            marker['footnote_type'] = fn['type']
            marker['footnote_verified'] = fn.get('verified', False)

    return markers


def format_footnote_ref(ref: Dict[str, Any]) -> str:
    """Format a footnote reference for display."""
    marker = ref.get('marker', f"[{ref.get('number', '?')}]")
    fn_type = ref.get('footnote_type', 'unknown')
    linked = ref.get('linked_footnote', '')

    type_emoji = {
        'quran': '🟢',
        'hadith': '🔵',
        'book': '📚',
        'other': '📝'
    }.get(fn_type, '❓')

    if linked:
        # Truncate long footnotes
        display_text = linked[:80] + '...' if len(linked) > 80 else linked
        return f"{type_emoji} {marker} → {display_text}"
    else:
        return f"❓ {marker} (unlinked)"
