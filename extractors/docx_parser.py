"""
DOCX Parser Module
Extracts paragraphs from DOCX files for annotation.
"""

from docx import Document
from typing import List, Dict, Any
from io import BytesIO


def extract_paragraphs(file_content: BytesIO) -> List[Dict[str, Any]]:
    """
    Extract paragraphs from a DOCX file.

    Args:
        file_content: BytesIO object containing DOCX file content

    Returns:
        List of paragraph dictionaries with id, text, and metadata
    """
    doc = Document(file_content)
    paragraphs = []

    para_id = 1
    for para in doc.paragraphs:
        text = para.text.strip()

        # Skip empty paragraphs
        if not text:
            continue

        paragraphs.append({
            "id": para_id,
            "text": text,
            "reviewed": False,
            "quran_refs": [],
            "hadith_refs": [],
            "seerah_refs": [],
            "manual_notes": ""
        })
        para_id += 1

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
