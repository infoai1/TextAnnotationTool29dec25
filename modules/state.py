"""
BookState - Centralized session state management.

This module provides a typed, centralized way to manage all annotation tool state.
Instead of 25+ scattered st.session_state variables, everything lives in BookState.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime
import time
import streamlit as st


@dataclass
class BookState:
    """
    Central data structure for book annotation.

    Replaces 25+ scattered session state variables with a single typed class.
    Makes state management clear, testable, and easier to modify.
    """

    # Book metadata
    book_title: str = ""
    author: str = "Maulana Wahiduddin Khan"
    book_slug: str = ""
    annotator: str = ""

    # Content
    paragraphs: List[Dict] = field(default_factory=list)
    groups: List[Dict] = field(default_factory=list)

    # References and detection
    detected_refs: Dict = field(default_factory=dict)  # para_id → {quran: [], hadith: []}
    document_footnotes: List = field(default_factory=list)
    endnotes: List = field(default_factory=list)

    # Highlighting settings
    highlight_keywords: bool = True
    highlight_numbers: bool = True
    highlight_years: bool = True
    custom_keywords: List[str] = field(default_factory=list)

    # Grouping & selection
    selected_for_grouping: Set[str] = field(default_factory=set)
    selected_groups: Set[str] = field(default_factory=set)
    selected_for_approval: Set[str] = field(default_factory=set)

    # PDF support
    pdf_pages: List = field(default_factory=list)
    pdf_loaded: bool = False

    # File upload state
    file_uploaded: bool = False

    # Navigation
    last_read_para: Optional[str] = None
    last_worked_para: Optional[str] = None
    scroll_to_para: Optional[str] = None
    scroll_to_group: Optional[str] = None

    # UI state
    view_mode: str = 'Paragraph View'

    # Workflow
    book_status: str = 'pending'
    current_book_folder: Optional[str] = None

    # User info
    current_user: str = 'guest'
    user_role: str = 'annotator'

    # Auto-save
    last_save_time: Optional[datetime] = None
    has_unsaved_changes: bool = False
    last_activity: float = 0.0

    # Feature flags
    auto_detect_enabled: bool = True

    # Token counting cache (performance optimization)
    _token_cache: Dict[str, int] = field(default_factory=dict)


    def mark_activity(self, para_id: Optional[str] = None):
        """
        Track user activity for auto-save.

        Called whenever user makes a change (edits paragraph, verifies ref, etc).
        Updates timestamp and marks changes as unsaved.

        Args:
            para_id: Optional paragraph ID that was modified
        """
        self.last_activity = time.time()
        self.has_unsaved_changes = True
        if para_id is not None:
            self.last_worked_para = para_id


    def needs_auto_save(self, auto_save_interval: int = 30) -> bool:
        """
        Check if auto-save should trigger.

        Args:
            auto_save_interval: Seconds between auto-saves (default 30)

        Returns:
            True if should auto-save now
        """
        if not self.has_unsaved_changes:
            return False

        elapsed = time.time() - self.last_activity
        return elapsed >= auto_save_interval


    def get_tokens(self, text: str, helpers_module) -> int:
        """
        Count tokens with caching for performance.

        Tokens are expensive to calculate repeatedly. This caches results.

        Args:
            text: Text to count tokens for
            helpers_module: Reference to helpers module (for count_tokens)

        Returns:
            Token count
        """
        if text not in self._token_cache:
            result = helpers_module.count_tokens(text)
            self._token_cache[text] = result.get('total', 0)
        return self._token_cache[text]


    def get_group_tokens(self, group_id: str, helpers_module) -> int:
        """
        Calculate total tokens for a group.

        Sums token counts for all paragraphs in the group.

        Args:
            group_id: Group ID to calculate tokens for
            helpers_module: Reference to helpers module

        Returns:
            Total token count
        """
        total = 0
        for p in self.paragraphs:
            if p.get('group_id') == group_id:
                total += self.get_tokens(p.get('text', ''), helpers_module)
        return total


    @classmethod
    def from_session_state(cls, st_session, default_keywords: List[str] = None):
        """
        Initialize BookState from Streamlit session state.

        Used when transitioning from old scattered session vars to BookState.

        Args:
            st_session: Streamlit session_state object
            default_keywords: Default keywords for highlighting

        Returns:
            BookState instance populated from session state
        """
        if default_keywords is None:
            default_keywords = []

        return cls(
            book_title=st_session.get('book_title', ''),
            author=st_session.get('author', 'Maulana Wahiduddin Khan'),
            book_slug=st_session.get('book_slug', ''),
            annotator=st_session.get('annotator', ''),

            paragraphs=st_session.get('paragraphs', []),
            groups=st_session.get('groups', []),

            detected_refs=st_session.get('detected_refs', {}),
            document_footnotes=st_session.get('document_footnotes', []),
            endnotes=st_session.get('endnotes', []),

            highlight_keywords=st_session.get('highlight_keywords', True),
            highlight_numbers=st_session.get('highlight_numbers', True),
            highlight_years=st_session.get('highlight_years', True),
            custom_keywords=st_session.get('custom_keywords', default_keywords.copy()),

            selected_for_grouping=st_session.get('selected_for_grouping', set()),
            selected_groups=st_session.get('selected_groups', set()),
            selected_for_approval=st_session.get('selected_for_approval', set()),

            pdf_pages=st_session.get('pdf_pages', []),
            pdf_loaded=st_session.get('pdf_loaded', False),

            file_uploaded=st_session.get('file_uploaded', False),

            last_read_para=st_session.get('last_read_para', None),
            last_worked_para=st_session.get('last_worked_para', None),
            scroll_to_para=st_session.get('scroll_to_para', None),
            scroll_to_group=st_session.get('scroll_to_group', None),

            view_mode=st_session.get('view_mode', 'Paragraph View'),

            book_status=st_session.get('book_status', 'pending'),
            current_book_folder=st_session.get('current_book_folder', None),

            current_user=st_session.get('current_user', 'guest'),
            user_role=st_session.get('user_role', 'annotator'),

            last_save_time=st_session.get('last_save_time', None),
            has_unsaved_changes=st_session.get('has_unsaved_changes', False),
            last_activity=st_session.get('last_activity', time.time()),

            auto_detect_enabled=st_session.get('auto_detect_enabled', True),
        )


    def to_session_state(self, st_session):
        """
        Sync BookState back to Streamlit session state.

        Call this after modifying BookState to update the UI.

        Args:
            st_session: Streamlit session_state object
        """
        st_session.book_title = self.book_title
        st_session.author = self.author
        st_session.book_slug = self.book_slug
        st_session.annotator = self.annotator

        st_session.paragraphs = self.paragraphs
        st_session.groups = self.groups

        st_session.detected_refs = self.detected_refs
        st_session.document_footnotes = self.document_footnotes
        st_session.endnotes = self.endnotes

        st_session.highlight_keywords = self.highlight_keywords
        st_session.highlight_numbers = self.highlight_numbers
        st_session.highlight_years = self.highlight_years
        st_session.custom_keywords = self.custom_keywords

        st_session.selected_for_grouping = self.selected_for_grouping
        st_session.selected_groups = self.selected_groups
        st_session.selected_for_approval = self.selected_for_approval

        st_session.pdf_pages = self.pdf_pages
        st_session.pdf_loaded = self.pdf_loaded

        st_session.file_uploaded = self.file_uploaded

        st_session.last_read_para = self.last_read_para
        st_session.last_worked_para = self.last_worked_para
        st_session.scroll_to_para = self.scroll_to_para
        st_session.scroll_to_group = self.scroll_to_group

        st_session.view_mode = self.view_mode

        st_session.book_status = self.book_status
        st_session.current_book_folder = self.current_book_folder

        st_session.current_user = self.current_user
        st_session.user_role = self.user_role

        st_session.last_save_time = self.last_save_time
        st_session.has_unsaved_changes = self.has_unsaved_changes
        st_session.last_activity = self.last_activity

        st_session.auto_detect_enabled = self.auto_detect_enabled


    def reset(self):
        """Reset to initial state (for loading new book)."""
        self.paragraphs = []
        self.groups = []
        self.detected_refs = {}
        self.document_footnotes = []
        self.endnotes = []
        self.selected_for_grouping = set()
        self.selected_groups = set()
        self.selected_for_approval = set()
        self.pdf_pages = []
        self.pdf_loaded = False
        self.file_uploaded = False
        self.last_read_para = None
        self.last_worked_para = None
        self.scroll_to_para = None
        self.scroll_to_group = None
        self.has_unsaved_changes = False
        self._token_cache = {}
