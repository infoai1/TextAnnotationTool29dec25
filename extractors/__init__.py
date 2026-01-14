"""Extractors module for parsing documents and detecting references."""

from .docx_parser import parse_docx, iter_paragraphs
from .quran_detector import detect_quran_refs, QuranReference
from .hadith_detector import detect_hadith_refs, HadithReference

__all__ = [
    'parse_docx',
    'iter_paragraphs',
    'detect_quran_refs',
    'QuranReference',
    'detect_hadith_refs',
    'HadithReference',
]
