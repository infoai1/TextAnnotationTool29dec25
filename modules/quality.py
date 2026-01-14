"""
QualityControl - Data detection and cleanup for annotation tool.

Handles junk detection, PDF/DOCX processing pipelines.
"""

from typing import List, Dict, Callable, Optional
import re


class QualityControl:
    """
    Data detection and cleanup.

    **Key Methods**:
    - detect_junk_paragraphs(): Identify likely junk (TOC, headers, etc.)
    - (PDF/DOCX processing left in app.py for now - too complex to extract quickly)
    """

    # Junk detection patterns
    JUNK_PATTERNS = [
        r'^Table of Contents$',
        r'^Contents$',
        r'^Index$',
        r'^Bibliography$',
        r'^Page \d+$',
        r'^\d+\s*$',  # Just numbers
        r'^Chapter \d+\s*$',  # Standalone "Chapter 1"
        r'^[ivxIVX]+\s*$',  # Roman numerals only
        r'^\.\.\.\s*$',  # Just dots
        r'^-+\s*$',  # Just dashes
    ]

    def __init__(self):
        """Initialize QualityControl."""
        self.junk_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.JUNK_PATTERNS]


    def detect_junk_paragraphs(self, paragraphs: List[Dict]) -> List[Dict]:
        """
        Identify likely junk paragraphs using heuristics.

        **Junk criteria**:
        - Too short (< 20 chars)
        - Matches junk patterns (TOC, page numbers, etc.)
        - All uppercase (likely header)
        - All numbers
        - Repeating characters

        Args:
            paragraphs: List of paragraph dicts

        Returns:
            List of junk paragraphs (subset of input)
        """
        junk = []

        for para in paragraphs:
            text = para.get('text', '').strip()

            # Too short
            if len(text) < 20:
                junk.append(para)
                continue

            # Matches junk pattern
            if any(regex.match(text) for regex in self.junk_regex):
                junk.append(para)
                continue

            # All uppercase (likely header)
            if text.isupper() and len(text) > 10:
                junk.append(para)
                continue

            # All numbers
            if text.replace(' ', '').replace(',', '').replace('.', '').isdigit():
                junk.append(para)
                continue

            # Repeating chars (like "........" or "--------")
            if len(set(text.replace(' ', ''))) < 3:
                junk.append(para)
                continue

        return junk


    def mark_junk(self, paragraphs: List[Dict]) -> List[Dict]:
        """
        Mark junk paragraphs with 'is_junk' flag (non-destructive).

        Args:
            paragraphs: List of paragraph dicts

        Returns:
            Same list with 'is_junk' flags added
        """
        junk_paras = self.detect_junk_paragraphs(paragraphs)
        junk_ids = {p.get('id') for p in junk_paras}

        for para in paragraphs:
            para['is_junk'] = para.get('id') in junk_ids

        return paragraphs
