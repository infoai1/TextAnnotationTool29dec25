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

# Import shared text utilities
from utils.text_utils import normalize_text

# Import fast text matcher for optimized paragraph matching
try:
    from services.fast_text_matcher import match_paragraphs as fast_match_paragraphs
    FAST_MATCHER_AVAILABLE = True
except ImportError:
    FAST_MATCHER_AVAILABLE = False


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
    exact_matches = []

    for page in pdf_pages:
        page_text = normalize_text(page["text"])

        # FIX #1: Check for exact matches but don't return early
        # Use full search_text (up to 200 chars) to reduce false positives
        # Try longest match first for better accuracy
        if len(search_text) >= 150 and search_text[:150] in page_text:
            exact_matches.append({
                "page_number": page["page_number"],
                "confidence": 1.0,
                "match_type": "exact",
                "match_length": 150,
                "position": page_text.find(search_text[:150])
            })
        elif len(search_text) >= 100 and search_text[:100] in page_text:
            exact_matches.append({
                "page_number": page["page_number"],
                "confidence": 1.0,
                "match_type": "exact",
                "match_length": 100,
                "position": page_text.find(search_text[:100])
            })
        elif search_text[:50] in page_text:
            # Fallback to 50 chars for shorter paragraphs
            exact_matches.append({
                "page_number": page["page_number"],
                "confidence": 1.0,
                "match_type": "exact",
                "match_length": 50,
                "position": page_text.find(search_text[:50])
            })

        # FIX #2: Fuzzy match with 50% overlap (50-char steps instead of 100)
        # Check multiple positions in page text
        for i in range(0, len(page_text) - 100, 50):
            chunk = page_text[i:i+100]  # Match extraction size to comparison
            ratio = SequenceMatcher(None, search_text[:100], chunk).ratio()

            if ratio > best_score:
                best_score = ratio
                best_match = {
                    "page_number": page["page_number"],
                    "confidence": round(ratio, 2),
                    "match_type": "fuzzy"
                }

    # Return best exact match if any found
    # Prefer longer matches (more specific), then first occurrence (sequential flow)
    if exact_matches:
        # Sort by match_length (descending), then by page_number (ascending)
        exact_matches.sort(key=lambda x: (-x.get('match_length', 50), x['page_number']))
        # Remove match_length before returning
        best = exact_matches[0].copy()
        best.pop('match_length', None)
        return best

    if best_match and best_score >= min_similarity:
        return best_match

    return None


def match_all_paragraphs_to_pages(
    paragraphs: List[Dict[str, Any]],
    pdf_pages: List[Dict[str, Any]],
    progress_callback: Optional[Any] = None,
    use_fast_matcher: bool = True
) -> List[Dict[str, Any]]:
    """
    Match all DOCX paragraphs to PDF pages.

    OPTIMIZED: Uses fast bulk matching when available (10x faster)

    Args:
        paragraphs: List of paragraph dicts from DOCX
        pdf_pages: List of page dicts from PDF
        progress_callback: Optional callback function(current, total) for progress updates
        use_fast_matcher: Use fast matcher if available (default True)

    Returns:
        Updated paragraphs with page_info added
    """
    total = len(paragraphs)

    # FAST PATH: Use bulk matching if available (10x faster)
    if use_fast_matcher and FAST_MATCHER_AVAILABLE and total > 5:
        # Extract paragraph texts
        para_texts = [p.get("text", "") for p in paragraphs]

        # Extract PDF page texts
        page_texts = [page.get("text", "") for page in pdf_pages]

        # Run fast matcher ONCE for all paragraphs (threshold=60 for fuzzy matches)
        matches = fast_match_paragraphs(para_texts, page_texts, threshold=60)

        # Build lookup dict: docx_idx → match_info
        match_lookup = {m['docx_idx']: m for m in matches}

        # Apply matches to paragraphs with sequential fallback logic
        last_known_page = 1
        consecutive_unmatched = 0

        for i, para in enumerate(paragraphs):
            if i in match_lookup:
                match = match_lookup[i]
                para["page_info"] = {
                    "page_number": match['pdf_idx'] + 1,  # Convert to 1-indexed
                    "confidence": match['score'] / 100,    # Convert to 0-1 scale
                    "match_type": match['method']
                }
                last_known_page = match['pdf_idx'] + 1
                consecutive_unmatched = 0
            else:
                # Sequential fallback for unmatched paragraphs
                consecutive_unmatched += 1

                if consecutive_unmatched > 3:
                    max_page = max(p["page_number"] for p in pdf_pages) if pdf_pages else 1
                    if last_known_page < max_page:
                        last_known_page += 1
                    consecutive_unmatched = 1

                para["page_info"] = {
                    "page_number": last_known_page,
                    "confidence": 0.0,
                    "match_type": "estimated"
                }

            # Call progress callback every paragraph for smooth updates
            if progress_callback:
                progress_callback(i + 1, total)

        # Final progress update
        if progress_callback:
            progress_callback(total, total)

        return paragraphs

    # SLOW PATH: Fall back to original paragraph-by-paragraph matching
    # (Used if fast matcher not available or disabled)
    last_known_page = 1
    consecutive_unmatched = 0

    for i, para in enumerate(paragraphs):
        match = find_paragraph_in_pdf(para.get("text", ""), pdf_pages)

        if match:
            para["page_info"] = match
            last_known_page = match["page_number"]
            consecutive_unmatched = 0
        else:
            consecutive_unmatched += 1

            if consecutive_unmatched > 3:
                max_page = max(p["page_number"] for p in pdf_pages) if pdf_pages else 1
                if last_known_page < max_page:
                    last_known_page += 1
                consecutive_unmatched = 1

            para["page_info"] = {
                "page_number": last_known_page,
                "confidence": 0.0,
                "match_type": "estimated"
            }

        # Call progress callback every paragraph for smooth updates
        if progress_callback:
            progress_callback(i + 1, total)

    # Final progress update
    if progress_callback:
        progress_callback(total, total)

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
