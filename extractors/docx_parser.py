"""
DOCX Parser Module
Extracts paragraphs from DOCX files for annotation.
"""

import re
from docx import Document
from typing import List, Dict, Any, Optional
from io import BytesIO


def detect_paragraph_type(text: str, next_text: Optional[str] = None, prev_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Detect the type of a paragraph based on its content and context.

    Args:
        text: The paragraph text
        next_text: The next paragraph's text (for context)
        prev_type: The previous paragraph's detected type (to avoid double-detection)

    Returns dict with: type, level, quote_type
    """
    word_count = len(text.split())

    # Check if ALL CAPS (chapter heading)
    # Allow for some punctuation but core text should be uppercase
    alpha_chars = [c for c in text if c.isalpha()]
    is_all_caps = len(alpha_chars) > 0 and all(c.isupper() for c in alpha_chars)

    if is_all_caps and word_count <= 15:
        return {
            "type": "chapter_heading",
            "level": 1,
            "quote_type": None
        }

    # Check if short text followed by long paragraph (likely heading)
    if next_text:
        next_word_count = len(next_text.split())
        if word_count < 10 and next_word_count > 50:
            # Additional check: headings often don't end with period
            if not text.endswith('.') or text.endswith('...'):
                return {
                    "type": "chapter_heading",
                    "level": 1,
                    "quote_type": None
                }

    # Check if it's a quote
    # Starts and ends with quotation marks
    quote_chars = ['"', '"', '"', "'", ''', ''']
    starts_with_quote = any(text.startswith(q) for q in quote_chars)
    ends_with_quote = any(text.rstrip('.,;:!?)0123456789- ').endswith(q) for q in quote_chars)

    # Check for Quran reference pattern in text
    has_quran_pattern = bool(re.search(r'\(\d{1,3}:\d{1,3}(?:-\d{1,3})?\)', text))

    # Check for Hadith indicators
    hadith_indicators = [
        r'[Pp]rophet\s+(?:once\s+)?said',
        r'[Pp]rophet\s+(?:\(.*?\))?\s*said',
        r'[Hh]adith',
        r'[Nn]arrated\s+by',
        r'[Rr]eported\s+by',
    ]
    has_hadith_indicator = any(re.search(p, text) for p in hadith_indicators)

    if starts_with_quote and (ends_with_quote or has_quran_pattern):
        quote_type = None
        if has_quran_pattern:
            quote_type = "quran"
        elif has_hadith_indicator:
            quote_type = "hadith"
        else:
            quote_type = "other"

        return {
            "type": "quote",
            "level": None,
            "quote_type": quote_type
        }

    # Check if it's a subheading (short, no period, not immediately after chapter heading)
    if word_count <= 8 and not text.endswith('.'):
        # Avoid detecting as subheading if previous was chapter_heading
        # (the chapter_heading detection uses "short + long next" pattern)
        if prev_type != 'chapter_heading':
            return {
                "type": "subheading",
                "level": 2,
                "quote_type": None
            }

    # Default to paragraph
    return {
        "type": "paragraph",
        "level": None,
        "quote_type": None
    }


def extract_paragraphs(file_content: BytesIO) -> List[Dict[str, Any]]:
    """
    Extract paragraphs from a DOCX file with structure detection.

    Args:
        file_content: BytesIO object containing DOCX file content

    Returns:
        List of paragraph dictionaries with id, text, type, and metadata
    """
    doc = Document(file_content)
    raw_paragraphs = []

    # First pass: collect all non-empty paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            raw_paragraphs.append(text)

    paragraphs = []
    current_chapter_id = None
    para_id = 1
    prev_type = None

    # Second pass: detect types and assign parent chapters
    for i, text in enumerate(raw_paragraphs):
        next_text = raw_paragraphs[i + 1] if i + 1 < len(raw_paragraphs) else None

        # Detect paragraph type (pass prev_type to avoid double-detection)
        type_info = detect_paragraph_type(text, next_text, prev_type)

        # Track current chapter
        if type_info["type"] == "chapter_heading":
            current_chapter_id = para_id
            parent_chapter = None  # Chapter headings don't have parents
        else:
            parent_chapter = current_chapter_id

        paragraphs.append({
            "id": para_id,
            "text": text,
            "type": type_info["type"],
            "level": type_info["level"],
            "parent_chapter_id": parent_chapter,
            "quote_type": type_info["quote_type"],
            "reviewed": False,
            "quran_refs": [],
            "hadith_refs": [],
            "seerah_refs": [],
            "year_refs": [],
            "other_book_refs": [],
            "manual_notes": ""
        })
        para_id += 1
        prev_type = type_info["type"]  # Track for next iteration

    return paragraphs


def get_document_metadata(file_content: BytesIO) -> Dict[str, str]:
    """
    Extract metadata from DOCX file if available.

    Args:
        file_content: BytesIO object containing DOCX file content

    Returns:
        Dictionary with document metadata
    """
    file_content.seek(0)
    doc = Document(file_content)
    core_props = doc.core_properties

    return {
        "title": core_props.title or "",
        "author": core_props.author or "",
        "subject": core_props.subject or "",
        "created": str(core_props.created) if core_props.created else "",
        "modified": str(core_props.modified) if core_props.modified else ""
    }
