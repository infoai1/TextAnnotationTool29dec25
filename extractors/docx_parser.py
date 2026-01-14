"""DOCX file parser with optimized paragraph extraction."""

from io import BytesIO
from typing import Iterator
from docx import Document


def parse_docx(file_bytes: bytes) -> list[str]:
    """
    Parse DOCX file and extract non-empty paragraphs.

    Args:
        file_bytes: Raw bytes of the DOCX file

    Returns:
        List of paragraph texts (stripped, non-empty only)
    """
    doc = Document(BytesIO(file_bytes))
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def iter_paragraphs(file_bytes: bytes) -> Iterator[str]:
    """
    Lazily iterate over paragraphs for memory efficiency with large docs.

    Args:
        file_bytes: Raw bytes of the DOCX file

    Yields:
        Non-empty paragraph texts
    """
    doc = Document(BytesIO(file_bytes))
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            yield text
