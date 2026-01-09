"""
PDF Handler Module
Extracts text from PDF with page numbers for paragraph matching.
"""

import fitz  # PyMuPDF
import streamlit as st
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
import re


def extract_pdf_pages(file_content: BytesIO) -> List[Dict[str, Any]]:
    """
    Extract text from each page of a PDF.

    Args:
        file_content: BytesIO object containing PDF

    Returns:
        List of page dictionaries with page number and text
    """
    file_content.seek(0)
    doc = fitz.open(stream=file_content.read(), filetype="pdf")

    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        pages.append({
            "page_number": page_num + 1,  # 1-indexed
            "text": text,
            "word_count": len(text.split()),
            "char_count": len(text)
        })

    doc.close()
    return pages


def get_pdf_metadata(file_content: BytesIO) -> Dict[str, Any]:
    """
    Get PDF metadata (title, author, page count).
    """
    file_content.seek(0)
    doc = fitz.open(stream=file_content.read(), filetype="pdf")

    metadata = {
        "page_count": len(doc),
        "title": doc.metadata.get("title", ""),
        "author": doc.metadata.get("author", ""),
        "subject": doc.metadata.get("subject", ""),
        "creator": doc.metadata.get("creator", "")
    }

    doc.close()
    return metadata


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    # Remove common punctuation variations
    text = text.lower()
    return text


def find_paragraph_in_pdf(
    paragraph_text: str,
    pdf_pages: List[Dict[str, Any]],
    min_similarity: float = 0.6
) -> Optional[Dict[str, Any]]:
    """
    Find which PDF page contains a paragraph.

    Args:
        paragraph_text: Text from DOCX paragraph
        pdf_pages: List of extracted PDF pages
        min_similarity: Minimum similarity threshold

    Returns:
        Match info with page number and confidence, or None
    """
    if not paragraph_text or len(paragraph_text.strip()) < 20:
        return None

    para_normalized = normalize_text(paragraph_text)

    # Take first 200 chars for matching (faster and handles paragraph splits)
    search_text = para_normalized[:200]

    best_match = None
    best_score = 0

    for page in pdf_pages:
        page_text = normalize_text(page["text"])

        # Quick check: is search text substring of page?
        if search_text[:50] in page_text:
            # Found exact substring match
            return {
                "page_number": page["page_number"],
                "confidence": 1.0,
                "match_type": "exact"
            }

        # Fuzzy match using SequenceMatcher
        # Check multiple positions in page text
        for i in range(0, len(page_text) - 100, 100):
            chunk = page_text[i:i+300]
            ratio = SequenceMatcher(None, search_text[:100], chunk[:100]).ratio()

            if ratio > best_score:
                best_score = ratio
                best_match = {
                    "page_number": page["page_number"],
                    "confidence": round(ratio, 2),
                    "match_type": "fuzzy"
                }

    if best_match and best_score >= min_similarity:
        return best_match

    return None


def match_all_paragraphs_to_pages(
    paragraphs: List[Dict[str, Any]],
    pdf_pages: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Match all DOCX paragraphs to PDF pages.

    Args:
        paragraphs: List of paragraph dicts from DOCX
        pdf_pages: List of page dicts from PDF

    Returns:
        Updated paragraphs with page_info added
    """
    last_known_page = 1

    for para in paragraphs:
        match = find_paragraph_in_pdf(para.get("text", ""), pdf_pages)

        if match:
            para["page_info"] = match
            last_known_page = match["page_number"]
        else:
            # If no match found, estimate based on last known page
            para["page_info"] = {
                "page_number": last_known_page,
                "confidence": 0.0,
                "match_type": "estimated"
            }

    return paragraphs


@st.cache_data(show_spinner=False)
def _render_pdf_page(pdf_bytes: bytes, page_number: int) -> Optional[bytes]:
    """Cached PDF page rendering."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    if page_number < 1 or page_number > len(doc):
        doc.close()
        return None

    page = doc[page_number - 1]

    # Render at 100 DPI (faster, still readable)
    mat = fitz.Matrix(100/72, 100/72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")

    doc.close()
    return img_bytes


def get_page_for_display(
    file_content: BytesIO,
    page_number: int
) -> Optional[bytes]:
    """
    Get a specific page as an image for display (cached).
    """
    file_content.seek(0)
    pdf_bytes = file_content.read()
    return _render_pdf_page(pdf_bytes, page_number)


def search_text_in_pdf(
    file_content: BytesIO,
    search_text: str
) -> List[Dict[str, Any]]:
    """
    Search for text in PDF and return page numbers.

    Args:
        file_content: PDF file content
        search_text: Text to search for

    Returns:
        List of matches with page numbers and positions
    """
    file_content.seek(0)
    doc = fitz.open(stream=file_content.read(), filetype="pdf")

    results = []
    search_lower = search_text.lower()

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").lower()

        if search_lower in text:
            # Find position in text
            pos = text.find(search_lower)

            results.append({
                "page_number": page_num + 1,
                "position": pos,
                "context": text[max(0, pos-50):pos+len(search_text)+50]
            })

    doc.close()
    return results
