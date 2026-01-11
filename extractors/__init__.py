from .docx_parser import extract_paragraphs
from .quran_detector import detect_quran_refs
from .hadith_detector import detect_hadith_refs
from .footnote_detector import (
    detect_footnote_markers,
    extract_docx_footnotes,
    extract_endnotes_from_text,
    link_markers_to_footnotes
)

__all__ = [
    'extract_paragraphs',
    'detect_quran_refs',
    'detect_hadith_refs',
    'detect_footnote_markers',
    'extract_docx_footnotes',
    'extract_endnotes_from_text',
    'link_markers_to_footnotes'
]
