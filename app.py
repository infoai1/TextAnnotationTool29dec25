"""
Islamic Text Annotation Tool
A Streamlit app to display DOCX books, auto-detect Quran/Hadith references,
and enable manual annotation. Supports PDF side-by-side verification.
"""

VERSION = "2.5.0"
BUILD_DATE = "2026-01-09"
# 2.5.0 - Smart grouping for LightRAG export (512-800 tokens, chapter boundaries)
# 2.4.0 - Modern UI redesign with white cards, colored pill tags

import streamlit as st
import streamlit.components.v1 as components
import streamlit_authenticator as stauth
import yaml
import json
import base64
import os
import tempfile
import asyncio
import glob
import time  # For elapsed time tracking
from datetime import datetime
from io import BytesIO

from extractors import (
    extract_paragraphs,
    detect_quran_refs,
    detect_hadith_refs,
    detect_footnote_markers,
    extract_docx_footnotes,
    extract_endnotes_from_text,
    link_markers_to_footnotes
)
from concept_extractor import (
    extract_batch_range,
    merge_extractions_to_paragraphs,
    get_extraction_stats,
    gemini_rotator
)
from lightrag_export import export_for_lightrag
from extractors.docx_parser import get_document_metadata
from extractors.quran_detector import format_quran_ref
from extractors.hadith_detector import format_hadith_ref, get_collection_list
from utils.highlighter import get_highlight_css, highlight_text_simple, DEFAULT_KEYWORDS, find_year_positions

# Refactored modules
from config import (
    DATA_DIR,
    BOOKS_DIR,
    AUTO_SAVE_INTERVAL,
    VERSION_KEEP_COUNT,
    LOCK_TIMEOUT_HOURS,
    GROUP_TOKEN_MIN,
    GROUP_TOKEN_TARGET,
    GROUP_TOKEN_MAX
)
from helpers import (
    slugify,
    humanize_time_ago as helpers_humanize_time_ago,
    estimate_tokens as helpers_estimate_tokens,
    count_tokens as helpers_count_tokens,
    validate_para_id,
    validate_group_id
)
import db

# PDF handling imports
try:
    from services.pdf_handler import extract_pdf_pages, match_all_paragraphs_to_pages
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# ============= LOGGING SETUP =============
import logging
from pathlib import Path

# Setup logging
LOG_DIR = Path("/root/annotation_tool/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # Also print to console
    ]
)
logger = logging.getLogger(__name__)

# Button-specific logger with rotation
from logging.handlers import RotatingFileHandler
button_logger = logging.getLogger('buttons')
button_logger.setLevel(logging.INFO)
button_log_handler = RotatingFileHandler(
    LOG_DIR / 'buttons.log',
    maxBytes=1024*1024,  # 1MB
    backupCount=3
)
button_log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
button_logger.addHandler(button_log_handler)

# ============= CACHING FOR PERFORMANCE =============
@st.cache_data(show_spinner=False)
def cached_extract_paragraphs(file_bytes: bytes):
    """Cached wrapper for DOCX parsing."""
    return extract_paragraphs(BytesIO(file_bytes))

@st.cache_data(show_spinner=False, ttl=3600)
def cached_detect_quran_refs(text: str):
    """Cached wrapper for Quran detection (1 hour TTL)."""
    return detect_quran_refs(text)

@st.cache_data(show_spinner=False)
def cached_detect_hadith_refs(text: str):
    """Cached wrapper for Hadith detection."""
    return detect_hadith_refs(text)


# Page configuration
st.set_page_config(
    page_title="Book Annotation Tool",
    layout="wide"
)

# Apply custom CSS
st.markdown(get_highlight_css(), unsafe_allow_html=True)

# Load Material Icons font FIRST via <link> tag (more reliable than @import)
st.markdown('<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">', unsafe_allow_html=True)
st.markdown('<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded" rel="stylesheet">', unsafe_allow_html=True)

# ============= MODERN UI THEME v2.5.1 =============
st.markdown("""
<style>
/* ===== GOOGLE FONTS ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons');


/* ===== COLOR PALETTE ===== */
:root {
    --bg-main: #1e293b;
    --bg-sidebar: #0f172a;
    --card-bg: #ffffff;
    --card-shadow: 0 1px 3px rgba(0,0,0,0.1);
    --card-shadow-hover: 0 4px 12px rgba(0,0,0,0.15);
    --card-radius: 8px;

    /* Role accents */
    --annotator-accent: #3b82f6;
    --admin-accent: #10b981;

    /* Tag colors */
    --tag-concept: #14b8a6;
    --tag-aspect: #8b5cf6;
    --tag-people: #ef4444;
    --tag-places: #3b82f6;
    --tag-hadith: #f59e0b;
    --tag-islamic: #f59e0b;

    /* Text */
    --text-dark: #1e293b;
    --text-light: #f8fafc;
    --text-muted: #64748b;
    --text-secondary: #94a3b8;

    /* Borders */
    --border-light: #e2e8f0;
    --border-dark: #334155;
}

/* ===== GLOBAL BACKGROUND ===== */
.stApp {
    background: var(--bg-main) !important;
}

/* ===== MAIN CONTENT TEXT ===== */
.stApp p, .stApp span, .stApp div, .stApp label {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

/* Light text on dark backgrounds */
.stApp {
    color: var(--text-light) !important;
}

/* ===== SIDEBAR ===== */
[data-testid="stSidebar"] {
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border-dark) !important;
}

[data-testid="stSidebar"] * {
    color: var(--text-light) !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: var(--annotator-accent) !important;
}

/* ===== HEADINGS ===== */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    color: var(--text-light) !important;
}

/* ===== WHITE CARDS (Paragraph containers) ===== */
.paragraph-card {
    background: var(--card-bg) !important;
    border-radius: var(--card-radius) !important;
    box-shadow: var(--card-shadow) !important;
    padding: 1rem 1.25rem !important;
    margin-bottom: 1rem !important;
    transition: all 0.2s ease !important;
}

.paragraph-card:hover {
    box-shadow: var(--card-shadow-hover) !important;
    transform: translateY(-2px);
}

.paragraph-card * {
    color: var(--text-dark) !important;
}

/* ===== GROUP CONTAINERS ===== */
.group-container {
    transition: all 0.3s ease;
}

.group-container:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.group-bg-even {
    background-color: #f0f9ff;
}

.group-bg-odd {
    background-color: #f8fafc;
}

/* ===== EXPANDERS AS DARK CARDS ===== */
[data-testid="stExpander"] {
    background: rgba(30, 41, 59, 0.4) !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    border-radius: var(--card-radius) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    margin-bottom: 0.75rem !important;
    overflow: hidden !important;
}

[data-testid="stExpander"]:hover {
    background: rgba(30, 41, 59, 0.6) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
}

[data-testid="stExpander"] details {
    border: none !important;
}

[data-testid="stExpander"] summary {
    color: var(--text-light) !important;
    font-weight: 500 !important;
    padding: 0.75rem 1rem !important;
}

[data-testid="stExpander"] summary:hover {
    background: rgba(51, 65, 85, 0.5) !important;
}

[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    padding: 0 1rem 1rem 1rem !important;
}

[data-testid="stExpander"] [data-testid="stExpanderDetails"] * {
    color: var(--text-light) !important;
}

/* ===== BUTTONS ===== */
.stButton > button {
    background: var(--annotator-accent) !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
}

.stButton > button:hover {
    background: #2563eb !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3) !important;
}

/* Submit button - green */
.submit-btn > button {
    background: var(--admin-accent) !important;
    color: white !important;
    border-radius: 20px !important;
    padding: 0.75rem 2rem !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3) !important;
}

.submit-btn > button:hover {
    background: #059669 !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4) !important;
}

/* ===== LLM EXTRACTION TAGS ===== */
.llm-tags {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}

.llm-tag {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 500;
    transition: all 0.15s ease;
}

.llm-tag:hover {
    transform: scale(1.05);
}

/* Concept tags - teal */
.tag-concept {
    background: rgba(20, 184, 166, 0.2);
    color: #0d9488;
    border: 1px solid rgba(20, 184, 166, 0.3);
}

/* Verse aspect tags - purple */
.tag-aspect {
    background: rgba(139, 92, 246, 0.2);
    color: #7c3aed;
    border: 1px solid rgba(139, 92, 246, 0.3);
}

/* People tags - red */
.tag-people {
    background: rgba(239, 68, 68, 0.2);
    color: #dc2626;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

/* Places tags - blue */
.tag-places {
    background: rgba(59, 130, 246, 0.2);
    color: #2563eb;
    border: 1px solid rgba(59, 130, 246, 0.3);
}

/* Hadith/Islamic terms tags - amber */
.tag-hadith {
    background: rgba(245, 158, 11, 0.2);
    color: #d97706;
    border: 1px solid rgba(245, 158, 11, 0.3);
}

/* ===== ROLE BADGES ===== */
.role-admin {
    background: rgba(16, 185, 129, 0.15);
    color: var(--admin-accent);
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.role-annotator {
    background: rgba(59, 130, 246, 0.15);
    color: var(--annotator-accent);
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ===== INPUT FIELDS ===== */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    background: var(--card-bg) !important;
    color: var(--text-dark) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: 6px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--annotator-accent) !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important;
}

/* ===== DROPDOWN/SELECTBOX FIX ===== */
/* Dropdown trigger button */
.stSelectbox [data-baseweb="select"] {
    background: #2d3748 !important;
    border: 1px solid #4a5568 !important;
}

.stSelectbox [data-baseweb="select"] * {
    color: #ffffff !important;
}

/* Dropdown menu popup */
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] ul,
[data-baseweb="select"] [role="listbox"] {
    background: #2d3748 !important;
}

[data-baseweb="popover"] li,
[data-baseweb="popover"] [role="option"],
[data-baseweb="select"] [role="option"] {
    color: #ffffff !important;
    background: #2d3748 !important;
}

[data-baseweb="popover"] li:hover,
[data-baseweb="popover"] [role="option"]:hover {
    background: #4a5568 !important;
}

/* Selected option highlight */
[data-baseweb="popover"] [aria-selected="true"],
[role="option"][aria-selected="true"] {
    background: #3b82f6 !important;
    color: #ffffff !important;
}

/* ===== METRICS ===== */
[data-testid="stMetric"] {
    background: var(--card-bg) !important;
    padding: 1rem !important;
    border-radius: var(--card-radius) !important;
    box-shadow: var(--card-shadow) !important;
}

[data-testid="stMetric"] label {
    color: var(--text-muted) !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--annotator-accent) !important;
    font-weight: 700 !important;
}

/* ===== CHECKBOXES ===== */
[data-testid="stCheckbox"] {
    background: transparent !important;
}

[data-testid="stCheckbox"] label span {
    color: var(--text-dark) !important;
}

/* ===== FILE UPLOADER ===== */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.05) !important;
    border: 2px dashed var(--border-dark) !important;
    border-radius: var(--card-radius) !important;
}

[data-testid="stFileUploader"]:hover {
    border-color: var(--annotator-accent) !important;
    background: rgba(59, 130, 246, 0.05) !important;
}

/* ===== PROGRESS BAR ===== */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--annotator-accent), #60a5fa) !important;
}

.stProgress > div > div {
    background: var(--border-dark) !important;
}

/* ===== PROGRESS DISPLAY SPACING ===== */
/* Ensure progress bar has proper height and spacing */
[data-testid="stProgress"] {
    margin: 8px 0 !important;
    min-height: 24px !important;
}

/* Space between progress bar and other elements in st.status */
[data-testid="stStatus"] [data-testid="stExpanderDetails"] > div {
    margin-bottom: 8px !important;
}

/* Prevent text overlap inside status containers */
[data-testid="stStatus"] p,
[data-testid="stStatus"] span {
    line-height: 1.6 !important;
    margin: 4px 0 !important;
}

/* Hide any residual progress bar percentage text (prevents overlap) */
[data-testid="stProgress"] .stProgressBarValue {
    display: none !important;
}

/* Ensure status updates don't overflow */
[data-testid="stStatus"] summary {
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}

/* ===== DIVIDERS ===== */
hr {
    border: none !important;
    height: 1px !important;
    background: var(--border-dark) !important;
    margin: 1rem 0 !important;
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg-sidebar);
}

::-webkit-scrollbar-thumb {
    background: var(--border-dark);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--annotator-accent);
}

/* ===== TOAST NOTIFICATIONS ===== */
[data-testid="stToast"] {
    background: var(--card-bg) !important;
    color: var(--text-dark) !important;
    border-left: 4px solid var(--admin-accent) !important;
    box-shadow: var(--card-shadow-hover) !important;
}

/* ===== SUCCESS/WARNING/ERROR ===== */
.stSuccess {
    background: rgba(16, 185, 129, 0.15) !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
    color: #059669 !important;
}

.stWarning {
    background: rgba(245, 158, 11, 0.15) !important;
    border: 1px solid rgba(245, 158, 11, 0.3) !important;
    color: #d97706 !important;
}

.stError {
    background: rgba(239, 68, 68, 0.15) !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
    color: #dc2626 !important;
}

/* ===== JUNK PARAGRAPH ===== */
.junk-paragraph {
    background-color: rgba(239, 68, 68, 0.1) !important;
    border-left: 4px solid #ef4444 !important;
}

/* ===== TABS ===== */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.05);
    border-radius: 8px;
    padding: 4px;
}

.stTabs [data-baseweb="tab"] {
    color: var(--text-secondary) !important;
    border-radius: 6px;
}

.stTabs [aria-selected="true"] {
    background: var(--annotator-accent) !important;
    color: white !important;
}

/* ===== MULTISELECT TAGS ===== */
.stMultiSelect [data-baseweb="tag"] {
    background: var(--annotator-accent) !important;
    color: white !important;
    border-radius: 16px !important;
}

/* ===== HEADER BANNER ===== */
.custom-header {
    background: linear-gradient(135deg, var(--annotator-accent) 0%, #1d4ed8 100%);
    color: white;
    padding: 1.5rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
}

.custom-header h1 {
    color: white !important;
    margin: 0 !important;
}

.custom-header p {
    color: rgba(255,255,255,0.9) !important;
    margin: 0.5rem 0 0 0 !important;
}

/* ===== ADMIN HEADER (green) ===== */
.admin-header {
    background: linear-gradient(135deg, var(--admin-accent) 0%, #047857 100%);
}

/* ===== WORD COUNT BADGE ===== */
.word-badge {
    background: #f1f5f9;
    color: var(--text-muted);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
}

/* ===== AUTO-DETECTED REFERENCES LAYOUT ===== */
/* Tighter alignment for reference rows */
[data-testid="stHorizontalBlock"] {
    align-items: center !important;
}

/* Checkbox vertical alignment */
[data-testid="stCheckbox"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 32px !important;
}

/* Compact delete button */
[data-testid="stHorizontalBlock"] button[kind="secondary"] {
    padding: 0.2rem 0.5rem !important;
    min-height: unset !important;
    line-height: 1 !important;
}

/* Tighter spacing for checkbox-text-delete rows */
[data-testid="stHorizontalBlock"]:has([data-testid="stCheckbox"]) {
    gap: 0.25rem !important;
}

/* Fix broken Material Icons - CSS only approach */
[data-testid="stExpanderToggleIcon"] {
    font-size: 0 !important;
    visibility: hidden !important;
    position: relative !important;
}
[data-testid="stExpanderToggleIcon"]::after {
    content: "→";
    font-size: 14px !important;
    visibility: visible !important;
    font-family: inherit !important;
}
details[open] > summary [data-testid="stExpanderToggleIcon"]::after {
    content: "↓";
}

/* Fix st.status broken Material Icons - broader approach */
/* Hide Material Icons text in st.status widgets */
[data-testid="stStatus"] [data-testid="stExpanderToggleIcon"] {
    font-size: 0 !important;
    visibility: hidden !important;
    position: relative !important;
}

[data-testid="stStatus"] [data-testid="stExpanderToggleIcon"]::after {
    content: "▼";
    font-size: 14px !important;
    visibility: visible !important;
    font-family: inherit !important;
}

/* When status is collapsed (details not open) */
[data-testid="stStatus"]:not(:has(details[open])) [data-testid="stExpanderToggleIcon"]::after {
    content: "▶";
}

/* Fallback: Universal Material Icons fix for any broken icons showing as text */
span.material-icons:not(:empty),
span.material-symbols-rounded:not(:empty) {
    font-size: 0 !important;
}

span.material-icons:not(:empty)::after,
span.material-symbols-rounded:not(:empty)::after {
    content: "▼";
    font-size: 14px !important;
    visibility: visible !important;
    font-family: inherit !important;
}

/* For collapsed states */
details:not([open]) > summary span.material-icons:not(:empty)::after,
details:not([open]) > summary span.material-symbols-rounded:not(:empty)::after {
    content: "▶";
}

</style>
""", unsafe_allow_html=True)



def init_session_state():
    """Initialize session state variables."""
    if 'paragraphs' not in st.session_state:
        st.session_state.paragraphs = []
    if 'book_title' not in st.session_state:
        st.session_state.book_title = ""
    if 'author' not in st.session_state:
        st.session_state.author = "Maulana Wahiduddin Khan"
    if 'annotator' not in st.session_state:
        st.session_state.annotator = ""
    if 'file_uploaded' not in st.session_state:
        st.session_state.file_uploaded = False
    if 'last_read_para' not in st.session_state:
        st.session_state.last_read_para = None
    if 'detected_refs' not in st.session_state:
        st.session_state.detected_refs = {}  # paragraph_id -> {'quran': [], 'hadith': [], 'footnotes': []}
    if 'document_footnotes' not in st.session_state:
        st.session_state.document_footnotes = []  # Extracted footnotes from DOCX
    if 'endnotes' not in st.session_state:
        st.session_state.endnotes = []  # Endnotes extracted from text
    # Keyword highlighting settings
    if 'highlight_keywords' not in st.session_state:
        st.session_state.highlight_keywords = True
    if 'highlight_numbers' not in st.session_state:
        st.session_state.highlight_numbers = True
    if 'highlight_years' not in st.session_state:
        st.session_state.highlight_years = True
    if 'custom_keywords' not in st.session_state:
        st.session_state.custom_keywords = DEFAULT_KEYWORDS.copy()
    # Paragraph grouping (manual merge - legacy feature)
    if 'selected_for_grouping' not in st.session_state:
        st.session_state.selected_for_grouping = set()
    # Visual grouping for LightRAG export
    if 'groups' not in st.session_state:
        st.session_state.groups = []
    if 'selected_groups' not in st.session_state:
        st.session_state.selected_groups = set()
    if 'scroll_to_group' not in st.session_state:
        st.session_state.scroll_to_group = None
    # PDF support (for page number extraction only)
    if 'pdf_pages' not in st.session_state:
        st.session_state.pdf_pages = []
    if 'pdf_loaded' not in st.session_state:
        st.session_state.pdf_loaded = False
    # Book status for workflow
    if 'book_status' not in st.session_state:
        st.session_state.book_status = 'pending'
    # User info (set by auth)
    if 'current_user' not in st.session_state:
        st.session_state.current_user = 'guest'
    if 'user_role' not in st.session_state:
        st.session_state.user_role = 'annotator'
    # Auto-save tracking
    if 'last_save_time' not in st.session_state:
        st.session_state.last_save_time = datetime.now()
    if 'has_unsaved_changes' not in st.session_state:
        st.session_state.has_unsaved_changes = False
    # Remember last worked paragraph for resume
    if 'last_worked_para' not in st.session_state:
        st.session_state.last_worked_para = None
    # View mode for group visualization
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = 'Paragraph View'
    # Scroll position for navigation
    if 'scroll_to_para' not in st.session_state:
        st.session_state.scroll_to_para = None
    # Book library
    if 'current_book_folder' not in st.session_state:
        st.session_state.current_book_folder = None
    if 'book_slug' not in st.session_state:
        st.session_state.book_slug = ''
    # Approval workflow
    if 'selected_for_approval' not in st.session_state:
        st.session_state.selected_for_approval = set()
    # Auto-detect toggle
    if 'auto_detect_enabled' not in st.session_state:
        st.session_state.auto_detect_enabled = True


def mark_activity(para_id=None):
    """Mark that user made changes (for auto-save tracking)."""
    st.session_state.has_unsaved_changes = True
    # Remember last worked paragraph
    if para_id is not None:
        st.session_state.last_worked_para = para_id


def check_auto_save():
    """Auto-save every 30 seconds if there are unsaved changes."""
    if not st.session_state.get('has_unsaved_changes'):
        return

    now = datetime.now()
    last_save = st.session_state.get('last_save_time', now)
    seconds_since_save = (now - last_save).total_seconds()

    if seconds_since_save >= 30:
        save_progress()
        st.session_state.last_save_time = now
        st.session_state.has_unsaved_changes = False
        st.toast("Auto-saved!", icon="💾")


def count_tokens(text: str) -> dict:
    """Wrapper for helpers.count_tokens()."""
    return helpers_count_tokens(text)


def save_progress():
    """Auto-save current work to disk for resume later. Now uses db module."""
    button_logger.info(f"[SAVE] starting book={st.session_state.get('book_title', 'unknown')}")

    if not st.session_state.book_title or not st.session_state.paragraphs:
        button_logger.warning(f"[SAVE] skipped - no book loaded")
        return

    # Get book folder and user
    book_folder = st.session_state.get('current_book_folder')
    if not book_folder:
        # Fallback for manual uploads before folder is set
        book_folder = slugify(st.session_state.book_title, max_length=50)

    user = st.session_state.get('current_user', 'guest')

    button_logger.info(f"[SAVE] folder={book_folder} user={user} title={st.session_state.get('book_title', '')[:30]}")

    # Prepare data
    data = {
        'paragraphs': st.session_state.paragraphs,
        'groups': st.session_state.get('groups', []),
        'book_title': st.session_state.book_title,
        'author': st.session_state.author,
        'annotator': st.session_state.annotator,
        'pdf_loaded': st.session_state.pdf_loaded,
        'pdf_pages': st.session_state.get('pdf_pages', []),
        'book_status': st.session_state.get('book_status', 'pending'),
        'last_worked_para': st.session_state.get('last_worked_para')
    }

    # Save progress using db module
    if db.save_progress(data, book_folder, user):
        # Create version snapshot
        db.create_version(book_folder, user, data)

        # Update auto-save tracking
        st.session_state.last_save_time = datetime.now()
        st.session_state.has_unsaved_changes = False
        button_logger.info(f"[SAVE] success via db module")
    else:
        button_logger.error(f"[SAVE] failed via db module")


def humanize_time_ago(dt):
    """Wrapper for helpers.humanize_time_ago()."""
    return helpers_humanize_time_ago(dt)


def load_last_read_position():
    """Load the user's last reading position for the current book."""
    book_folder = st.session_state.get('current_book_folder')
    user = st.session_state.get('current_user', 'guest')
    if book_folder:
        try:
            filepath = os.path.join(book_folder, f'last_read_{user}.json')
            if os.path.exists(filepath):
                with open(filepath) as f:
                    data = json.load(f)
                    return data.get('para_id')
        except Exception:
            pass
    return None


def get_saved_books():
    """Wrapper for db.list_saved_books()."""
    current_user = st.session_state.get('current_user', 'guest')
    user_role = st.session_state.get('user_role', 'annotator')
    return db.list_saved_books(current_user, user_role)


def load_saved_book(fpath):
    """Load a saved book for resume."""
    with open(fpath) as f:
        data = json.load(f)
    st.session_state.paragraphs = data.get('paragraphs', [])
    st.session_state.groups = data.get('groups', [])
    st.session_state.book_title = data.get('book_title', '')
    st.session_state.author = data.get('author', '')
    st.session_state.annotator = data.get('annotator', '')
    st.session_state.pdf_loaded = data.get('pdf_loaded', False)
    st.session_state.pdf_pages = data.get('pdf_pages', [])
    st.session_state.book_status = data.get('book_status', 'pending')
    st.session_state.file_uploaded = True
    st.session_state.last_worked_para = data.get('last_worked_para')

    # Rebuild detected_refs from paragraphs
    st.session_state.detected_refs = {}
    for para in st.session_state.paragraphs:
        para_id = para['id']
        st.session_state.detected_refs[para_id] = {
            'quran': para.get('quran_refs', []),
            'hadith': para.get('hadith_refs', []),
            'year': para.get('year_refs', []),
            'footnotes': para.get('footnote_refs', [])
        }

    # Rebuild paragraph group_id references if groups exist
    if st.session_state.groups:
        for group in st.session_state.groups:
            for para_id in group.get('para_ids', []):
                for para in st.session_state.paragraphs:
                    if para['id'] == para_id:
                        para['group_id'] = group['group_id']
                        break
    else:
        # Auto-generate groups on book load if they don't exist
        generate_groups()


# ============= BOOK LIBRARY FUNCTIONS =============

# DATA_DIR and BOOKS_DIR now imported from config.py (handles environment detection)

def load_meta(book_folder):
    """Wrapper for db.load_meta()."""
    return db.load_meta(book_folder)

def save_meta(book_folder, meta):
    """Wrapper for db.save_meta()."""
    return db.save_meta(book_folder, meta)

def get_library_books():
    """Wrapper for db.get_library_books()."""
    return db.get_library_books()

def can_lock_book(book_folder, username):
    """Wrapper for db.can_lock_book()."""
    return db.can_lock_book(book_folder, username)

def lock_book(book_folder, username):
    """Wrapper for db.lock_book()."""
    return db.lock_book(book_folder, username)

def release_lock(book_folder):
    """Wrapper for db.release_lock()."""
    return db.release_lock(book_folder)

def load_book_from_library(book_folder):
    """Load a book from the library for annotation."""
    start_time = time.time()  # Track load time for logging

    folder_path = os.path.join(BOOKS_DIR, book_folder)
    docx_path = os.path.join(folder_path, 'document.docx')
    pdf_path = os.path.join(folder_path, 'document.pdf')
    meta = load_meta(book_folder)

    # Check for existing progress in data folder
    username = st.session_state.get('current_user', 'guest')
    slug = book_folder.replace(' ', '_').lower()
    progress_file = os.path.join(DATA_DIR, f"{slug}_{username}_progress.json")

    # Debug logging
    button_logger.info(f"[LOAD] folder={book_folder} slug={slug} exists={os.path.exists(progress_file)}")

    if os.path.exists(progress_file):
        # Resume from saved progress
        load_saved_book(progress_file)
    else:
        # Start fresh from DOCX
        if os.path.exists(docx_path):
            with open(docx_path, 'rb') as f:
                from io import BytesIO
                docx_bytes = BytesIO(f.read())
                docx_bytes.name = 'document.docx'
                process_uploaded_file(docx_bytes)
            st.session_state.book_title = meta.get('title', book_folder)

    # Skip PDF processing entirely if already loaded from saved progress
    # Double-safety check: both pdf_loaded flag AND paragraph page_info presence
    skipped_pdf = False
    if not st.session_state.get('pdf_loaded', False):
        # Also check if paragraphs already have page_info (double safety)
        already_matched = any(p.get('page_info') for p in st.session_state.paragraphs)

        if not already_matched and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                from io import BytesIO
                pdf_bytes = BytesIO(f.read())
                pdf_bytes.name = 'document.pdf'
                process_pdf_file(pdf_bytes)
        else:
            skipped_pdf = True
    else:
        skipped_pdf = True

    # Store which book we're working on
    st.session_state.current_book_folder = book_folder

    # Load last read position and set up scroll
    last_read = load_last_read_position()
    if last_read:
        st.session_state.last_read_para = last_read
        st.session_state.scroll_to_para = last_read

    # Lock the book (only for annotators, not admin)
    user_role = st.session_state.get('user_role', 'annotator')
    if user_role == 'annotator':
        lock_book(book_folder, username)

    save_progress()

    # Save book to query params for navigation persistence
    try:
        st.query_params["book"] = book_folder
        logger.info(f"[NAV_SAVE] book={book_folder}")
    except AttributeError:
        # Fallback for older Streamlit versions
        st.experimental_set_query_params(book=book_folder)
        logger.info(f"[NAV_SAVE] book={book_folder}")

    # Log book loading operation
    load_time_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[LOAD_BOOK] book={slug}, skipped_pdf={skipped_pdf}, load_time={load_time_ms}ms")

def submit_book_for_review():
    """Submit current book for reviewer approval."""
    book_folder = st.session_state.get('current_book_folder')
    if book_folder:
        meta = load_meta(book_folder)
        meta['status'] = 'submitted'
        meta['annotated_by'] = st.session_state.get('current_user')
        meta['submitted_at'] = datetime.now().isoformat()
        meta['progress'] = 100
        release_lock(book_folder)
        save_meta(book_folder, meta)
        st.session_state.book_status = 'annotated'
        save_progress()

def approve_book(book_folder):
    """Approve a book (admin action)."""
    meta = load_meta(book_folder)
    meta['status'] = 'approved'
    meta['approved_by'] = st.session_state.get('current_user')
    meta['approved_at'] = datetime.now().isoformat()
    save_meta(book_folder, meta)

def delete_book(book_folder):
    """Delete a book from library (admin action)."""
    import shutil
    folder_path = os.path.join(BOOKS_DIR, book_folder)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        return True
    return False

# ============= END LIBRARY FUNCTIONS =============


def detect_junk_paragraphs(paragraphs):
    """Auto-detect cover, index, copyright, etc. Mark as potential_delete."""
    import re

    junk_patterns = [
        r'^table of contents?$',
        r'^contents?$',
        r'^index$',
        r'^\d+$',  # Just a number (page number)
        r'^copyright',
        r'all rights reserved',
        r'^isbn',
        r'^published by',
        r'^first published',
        r'^printed in',
        r'^cover design',
        r'^acknowledgements?$',
        r'^about the author$',
        r'^other books by',
        r'^also available',
        r'www\.',
        r'\.com$',
        r'\.org$',
    ]

    total = len(paragraphs)

    for i, para in enumerate(paragraphs):
        text = para.get('text', '').strip().lower()

        # Skip if already reviewed or deleted
        if para.get('reviewed') or para.get('deleted'):
            continue

        is_junk = False
        reason = None

        # First 5 paragraphs (cover, title page, copyright)
        if i < 5:
            if len(text) < 100:  # Short paragraphs at start
                is_junk = True
                reason = "front_matter"

        # Last 3 paragraphs
        if i >= total - 3:
            if len(text) < 100:
                is_junk = True
                reason = "back_matter"

        # Pattern matching
        for pattern in junk_patterns:
            if re.search(pattern, text):
                is_junk = True
                reason = "pattern_match"
                break

        # Very short paragraphs that are likely page numbers or headers
        if len(text) < 20 and not any(c.isalpha() for c in text):
            is_junk = True
            reason = "page_number"

        if is_junk:
            para['potential_delete'] = True
            para['delete_reason'] = reason


def process_pdf_file(uploaded_pdf):
    """Process PDF to extract page numbers for paragraphs."""
    if not PDF_SUPPORT:
        st.warning("PDF support not available.")
        return

    with st.status("📄 Processing PDF...", expanded=True) as status:
        try:
            # Phase 1: Extract pages
            status.update(label="Reading PDF file...")
            pdf_content = BytesIO(uploaded_pdf.getvalue())
            st.session_state.pdf_pages = extract_pdf_pages(pdf_content)
            st.session_state.pdf_loaded = True

            page_count = len(st.session_state.pdf_pages)
            para_count = len(st.session_state.paragraphs)

            # Match paragraphs to pages if DOCX already loaded
            if st.session_state.paragraphs:
                # Check if paragraphs already have page_info (from previous matching or saved progress)
                already_matched = any(p.get('page_info') for p in st.session_state.paragraphs)

                if already_matched:
                    # Count existing matches
                    exact = sum(1 for p in st.session_state.paragraphs
                               if p.get('page_info', {}).get('match_type') == 'exact')
                    fuzzy = sum(1 for p in st.session_state.paragraphs
                               if p.get('page_info', {}).get('match_type') == 'fuzzy')
                    estimated = sum(1 for p in st.session_state.paragraphs
                                   if p.get('page_info', {}).get('match_type') == 'estimated')

                    status.update(label=f"✅ Using saved matches: {exact} exact, {fuzzy} fuzzy, {estimated} estimated", state="complete")
                else:
                    # Run matching (first time only)
                    # Phase 2: Match paragraphs with progress tracking
                    progress_bar = st.progress(0)
                    start_time = time.time()

                    # Track stats in real-time
                    stats = {'exact': 0, 'fuzzy': 0, 'estimated': 0}

                    def update_progress(current, total):
                        # Update progress bar
                        progress_bar.progress(current / total)

                        # Calculate elapsed time and estimate remaining
                        elapsed = time.time() - start_time
                        rate = current / elapsed if elapsed > 0 else 0
                        remaining_secs = int((total - current) / rate) if rate > 0 else 0

                        # Count current match stats (from paragraphs processed so far)
                        stats['exact'] = sum(1 for p in st.session_state.paragraphs[:current]
                                            if p.get('page_info', {}).get('match_type') == 'exact')
                        stats['fuzzy'] = sum(1 for p in st.session_state.paragraphs[:current]
                                            if p.get('page_info', {}).get('match_type') == 'fuzzy')
                        stats['estimated'] = sum(1 for p in st.session_state.paragraphs[:current]
                                                if p.get('page_info', {}).get('match_type') == 'estimated')

                        # Update status label with ALL info (single source of truth)
                        pct = int(100 * current / total)
                        status.update(
                            label=f"📊 Matching: {pct}% ({current}/{total}) | "
                                  f"✓ {stats['exact']} exact, {stats['fuzzy']} fuzzy, {stats['estimated']} estimated | "
                                  f"⏱️ {remaining_secs}s remaining"
                        )

                    st.session_state.paragraphs = match_all_paragraphs_to_pages(
                        st.session_state.paragraphs,
                        st.session_state.pdf_pages,
                        progress_callback=update_progress
                    )

                    progress_bar.empty()

                    # Count final match types
                    exact = sum(1 for p in st.session_state.paragraphs
                               if p.get('page_info', {}).get('match_type') == 'exact')
                    fuzzy = sum(1 for p in st.session_state.paragraphs
                               if p.get('page_info', {}).get('match_type') == 'fuzzy')
                    estimated = sum(1 for p in st.session_state.paragraphs
                                   if p.get('page_info', {}).get('match_type') == 'estimated')

                    status.update(label=f"✅ Matched! {exact} exact, {fuzzy} fuzzy, {estimated} estimated", state="complete")
            else:
                status.update(label=f"✅ PDF loaded ({page_count} pages). Upload DOCX to match paragraphs.", state="complete")

        except Exception as e:
            status.update(label=f"❌ Failed: {str(e)}", state="error")
            st.session_state.pdf_pages = []
            st.session_state.pdf_loaded = False


def process_uploaded_file(uploaded_file):
    """Process the uploaded DOCX file."""
    with st.status("📖 Processing document...", expanded=True) as status:
        file_bytes = uploaded_file.getvalue()
        file_content = BytesIO(file_bytes)

        # Phase 1: Extract paragraphs
        status.update(label="Extracting paragraphs...")
        paragraphs = cached_extract_paragraphs(file_bytes)

        # Get metadata
        file_content.seek(0)
        metadata = get_document_metadata(file_content)

        # Phase 2: Analyze footnotes
        status.update(label="Analyzing footnotes...")
        file_content.seek(0)
        docx_footnotes = extract_docx_footnotes(file_content)
        st.session_state.document_footnotes = docx_footnotes

        # Extract endnotes from text (paragraphs that are [1] ... style)
        paragraphs, endnotes = extract_endnotes_from_text(paragraphs)
        st.session_state.endnotes = endnotes

        # Combine all footnotes for linking
        all_footnotes = docx_footnotes + endnotes

        # Phase 3: Detect references
        para_count = len(paragraphs)
        status.update(label=f"🔍 Detecting references in {para_count} paragraphs...")

        # Show progress bar only if we have many paragraphs
        if para_count > 50:
            progress_bar = st.progress(0)
            start_time = time.time()
        else:
            progress_bar = None

        # Auto-detect references for each paragraph (cached)
        # Quran/Hadith detection controlled by toggle (default: enabled)
        auto_detect_enabled = st.session_state.get('auto_detect_enabled', True)
        detected_refs = {}
        for i, para in enumerate(paragraphs):
            para_id = para['id']

            # Always detect years and footnotes
            year_refs = find_year_positions(para['text'])
            footnote_markers = detect_footnote_markers(para['text'])

            # Conditionally detect Quran/Hadith based on toggle
            if auto_detect_enabled:
                quran_refs = cached_detect_quran_refs(para['text'])
                hadith_refs = cached_detect_hadith_refs(para['text'])
            else:
                quran_refs = []
                hadith_refs = []

            # Link footnote markers to footnote content
            footnote_markers = link_markers_to_footnotes(footnote_markers, all_footnotes)

            # Store detected refs
            detected_refs[para_id] = {
                'quran': quran_refs,
                'hadith': hadith_refs,
                'year': year_refs,
                'footnotes': footnote_markers
            }

            # Initialize paragraph refs from auto-detection
            para['quran_refs'] = [
                {
                    'surah': ref['surah'],
                    'ayah_start': ref['ayah_start'],
                    'ayah_end': ref.get('ayah_end'),
                    'quoted_text': ref.get('quoted_text', ''),
                    'detection': 'auto',
                    'verified': False
                }
                for ref in quran_refs
            ]
            para['hadith_refs'] = [
                {
                    'collection': ref.get('collection'),
                    'number': ref.get('number'),
                    'narrator': ref.get('narrator'),
                    'detection': 'auto',
                    'verified': False
                }
                for ref in hadith_refs
            ]
            para['year_refs'] = [
                {
                    'text': para['text'][ref[0]:ref[1]],
                    'start_pos': ref[0],
                    'end_pos': ref[1],
                    'detection': 'auto',
                    'verified': False
                }
                for ref in year_refs
            ]
            para['footnote_refs'] = [
                {
                    'marker': ref['marker'],
                    'number': ref['number'],
                    'linked_footnote': ref.get('linked_footnote'),
                    'footnote_type': ref.get('footnote_type'),
                    'detection': 'auto',
                    'verified': False
                }
                for ref in footnote_markers
            ]

            # Update progress every 10 paragraphs
            if progress_bar and i % 10 == 0:
                progress_bar.progress((i + 1) / para_count)

                # Calculate time estimate
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining_secs = int((para_count - i - 1) / rate) if rate > 0 else 0

                pct = int(100 * (i + 1) / para_count)
                status.update(
                    label=f"🔍 Analyzing: {pct}% ({i + 1}/{para_count}) | "
                          f"⏱️ {remaining_secs}s remaining"
                )

        # Clean up progress indicators
        if progress_bar:
            progress_bar.empty()

        st.session_state.paragraphs = paragraphs
        st.session_state.detected_refs = detected_refs
        st.session_state.file_uploaded = True

        if metadata.get('title'):
            st.session_state.book_title = metadata['title']
        if metadata.get('author'):
            st.session_state.author = metadata['author']

        # Phase 4: Match paragraphs to PDF pages if PDF already loaded
        if PDF_SUPPORT and st.session_state.pdf_pages:
            try:
                page_count = len(st.session_state.pdf_pages)

                # Check if we need to match (new upload without page_info)
                needs_matching = not any(p.get('page_info') for p in st.session_state.paragraphs)

                if needs_matching:
                    status.update(label=f"Matching {para_count} paragraphs to {page_count} pages...")

                    progress_bar = st.progress(0)
                    start_time = time.time()

                    # Track stats in real-time
                    stats = {'exact': 0, 'fuzzy': 0, 'estimated': 0}

                    def update_progress(current, total):
                        # Update progress bar
                        progress_bar.progress(current / total)

                        # Calculate elapsed time and estimate remaining
                        elapsed = time.time() - start_time
                        rate = current / elapsed if elapsed > 0 else 0
                        remaining_secs = int((total - current) / rate) if rate > 0 else 0

                        # Count current match stats (from paragraphs processed so far)
                        stats['exact'] = sum(1 for p in st.session_state.paragraphs[:current]
                                            if p.get('page_info', {}).get('match_type') == 'exact')
                        stats['fuzzy'] = sum(1 for p in st.session_state.paragraphs[:current]
                                            if p.get('page_info', {}).get('match_type') == 'fuzzy')
                        stats['estimated'] = sum(1 for p in st.session_state.paragraphs[:current]
                                                if p.get('page_info', {}).get('match_type') == 'estimated')

                        # Update status label with ALL info (single source of truth)
                        pct = int(100 * current / total)
                        status.update(
                            label=f"📊 Matching: {pct}% ({current}/{total}) | "
                                  f"✓ {stats['exact']} exact, {stats['fuzzy']} fuzzy, {stats['estimated']} estimated | "
                                  f"⏱️ {remaining_secs}s remaining"
                        )

                    st.session_state.paragraphs = match_all_paragraphs_to_pages(
                        st.session_state.paragraphs,
                        st.session_state.pdf_pages,
                        progress_callback=update_progress
                    )

                    progress_bar.empty()

                    # Count match types
                    exact = sum(1 for p in st.session_state.paragraphs
                               if p.get('page_info', {}).get('match_type') == 'exact')
                    fuzzy = sum(1 for p in st.session_state.paragraphs
                               if p.get('page_info', {}).get('match_type') == 'fuzzy')
                    estimated = sum(1 for p in st.session_state.paragraphs
                                   if p.get('page_info', {}).get('match_type') == 'estimated')

                    status.update(label=f"✅ Matched to PDF! {exact} exact, {fuzzy} fuzzy, {estimated} estimated", state="complete")
                else:
                    status.update(label="✅ Using saved PDF matches", state="complete")
            except Exception as e:
                st.error(f"❌ Page matching failed: {str(e)}")

        # Phase 5: Detect junk paragraphs
        if not (PDF_SUPPORT and st.session_state.pdf_pages):
            # Only show this status if we didn't already complete with PDF matching
            status.update(label="Detecting junk paragraphs...")

        detect_junk_paragraphs(st.session_state.paragraphs)

        # Final status update if no PDF was matched
        if not (PDF_SUPPORT and st.session_state.pdf_pages):
            status.update(label=f"✅ Document processed! {para_count} paragraphs", state="complete")


def get_progress():
    """Calculate review progress."""
    total = len(st.session_state.paragraphs)
    reviewed = sum(1 for p in st.session_state.paragraphs if p.get('reviewed', False))
    return reviewed, total


def render_junk_approval():
    """Render bulk approval panel for detected junk paragraphs."""
    junk = [p for p in st.session_state.paragraphs
            if p.get('potential_delete') and not p.get('deleted')]
    deleted = [p for p in st.session_state.paragraphs if p.get('deleted')]

    if not junk and not deleted:
        return

    with st.expander(f"🗑️ Deletion Queue: {len(junk)} pending, {len(deleted)} deleted", expanded=len(junk) > 0):

        # Pending deletions
        if junk:
            st.markdown("### Pending Deletions")

            # Action buttons at top
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                if st.button("🗑️ DELETE ALL", type="primary", key="delete_all_junk"):
                    for p in junk:
                        p['deleted'] = True
                        p['potential_delete'] = False
                        st.session_state[f"pdel_{p['id']}"] = False
                    save_progress()
                    st.rerun()
            with col2:
                if st.button("❎ Clear All", key="clear_all_junk"):
                    for p in junk:
                        p['potential_delete'] = False
                        st.session_state[f"pdel_{p['id']}"] = False
                    save_progress()
                    st.rerun()
            with col3:
                st.caption(f"{len(junk)} items")

            st.divider()

            # List with clear button per item (no checkbox, controlled via paragraph DEL only)
            for p in junk:
                page_num = p.get('page_info', {}).get('page_number', '?')
                reason = p.get('delete_reason', 'auto')
                text_preview = p['text'][:60].replace('\n', ' ')

                col_text, col_reason, col_action = st.columns([3.5, 1, 0.7])
                with col_text:
                    st.markdown(
                        f'<a href="#para-{p["id"]}" style="text-decoration:none;color:#6ee7b7;'
                        f'font-size:0.9em;display:block;padding:4px 0;">'
                        f'#{p["id"]} | p.{page_num} | {text_preview}...</a>',
                        unsafe_allow_html=True
                    )
                with col_reason:
                    st.caption(reason)
                with col_action:
                    # Clear button to remove from queue
                    if st.button("❌", key=f"clear_{p['id']}", help="Remove from queue"):
                        p['potential_delete'] = False
                        st.session_state[f"pdel_{p['id']}"] = False
                        save_progress()
                        st.rerun()

        # Deleted items
        if deleted:
            st.divider()
            st.markdown(f"### Deleted ({len(deleted)})")

            if st.button("↩️ UNDO ALL DELETIONS", key="undo_all"):
                for p in st.session_state.paragraphs:
                    if p.get('deleted'):
                        p['deleted'] = False
                st.rerun()

            for p in deleted[:5]:
                page_num = p.get('page_info', {}).get('page_number', '?')
                st.caption(f"p.{page_num} | #{p['id']} | {p['text'][:40]}...")

            if len(deleted) > 5:
                st.caption(f"...and {len(deleted) - 5} more")


def generate_slug(title: str) -> str:
    """Generate a URL-friendly slug from title."""
    import re
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def estimate_tokens(text):
    """Wrapper for helpers.estimate_tokens()."""
    return helpers_estimate_tokens(text)


def create_groups_for_chapter(paragraphs, chapter_title, group_counter_start):
    """
    Create smart groups within a chapter.

    Rules:
    - Subheading starts new group
    - But merge subheading sections if combined < 800 tokens
    - Target: 512-800 tokens per group
    - Max: 1000 tokens
    - Never cross chapter boundary (handled by caller)
    """
    if not paragraphs:
        return [], group_counter_start

    groups = []
    current_group = {
        'para_ids': [],
        'texts': [],
        'token_count': 0,
        'page_start': None,
        'page_end': None
    }
    group_counter = group_counter_start

    def flush_group():
        """Flush current group to groups list."""
        nonlocal group_counter, current_group
        if current_group['para_ids']:
            group_counter += 1
            groups.append({
                'group_id': f"g_{group_counter:03d}",
                'para_ids': current_group['para_ids'],
                'combined_text': '\n\n'.join(current_group['texts']),
                'token_count': current_group['token_count'],
                'chapter': chapter_title,
                'page_start': current_group['page_start'],
                'page_end': current_group['page_end']
            })
        current_group = {
            'para_ids': [], 'texts': [], 'token_count': 0,
            'page_start': None, 'page_end': None
        }

    def add_para_to_group(para):
        """Add a paragraph to current group."""
        para_id = f"p_{para['id']:03d}"
        current_group['para_ids'].append(para_id)
        current_group['texts'].append(para.get('text', ''))
        current_group['token_count'] += estimate_tokens(para.get('text', ''))

        page_info = para.get('page_info', {})
        page_num = page_info.get('page_number')
        if page_num:
            if current_group['page_start'] is None:
                current_group['page_start'] = page_num
            current_group['page_end'] = page_num

    for para in paragraphs:
        # Skip empty paragraphs
        text = para.get('text', '').strip()
        if not text:
            continue

        para_tokens = estimate_tokens(text)
        is_subheading = para.get('type') == 'subheading' or para.get('is_subheading')

        # Subheading with existing content >= 512 tokens: start new group
        if is_subheading and current_group['token_count'] >= 512:
            flush_group()

        # Single para > 800 tokens: isolate it
        if para_tokens > 800:
            flush_group()
            add_para_to_group(para)
            flush_group()
            continue

        # Would exceed 1000 tokens? Flush first
        if current_group['token_count'] + para_tokens > 1000:
            flush_group()

        # Would exceed 800 and current is already substantial (>512)? Flush first
        if current_group['token_count'] >= 512 and current_group['token_count'] + para_tokens > 800:
            flush_group()

        add_para_to_group(para)

    # Flush final group
    flush_group()

    return groups, group_counter


# ============= GROUP VISUALIZATION HELPER FUNCTIONS =============

def find_paragraph(para_id: int) -> dict:
    """Find paragraph by numeric ID."""
    for p in st.session_state.paragraphs:
        if p['id'] == para_id:
            return p
    return None


def find_paragraph_index(para_id: int) -> int:
    """Find paragraph array index by numeric ID."""
    for i, p in enumerate(st.session_state.paragraphs):
        if p['id'] == para_id:
            return i
    return -1


def find_group(group_id: str) -> dict:
    """Find group by group_id."""
    for g in st.session_state.groups:
        if g['group_id'] == group_id:
            return g
    return None


def recalculate_group_stats(group: dict):
    """Recalculate token count, page range for group."""
    total_tokens = 0
    page_start = None
    page_end = None

    for para_id in group['para_ids']:
        para = find_paragraph(para_id)
        if para and not para.get('deleted'):
            total_tokens += estimate_tokens(para.get('text', ''))
            page_num = para.get('page_info', {}).get('page_number')
            if page_num:
                if page_start is None or page_num < page_start:
                    page_start = page_num
                if page_end is None or page_num > page_end:
                    page_end = page_num

    group['token_count'] = total_tokens
    group['page_start'] = page_start
    group['page_end'] = page_end


def generate_next_group_id() -> str:
    """Generate next available group ID."""
    if not st.session_state.groups:
        return "g_001"
    existing_ids = [g['group_id'] for g in st.session_state.groups]
    counter = 1
    while f"g_{counter:03d}" in existing_ids:
        counter += 1
    return f"g_{counter:03d}"


def generate_groups():
    """Generate groups from current paragraphs using smart algorithm."""
    # Get active paragraphs (not deleted, not manually merged, not headings)
    active_paras = [p for p in st.session_state.paragraphs
                    if not p.get('deleted')
                    and not p.get('grouped_into')
                    and p.get('type') != 'chapter_heading']

    if not active_paras:
        st.session_state.groups = []
        return

    # Use existing smart grouping algorithm
    groups, _ = create_groups_for_chapter(active_paras, "Main", 0)

    # Convert para_ids from "p_001" format to numeric
    for group in groups:
        group['para_ids'] = [int(pid.split('_')[1]) for pid in group['para_ids']]
        group['collapsed'] = False  # Add UI state

    st.session_state.groups = groups

    # Update paragraph group_id references
    for group in groups:
        for para_id in group['para_ids']:
            para = find_paragraph(para_id)
            if para:
                para['group_id'] = group['group_id']

    mark_activity()


def cleanup_empty_groups():
    """Remove groups with no paragraphs."""
    st.session_state.groups = [g for g in st.session_state.groups if g['para_ids']]


def get_group_validation_status(group):
    """Return 'optimal', 'acceptable', or 'warning'."""
    tokens = group['token_count']
    if 512 <= tokens <= 800:
        return 'optimal'
    elif 200 <= tokens < 512 or 800 < tokens <= 1000:
        return 'acceptable'
    else:
        return 'warning'


# ============= GROUP OPERATIONS =============

def move_paragraph_to_group(para_id: int, target_group_id: str):
    """Move paragraph from current group to target group."""
    para = find_paragraph(para_id)
    if not para:
        return

    old_group_id = para.get('group_id')

    # Remove from old group
    if old_group_id:
        old_group = find_group(old_group_id)
        if old_group and para_id in old_group['para_ids']:
            old_group['para_ids'].remove(para_id)
            recalculate_group_stats(old_group)

    # Add to new group
    new_group = find_group(target_group_id)
    if new_group:
        new_group['para_ids'].append(para_id)
        para['group_id'] = target_group_id
        recalculate_group_stats(new_group)

    cleanup_empty_groups()
    mark_activity()


def merge_groups(group_id_1: str, group_id_2: str):
    """Merge two groups into one."""
    g1 = find_group(group_id_1)
    g2 = find_group(group_id_2)

    if not g1 or not g2:
        return

    # Combine para_ids (maintain order)
    g1['para_ids'].extend(g2['para_ids'])

    # Update paragraphs to point to g1
    for para_id in g2['para_ids']:
        para = find_paragraph(para_id)
        if para:
            para['group_id'] = group_id_1

    # Recalculate stats
    recalculate_group_stats(g1)

    # Remove g2
    st.session_state.groups.remove(g2)

    mark_activity()


def split_group_at_paragraph(para_id: int):
    """Split group into two at specified paragraph."""
    para = find_paragraph(para_id)
    if not para or not para.get('group_id'):
        return

    old_group = find_group(para['group_id'])
    if not old_group:
        return

    # Find split index
    try:
        split_idx = old_group['para_ids'].index(para_id)
    except ValueError:
        return

    if split_idx == 0:
        st.error("Cannot split at first paragraph")
        return

    # Create new group with paragraphs after split point
    new_group_id = generate_next_group_id()
    new_group = {
        'group_id': new_group_id,
        'para_ids': old_group['para_ids'][split_idx:],
        'token_count': 0,
        'page_start': None,
        'page_end': None,
        'chapter': old_group.get('chapter', 'Main'),
        'collapsed': False
    }

    # Update old group
    old_group['para_ids'] = old_group['para_ids'][:split_idx]

    # Update paragraph references
    for pid in new_group['para_ids']:
        p = find_paragraph(pid)
        if p:
            p['group_id'] = new_group_id

    # Recalculate stats
    recalculate_group_stats(old_group)
    recalculate_group_stats(new_group)

    # Add new group
    st.session_state.groups.append(new_group)

    mark_activity()


def render_group_dashboard():
    """Render world-class group visualization dashboard with Material Design."""
    if not st.session_state.get('groups'):
        st.info("📦 No groups generated yet. Click 'Generate Groups' in the sidebar.")
        return

    # Custom CSS for Material Design cards
    st.markdown("""
    <style>
    .group-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 5px solid #3b82f6;
        transition: all 0.3s ease;
    }
    .group-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        transform: translateY(-2px);
    }
    .group-card.optimal { border-left-color: #22c55e; }
    .group-card.acceptable { border-left-color: #f59e0b; }
    .group-card.warning { border-left-color: #ef4444; }
    .group-card.quran-rich { background: linear-gradient(135deg, #f0fdf4 0%, white 100%); }
    .group-card.hadith-rich { background: linear-gradient(135deg, #eff6ff 0%, white 100%); }
    .group-card.concept-rich { background: linear-gradient(135deg, #fef3c7 0%, white 100%); }
    .stat-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85em;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 4px;
    }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-blue { background: #dbeafe; color: #1e40af; }
    .badge-orange { background: #fed7aa; color: #9a3412; }
    .badge-purple { background: #e9d5ff; color: #6b21a8; }
    .badge-gray { background: #f1f5f9; color: #475569; }
    .stat-card {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        padding: 24px;
        border-radius: 16px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }
    .stat-number {
        font-size: 2.5em;
        font-weight: 700;
        margin: 0;
        line-height: 1;
    }
    .stat-label {
        font-size: 0.9em;
        opacity: 0.9;
        margin-top: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    groups = st.session_state.groups

    # === STATS DASHBOARD ===
    st.markdown("### 📊 Group Analytics Dashboard")

    total_groups = len(groups)
    avg_tokens = sum(g['token_count'] for g in groups) / total_groups if total_groups > 0 else 0
    optimal_count = sum(1 for g in groups if get_group_validation_status(g) == 'optimal')
    acceptable_count = sum(1 for g in groups if get_group_validation_status(g) == 'acceptable')
    warning_count = sum(1 for g in groups if get_group_validation_status(g) == 'warning')

    # Count reference types across all groups
    total_quran = 0
    total_hadith = 0
    total_concepts = 0

    for g in groups:
        for para_id in g['para_ids']:
            para = find_paragraph(para_id)
            if para and not para.get('deleted'):
                total_quran += len(para.get('quran_refs', []))
                total_hadith += len(para.get('hadith_refs', []))
                total_concepts += len(para.get('concepts', []))

    # Top row: Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);">
            <div class="stat-number">{total_groups}</div>
            <div class="stat-label">Total Groups</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);">
            <div class="stat-number">{optimal_count}</div>
            <div class="stat-label">Optimal</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">
            <div class="stat-number">{acceptable_count}</div>
            <div class="stat-label">Acceptable</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">
            <div class="stat-number">{warning_count}</div>
            <div class="stat-label">Needs Review</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="stat-card" style="background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);">
            <div class="stat-number">{int(avg_tokens)}</div>
            <div class="stat-label">Avg Tokens</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Second row: Content metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🟢 Quran References", total_quran)
    with col2:
        st.metric("🔵 Hadith References", total_hadith)
    with col3:
        st.metric("🟡 Concepts Tagged", total_concepts)

    st.markdown("---")

    # === FILTERS & SORT ===
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        filter_status = st.selectbox(
            "Filter by Status",
            ["All", "Optimal (512-800t)", "Acceptable", "Needs Review"],
            key="group_filter_status"
        )

    with col2:
        sort_by = st.selectbox(
            "Sort By",
            ["Group ID", "Token Count (High→Low)", "Token Count (Low→High)", "Paragraph Count"],
            key="group_sort"
        )

    with col3:
        show_mode = st.radio(
            "Show",
            ["Cards Only", "Cards + Paragraphs"],
            key="group_show_mode",
            horizontal=True
        )

    st.markdown("---")

    # Filter groups
    filtered_groups = groups.copy()

    if filter_status == "Optimal (512-800t)":
        filtered_groups = [g for g in filtered_groups if get_group_validation_status(g) == 'optimal']
    elif filter_status == "Acceptable":
        filtered_groups = [g for g in filtered_groups if get_group_validation_status(g) == 'acceptable']
    elif filter_status == "Needs Review":
        filtered_groups = [g for g in filtered_groups if get_group_validation_status(g) == 'warning']

    # Sort groups
    if sort_by == "Token Count (High→Low)":
        filtered_groups.sort(key=lambda g: g['token_count'], reverse=True)
    elif sort_by == "Token Count (Low→High)":
        filtered_groups.sort(key=lambda g: g['token_count'])
    elif sort_by == "Paragraph Count":
        filtered_groups.sort(key=lambda g: len(g['para_ids']), reverse=True)

    st.caption(f"Showing {len(filtered_groups)} of {total_groups} groups")

    # === GROUP CARDS ===
    for group in filtered_groups:
        status = get_group_validation_status(group)

        # Count references in this group
        group_quran = 0
        group_hadith = 0
        group_concepts = 0
        group_people = 0
        group_places = 0

        for para_id in group['para_ids']:
            para = find_paragraph(para_id)
            if para and not para.get('deleted'):
                group_quran += len(para.get('quran_refs', []))
                group_hadith += len(para.get('hadith_refs', []))
                group_concepts += len(para.get('concepts', []))
                group_people += len(para.get('people', []))
                group_places += len(para.get('places', []))

        # Determine card theme
        card_class = f"group-card {status}"
        if group_quran >= 3:
            card_class += " quran-rich"
        elif group_hadith >= 2:
            card_class += " hadith-rich"
        elif group_concepts >= 5:
            card_class += " concept-rich"

        # Card header
        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 3, 1])

        with col1:
            status_emoji = "🟢" if status == "optimal" else "🟡" if status == "acceptable" else "🔴"
            st.markdown(f"### {status_emoji} {group['group_id'].upper()}")

        with col2:
            # Token badge
            token_color = "badge-green" if status == "optimal" else "badge-orange" if status == "acceptable" else "badge-gray"
            st.markdown(
                f'<span class="stat-badge {token_color}">{group["token_count"]} tokens</span>'
                f'<span class="stat-badge badge-gray">{len(group["para_ids"])} paragraphs</span>'
                f'<span class="stat-badge badge-gray">p.{group.get("page_start", "?")}-{group.get("page_end", "?")}</span>',
                unsafe_allow_html=True
            )

        with col3:
            expand_key = f"expand_{group['group_id']}"
            is_expanded = st.session_state.get(expand_key, False)
            if st.button("▼ Expand" if not is_expanded else "▲ Collapse", key=f"btn_{expand_key}"):
                st.session_state[expand_key] = not is_expanded
                st.rerun()

        # Reference badges
        if group_quran or group_hadith or group_concepts or group_people or group_places:
            st.markdown("<br>", unsafe_allow_html=True)
            badges_html = ""
            if group_quran > 0:
                badges_html += f'<span class="stat-badge badge-green">🟢 {group_quran} Quran</span>'
            if group_hadith > 0:
                badges_html += f'<span class="stat-badge badge-blue">🔵 {group_hadith} Hadith</span>'
            if group_concepts > 0:
                badges_html += f'<span class="stat-badge badge-orange">🟡 {group_concepts} Concepts</span>'
            if group_people > 0:
                badges_html += f'<span class="stat-badge badge-purple">👤 {group_people} People</span>'
            if group_places > 0:
                badges_html += f'<span class="stat-badge badge-purple">📍 {group_places} Places</span>'
            st.markdown(badges_html, unsafe_allow_html=True)

        # Show paragraphs if expanded or mode is "Cards + Paragraphs"
        if show_mode == "Cards + Paragraphs" or st.session_state.get(expand_key, False):
            st.markdown("---")
            for para_id in group['para_ids']:
                para_idx = find_paragraph_index(para_id)
                if para_idx >= 0:
                    para = st.session_state.paragraphs[para_idx]
                    # Show condensed paragraph info
                    st.markdown(f"**Para {para_id}** • p.{para.get('page_info', {}).get('page_number', '?')}")
                    st.caption(para['text'][:200] + "..." if len(para['text']) > 200 else para['text'])
                    st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption(f"💡 Groups are auto-generated to optimize retrieval (target: 512-800 tokens)")


def build_hierarchical_structure():
    """Build hierarchical structure: chapters containing paragraphs."""
    active_paragraphs = [p for p in st.session_state.paragraphs
                         if not p.get('grouped_into') and not p.get('deleted')]

    structure = []
    current_chapter = None
    ref_counter = 0

    for para in active_paragraphs:
        para_type = para.get('type', 'paragraph')

        # Start new chapter when we hit a chapter heading
        if para_type == 'chapter_heading':
            if current_chapter:
                structure.append(current_chapter)
            current_chapter = {
                'type': 'chapter',
                'title': para['text'][:100].strip(),
                'level': para.get('level', 1),
                'paragraphs': []
            }
        else:
            # If no chapter yet, create an implicit one
            if current_chapter is None:
                current_chapter = {
                    'type': 'chapter',
                    'title': 'Introduction',
                    'level': 1,
                    'paragraphs': []
                }

            # Build paragraph with references
            para_data = {
                'id': f"p_{para['id']:03d}",
                'text': para['text'],
                'type': para_type,
                'reviewed': para.get('reviewed', False),
                'references': []
            }

            # Add page info if available (from PDF matching)
            page_info = para.get('page_info')
            if page_info:
                para_data['page_info'] = {
                    'page_number': page_info.get('page_number'),
                    'confidence': page_info.get('confidence', 0),
                    'match_type': page_info.get('match_type', 'unknown')
                }

            # Add Quran references
            for qref in para.get('quran_refs', []):
                ref_counter += 1
                ref_data = {
                    'id': f"ref_{ref_counter:03d}",
                    'type': 'quran',
                    'detection': qref.get('detection', 'auto'),
                    'surah': qref.get('surah'),
                    'ayah_start': qref.get('ayah_start'),
                    'ayah_end': qref.get('ayah_end'),
                    'maulana_text': qref.get('quoted_text', ''),
                    'status': 'verified' if qref.get('verified') else 'pending',
                    'verified_ref': None,  # Will be populated by API verification
                    'notes': []
                }
                para_data['references'].append(ref_data)

            # Add Hadith references
            for href in para.get('hadith_refs', []):
                ref_counter += 1
                ref_data = {
                    'id': f"ref_{ref_counter:03d}",
                    'type': 'hadith',
                    'detection': href.get('detection', 'auto'),
                    'maulana_ref': f"{href.get('collection', 'Unknown')} {href.get('number', '')}".strip(),
                    'maulana_text': '',  # Extracted hadith text from passage
                    'verified_ref': {
                        'collection': href.get('collection'),
                        'number': href.get('number'),
                        'sunnah_url': None,
                        'authenticity': None
                    } if href.get('verified') else None,
                    'modern_translation': None,
                    'match_confidence': None,
                    'status': 'verified' if href.get('verified') else 'pending',
                    'notes': []
                }
                para_data['references'].append(ref_data)

            # Add footnote references
            for fref in para.get('footnote_refs', []):
                ref_counter += 1
                fn_type = fref.get('footnote_type', 'other')
                ref_data = {
                    'id': f"ref_{ref_counter:03d}",
                    'type': fn_type if fn_type in ['quran', 'hadith'] else 'footnote',
                    'marker': fref.get('marker'),
                    'footnote_number': fref.get('number'),
                    'linked_footnote': fref.get('linked_footnote'),
                    'footnote_type': fn_type,
                    'detection': 'auto',
                    'status': 'verified' if fref.get('verified') else 'pending'
                }
                para_data['references'].append(ref_data)

            # Add to chapter
            if para_type == 'subheading':
                para_data['is_subheading'] = True

            current_chapter['paragraphs'].append(para_data)

    # Don't forget the last chapter
    if current_chapter:
        structure.append(current_chapter)

    return structure


def export_json():
    """Generate JSON export matching ANNOTATION_TOOL_SPEC.md schema with smart grouping."""
    reviewed, total = get_progress()
    active_paragraphs = [p for p in st.session_state.paragraphs
                         if not p.get('grouped_into') and not p.get('deleted')]

    # Count references
    quran_count = sum(len(p.get('quran_refs', [])) for p in st.session_state.paragraphs)
    hadith_count = sum(len(p.get('hadith_refs', [])) for p in st.session_state.paragraphs)
    footnote_count = sum(len(p.get('footnote_refs', [])) for p in st.session_state.paragraphs)

    # Count verified vs pending
    verified_count = 0
    flagged_count = 0
    for p in st.session_state.paragraphs:
        for ref in p.get('quran_refs', []) + p.get('hadith_refs', []) + p.get('footnote_refs', []):
            if ref.get('verified'):
                verified_count += 1
            elif ref.get('flagged'):
                flagged_count += 1

    # Count chapters
    chapter_count = sum(1 for p in active_paragraphs if p.get('type') == 'chapter_heading')

    # Determine annotation status
    if reviewed == 0:
        annotation_status = 'not_started'
    elif reviewed < total:
        annotation_status = 'in_progress'
    else:
        annotation_status = 'pending_review'

    # Build footnotes list
    all_footnotes = st.session_state.document_footnotes + st.session_state.endnotes
    footnotes_export = []
    for fn in all_footnotes:
        footnotes_export.append({
            'marker': f"[{fn['id']}]",
            'original_text': fn.get('text', ''),
            'type': fn.get('type', 'other'),
            'linked_to': None  # Will be populated when linking is complete
        })

    # Build structure first
    structure = build_hierarchical_structure()

    # Create groups from structure (chapter by chapter)
    all_groups = []
    group_counter = 0
    para_to_group = {}  # Map para_id -> group_id

    for chapter in structure:
        chapter_title = chapter.get('title', 'Unknown')
        chapter_paras = []

        # Collect raw paragraph data for grouping
        for para in chapter.get('paragraphs', []):
            # Build a simplified para object for grouping
            para_obj = {
                'id': int(para['id'].replace('p_', '')),
                'text': para.get('text', ''),
                'type': para.get('type', 'paragraph'),
                'is_subheading': para.get('is_subheading', False),
                'page_info': para.get('page_info', {})
            }
            chapter_paras.append(para_obj)

        # Create groups for this chapter
        chapter_groups, group_counter = create_groups_for_chapter(
            chapter_paras, chapter_title, group_counter
        )
        all_groups.extend(chapter_groups)

        # Build para_id -> group_id mapping
        for group in chapter_groups:
            for para_id in group['para_ids']:
                para_to_group[para_id] = group['group_id']

    # Add group_id to each paragraph in structure
    for chapter in structure:
        for para in chapter.get('paragraphs', []):
            para_id = para['id']
            para['group_id'] = para_to_group.get(para_id)

    export_data = {
        'book_metadata': {
            'title': st.session_state.book_title or 'Untitled',
            'author': st.session_state.author or 'Maulana Wahiduddin Khan',
            'slug': generate_slug(st.session_state.book_title or 'untitled'),
            'total_chapters': chapter_count,
            'total_paragraphs': len(active_paragraphs),
            'total_groups': len(all_groups),
            'annotation_status': annotation_status,
            'annotated_by': st.session_state.annotator or None,
            'approved_date': None,
            'export_date': datetime.now().isoformat()
        },
        'structure': structure,
        'groups': all_groups,
        'footnotes': footnotes_export,
        'statistics': {
            'total_quran_refs': quran_count,
            'total_hadith_refs': hadith_count,
            'total_footnote_refs': footnote_count,
            'verified_refs': verified_count,
            'flagged_refs': flagged_count,
            'unverified_refs': (quran_count + hadith_count + footnote_count) - verified_count,
            'reviewed_paragraphs': reviewed,
            'total_paragraphs': total,
            'completion_percentage': round((reviewed / total * 100) if total > 0 else 0, 1),
            'avg_tokens_per_group': round(sum(g['token_count'] for g in all_groups) / len(all_groups), 1) if all_groups else 0,
            'min_group_tokens': min((g['token_count'] for g in all_groups), default=0),
            'max_group_tokens': max((g['token_count'] for g in all_groups), default=0)
        }
    }

    return json.dumps(export_data, indent=2, ensure_ascii=False)


def render_header():
    """Render the header section with upload and metadata."""
    st.title("📖 Islamic Text Annotation Tool")
    st.caption(f"v{VERSION} • {BUILD_DATE}")

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        # DOCX upload - hide after loaded
        if not st.session_state.file_uploaded:
            uploaded_file = st.file_uploader(
                "Upload DOCX file",
                type=['docx'],
                key='file_uploader'
            )
            if uploaded_file is not None:
                process_uploaded_file(uploaded_file)
                # Set book title from filename if not set
                if not st.session_state.book_title:
                    st.session_state.book_title = uploaded_file.name.replace('.docx', '')
                save_progress()  # Auto-save after upload
                st.rerun()
        else:
            st.markdown('<div class="upload-success">✅ DOCX loaded</div>', unsafe_allow_html=True)

        # PDF upload - hide after loaded
        if PDF_SUPPORT:
            if not st.session_state.pdf_loaded:
                uploaded_pdf = st.file_uploader(
                    "Upload PDF (for page numbers)",
                    type=['pdf'],
                    key='pdf_uploader',
                    help="Extracts page numbers for each paragraph"
                )
                if uploaded_pdf is not None:
                    process_pdf_file(uploaded_pdf)
                    save_progress()  # Auto-save after PDF upload
                    st.rerun()
            else:
                # Show status + re-upload + re-match options
                col_status, col_reupload, col_rematch = st.columns([2, 1, 1])
                with col_status:
                    st.markdown('<div class="upload-success">✅ PDF loaded</div>', unsafe_allow_html=True)
                with col_reupload:
                    if st.button("🔄 Re-upload", key='reupload_pdf', help="Replace current PDF"):
                        st.session_state.pdf_loaded = False
                        st.session_state.pdf_pages = []
                        st.rerun()
                with col_rematch:
                    if st.button("🔁 Re-match", key='rematch_pdf', help="Re-run paragraph-to-PDF matching"):
                        # Force re-matching by clearing page_info
                        for para in st.session_state.paragraphs:
                            if 'page_info' in para:
                                del para['page_info']

                        # Re-run matching
                        with st.status("🔄 Re-matching paragraphs to PDF...", expanded=True) as status:
                            para_count = len(st.session_state.paragraphs)
                            page_count = len(st.session_state.pdf_pages)

                            status.update(label=f"Matching {para_count} paragraphs to {page_count} pages...")

                            progress_bar = st.progress(0)
                            start_time = time.time()

                            # Track stats in real-time
                            stats = {'exact': 0, 'fuzzy': 0, 'estimated': 0}

                            def update_progress(current, total):
                                # Update progress bar
                                progress_bar.progress(current / total)

                                # Calculate elapsed time and estimate remaining
                                elapsed = time.time() - start_time
                                rate = current / elapsed if elapsed > 0 else 0
                                remaining_secs = int((total - current) / rate) if rate > 0 else 0

                                # Count current match stats (from paragraphs processed so far)
                                stats['exact'] = sum(1 for p in st.session_state.paragraphs[:current]
                                                    if p.get('page_info', {}).get('match_type') == 'exact')
                                stats['fuzzy'] = sum(1 for p in st.session_state.paragraphs[:current]
                                                    if p.get('page_info', {}).get('match_type') == 'fuzzy')
                                stats['estimated'] = sum(1 for p in st.session_state.paragraphs[:current]
                                                        if p.get('page_info', {}).get('match_type') == 'estimated')

                                # Update status label with ALL info (single source of truth)
                                pct = int(100 * current / total)
                                status.update(
                                    label=f"🔄 Re-matching: {pct}% ({current}/{total}) | "
                                          f"✓ {stats['exact']} exact, {stats['fuzzy']} fuzzy, {stats['estimated']} estimated | "
                                          f"⏱️ {remaining_secs}s remaining"
                                )

                            st.session_state.paragraphs = match_all_paragraphs_to_pages(
                                st.session_state.paragraphs,
                                st.session_state.pdf_pages,
                                progress_callback=update_progress
                            )

                            progress_bar.empty()

                            # Count match types
                            exact = sum(1 for p in st.session_state.paragraphs
                                       if p.get('page_info', {}).get('match_type') == 'exact')
                            fuzzy = sum(1 for p in st.session_state.paragraphs
                                       if p.get('page_info', {}).get('match_type') == 'fuzzy')
                            estimated = sum(1 for p in st.session_state.paragraphs
                                           if p.get('page_info', {}).get('match_type') == 'estimated')

                            status.update(label=f"✅ Re-matched! {exact} exact, {fuzzy} fuzzy, {estimated} estimated", state="complete")

                        save_progress()
                        st.rerun()

    with col2:
        st.session_state.book_title = st.text_input(
            "Book Title",
            value=st.session_state.book_title,
            key='book_title_input'
        )
        col2a, col2b = st.columns(2)
        with col2a:
            st.session_state.author = st.text_input(
                "Author",
                value=st.session_state.author,
                key='author_input'
            )
        with col2b:
            st.session_state.annotator = st.text_input(
                "Annotator Name",
                value=st.session_state.annotator,
                key='annotator_input'
            )

        # PDF status
        if st.session_state.pdf_loaded:
            st.caption(f"📄 PDF loaded ({len(st.session_state.pdf_pages)} pages)")

    with col3:
        st.write("")  # Spacing
        st.write("")
        if st.session_state.file_uploaded:
            json_data = export_json()
            st.download_button(
                label="📥 Export JSON",
                data=json_data,
                file_name=f"{st.session_state.book_title or 'annotations'}.json",
                mime="application/json"
            )


def render_progress():
    """Render the progress bar."""
    if not st.session_state.file_uploaded:
        return

    reviewed, total = get_progress()
    if total > 0:
        progress = reviewed / total
        st.progress(progress)
        st.caption(f"Progress: {reviewed}/{total} paragraphs reviewed ({progress*100:.1f}%)")


def group_selected_paragraphs():
    """Group selected consecutive paragraphs into one."""
    selected = sorted(st.session_state.selected_for_grouping)

    if len(selected) < 2:
        return

    # Check if paragraphs are consecutive
    para_indices = []
    for i, para in enumerate(st.session_state.paragraphs):
        if para['id'] in selected:
            para_indices.append(i)

    # Verify they are consecutive
    is_consecutive = all(para_indices[i] + 1 == para_indices[i + 1] for i in range(len(para_indices) - 1))

    if not is_consecutive:
        st.sidebar.error("Please select consecutive paragraphs only")
        return

    # Get the first paragraph (will be the merged one)
    first_idx = para_indices[0]
    first_para = st.session_state.paragraphs[first_idx]

    # Merge text from all selected paragraphs
    merged_text_parts = []
    merged_quran_refs = list(first_para.get('quran_refs', []))
    merged_hadith_refs = list(first_para.get('hadith_refs', []))
    merged_seerah_refs = list(first_para.get('seerah_refs', []))
    merged_other_book_refs = list(first_para.get('other_book_refs', []))
    merged_year_refs = list(first_para.get('year_refs', []))
    grouped_para_ids = []

    for idx in para_indices:
        para = st.session_state.paragraphs[idx]
        merged_text_parts.append(para['text'])
        grouped_para_ids.append(para['id'])

        if idx != first_idx:
            # Merge references from other paragraphs
            merged_quran_refs.extend(para.get('quran_refs', []))
            merged_hadith_refs.extend(para.get('hadith_refs', []))
            merged_seerah_refs.extend(para.get('seerah_refs', []))
            merged_other_book_refs.extend(para.get('other_book_refs', []))
            merged_year_refs.extend(para.get('year_refs', []))
            # Mark as grouped
            para['grouped_into'] = first_para['id']

    # Update first paragraph with merged content
    first_para['text'] = '\n\n'.join(merged_text_parts)
    first_para['quran_refs'] = merged_quran_refs
    first_para['hadith_refs'] = merged_hadith_refs
    first_para['seerah_refs'] = merged_seerah_refs
    first_para['other_book_refs'] = merged_other_book_refs
    first_para['grouped_from'] = grouped_para_ids

    # Update detected refs for the merged paragraph (cached)
    quran_refs = cached_detect_quran_refs(first_para['text'])
    hadith_refs = cached_detect_hadith_refs(first_para['text'])
    year_refs = find_year_positions(first_para['text'])
    st.session_state.detected_refs[first_para['id']] = {
        'quran': quran_refs,
        'hadith': hadith_refs,
        'year': year_refs
    }
    # Update year_refs for merged paragraph
    first_para['year_refs'] = [
        {
            'text': first_para['text'][ref[0]:ref[1]],
            'start_pos': ref[0],
            'end_pos': ref[1],
            'detection': 'auto',
            'verified': False
        }
        for ref in year_refs
    ]

    # Clear selection
    st.session_state.selected_for_grouping = set()


def render_sidebar():
    """Render the sidebar with highlighting options."""
    with st.sidebar:
        # Resume saved work section
        saved_books = get_saved_books()
        if saved_books and not st.session_state.file_uploaded:
            st.header("📂 Resume Work")
            for book in saved_books[:5]:  # Show top 5 recent
                last_time = book['last_saved'][:16].replace('T', ' ') if book['last_saved'] else '?'
                status = book.get('status', 'pending')
                saved_by = book.get('saved_by', '?')

                # Status badge
                status_badge = {'pending': '🟡', 'annotated': '🔵', 'approved': '🟢', 'needs_revision': '🟠'}.get(status, '⚪')

                if st.button(f"{status_badge} {book['title'][:20]}...",
                             key=f"resume_{book['file']}", use_container_width=True):
                    load_saved_book(book['file'])
                    st.rerun()
                st.caption(f"{book['para_count']} para | by {saved_by} | {last_time}")
            st.divider()

        # Version History Section (show when book is loaded)
        if st.session_state.get('file_uploaded'):
            st.header("📜 Version History")

            # Use current_book_folder for consistent slug generation
            book_folder = st.session_state.get('current_book_folder')
            slug = book_folder if book_folder else st.session_state.book_title.strip().lower().replace(' ', '_').replace('/', '_')[:50]
            user = st.session_state.get('current_user', 'guest')
            version_dir = os.path.join(DATA_DIR, 'versions', f"{slug}_{user}")

            if os.path.exists(version_dir):
                version_files = sorted(glob.glob(os.path.join(version_dir, "v_*.json")), reverse=True)

                if version_files:
                    st.caption(f"{len(version_files)} versions available")

                    # Show version selector
                    version_labels = []
                    for vf in version_files[:10]:  # Show last 10
                        # Extract timestamp from filename: v_2026-01-11T10:30:00.json
                        timestamp_str = os.path.basename(vf).replace('v_', '').replace('.json', '')
                        try:
                            dt = datetime.fromisoformat(timestamp_str)
                            time_ago = humanize_time_ago(dt)  # "2 hours ago"
                            version_labels.append(f"{time_ago} ({dt.strftime('%I:%M %p')})")
                        except:
                            version_labels.append(timestamp_str)

                    selected_idx = st.selectbox(
                        "Restore from:",
                        range(len(version_labels)),
                        format_func=lambda i: version_labels[i],
                        key="version_select"
                    )

                    if st.button("⏪ Rollback to this version", type="secondary", use_container_width=True):
                        selected_file = version_files[selected_idx]
                        # Log rollback
                        current_version = len(version_files)
                        target_version = len(version_files) - selected_idx
                        logger.info(f"[VERSION_ROLLBACK] book={slug}, from=v{current_version}, to=v{target_version}")

                        load_saved_book(selected_file)
                        st.success(f"Restored version from {version_labels[selected_idx]}")
                        st.rerun()
                else:
                    st.caption("No versions yet")
            else:
                st.caption("No versions yet")

            st.divider()

        st.header("Highlight Settings")

        # Toggle switches
        st.session_state.highlight_keywords = st.checkbox(
            "Highlight Keywords",
            value=st.session_state.highlight_keywords,
            help="Highlight Islamic terms like Quran, Hadith, Prophet, etc."
        )

        st.session_state.highlight_numbers = st.checkbox(
            "Highlight Numbers",
            value=st.session_state.highlight_numbers,
            help="Highlight numbers and numerical references (e.g., 3:195)"
        )

        st.session_state.highlight_years = st.checkbox(
            "Highlight Years/Dates",
            value=st.session_state.highlight_years,
            help="Highlight year references (AD, BC, CE, AH, century, etc.)"
        )

        st.divider()

        # Auto-detection toggle
        st.subheader("Auto-Detection")
        auto_detect_enabled = st.checkbox(
            "Auto-detect Quran/Hadith",
            value=st.session_state.get('auto_detect_enabled', True),
            help="Automatically detect Quran verses and Hadith references on book load"
        )
        st.session_state.auto_detect_enabled = auto_detect_enabled
        if not auto_detect_enabled:
            st.caption("Auto-detection disabled. Manual annotation only.")

        st.divider()

        # Custom keywords
        st.subheader("Custom Keywords")
        st.caption("Add words to highlight (one per line)")

        # Text area for keywords
        keywords_text = st.text_area(
            "Keywords",
            value="\n".join(st.session_state.custom_keywords),
            height=200,
            key="keywords_input",
            label_visibility="collapsed"
        )

        # Parse keywords from text area
        new_keywords = [k.strip() for k in keywords_text.split("\n") if k.strip()]
        st.session_state.custom_keywords = new_keywords

        # Quick add common keywords
        st.caption("Quick add:")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reset Defaults", use_container_width=True):
                st.session_state.custom_keywords = DEFAULT_KEYWORDS.copy()
                st.rerun()
        with col2:
            if st.button("Clear All", use_container_width=True):
                st.session_state.custom_keywords = []
                st.rerun()

        st.divider()

        # Paragraph Grouping Section
        st.subheader("Paragraph Grouping")
        selected_count = len(st.session_state.selected_for_grouping)
        if selected_count > 0:
            st.info(f"{selected_count} paragraphs selected")

            if selected_count >= 2:
                if st.button("🔗 Group Selected", use_container_width=True):
                    group_selected_paragraphs()
                    st.rerun()
            else:
                st.caption("Select at least 2 consecutive paragraphs to group")

            if st.button("Clear Selection", use_container_width=True):
                st.session_state.selected_for_grouping = set()
                st.rerun()
        else:
            st.caption("Check 'Group' boxes on consecutive paragraphs to merge them")

        st.divider()

        # LLM Concept Extraction Section (Admin Only)
        if st.session_state.get('user_role') == 'admin':
            st.subheader("LLM Extraction")
            has_deepseek = bool(os.environ.get('DEEPSEEK_API_KEY'))
            has_gemini = gemini_rotator.has_keys()

            if st.session_state.file_uploaded and (has_deepseek or has_gemini):
                # Provider selection
                available_providers = []
                if has_deepseek:
                    available_providers.append("deepseek")
                if has_gemini:
                    available_providers.append("gemini")
                provider_choice = st.radio("Provider", available_providers, horizontal=True)

                # Get extraction stats
                all_paras = st.session_state.paragraphs
                stats = get_extraction_stats(all_paras)

                # Count extractable paragraphs (not deleted, not header, type=paragraph)
                extractable = [p for p in all_paras
                              if not p.get('deleted')
                              and not p.get('grouped_into')
                              and p.get('type', 'paragraph') == 'paragraph'
                              and p.get('extraction_status') != 'extracted']
                pending_extractable = len(extractable)

                st.caption(f"Extracted: {stats['extracted']}/{stats['total']} | Pending: {pending_extractable}")
                if stats['errors'] > 0:
                    st.caption(f"Errors: {stats['errors']}")

                # Find next unextracted paragraph (skip deleted/headers)
                next_idx = 0
                for i, p in enumerate(all_paras):
                    if (p.get('extraction_status') != 'extracted'
                        and not p.get('deleted')
                        and not p.get('grouped_into')
                        and p.get('type', 'paragraph') == 'paragraph'):
                        next_idx = i
                        break

                col_ext1, col_ext2 = st.columns(2)
                with col_ext1:
                    if st.button("Extract 10", use_container_width=True, help="Extract concepts from next 10 paragraphs"):
                        with st.spinner(f"Extracting from para {next_idx+1}..."):
                            # Run extraction
                            results = asyncio.run(extract_batch_range(
                                all_paras, next_idx, 10,
                                provider=provider_choice,
                                pause_seconds=1.0 if provider_choice == "gemini" else 0.5
                            ))
                            # Merge results
                            merge_extractions_to_paragraphs(all_paras, results)
                            save_progress()
                            st.success(f"Extracted {len(results)} paragraphs!")
                            st.rerun()

                with col_ext2:
                    if st.button("Extract All", use_container_width=True, help="Extract all remaining paragraphs"):
                        if pending_extractable > 50:
                            st.warning(f"{pending_extractable} paragraphs - may take ~{pending_extractable}s")
                        progress = st.progress(0)
                        status = st.empty()

                        def update_progress(done, total):
                            progress.progress(done / total)
                            status.text(f"Processing {done}/{total}...")

                        results = asyncio.run(extract_batch_range(
                            all_paras, next_idx, pending_extractable,
                            provider=provider_choice,
                            pause_seconds=1.0 if provider_choice == "gemini" else 0.5,
                            progress_callback=update_progress
                        ))
                        merge_extractions_to_paragraphs(all_paras, results)
                        save_progress()
                        st.success(f"Extracted {len(results)} paragraphs!")
                        st.rerun()

                # Stats display
                if stats['extracted'] > 0:
                    st.markdown(f"""
                    <div style='font-size:0.8em;color:#94a3b8;'>
                    Concepts: {stats['total_concepts']} | Aspects: {stats['total_verse_aspects']} |
                    People: {stats['total_people']} | Events: {stats['total_events']}
                    </div>
                    """, unsafe_allow_html=True)
            elif not (has_deepseek or has_gemini):
                st.caption("Set DEEPSEEK_API_KEY or GEMINI_API_KEY env")
            else:
                st.caption("Upload a book first")

            st.divider()

            # LightRAG Export Section
            st.subheader("LightRAG Export")
            if st.session_state.file_uploaded:
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    merge_chunks = st.checkbox("Merge to 512t", value=True,
                                              help="Merge paragraphs to ~512 tokens")
                with col_exp2:
                    if st.button("Export", use_container_width=True):
                        # Build book data from session state
                        book_slug = st.session_state.get('book_slug', 'unknown-book')
                        book_data = {
                            "book_metadata": {
                                "title": st.session_state.get('book_title', 'Unknown'),
                                "author": "Maulana Wahiduddin Khan",
                                "slug": book_slug,
                            },
                            "structure": [],
                            "groups": []
                        }
                        # Rebuild structure from paragraphs
                        current_chapter = {"title": "Main", "paragraphs": []}
                        for para in st.session_state.paragraphs:
                            current_chapter["paragraphs"].append(para)
                        book_data["structure"].append(current_chapter)

                        # Create groups for citation linking
                        chapter_paras = []
                        for para in st.session_state.paragraphs:
                            if not para.get('deleted') and not para.get('grouped_into'):
                                chapter_paras.append({
                                    'id': para.get('id'),
                                    'text': para.get('text', ''),
                                    'type': para.get('type', 'paragraph'),
                                    'is_subheading': para.get('type') == 'subheading',
                                    'page_info': para.get('page_info', {})
                                })
                        groups, _ = create_groups_for_chapter(chapter_paras, "Main", 0)
                        book_data["groups"] = groups

                        # Export
                        lightrag_data = export_for_lightrag(book_data, use_merged_chunks=merge_chunks)
                        json_str = json.dumps(lightrag_data, indent=2, ensure_ascii=False)

                        st.download_button(
                            "Download LightRAG JSON",
                            json_str,
                            f"{st.session_state.get('book_slug', 'book')}_lightrag.json",
                            mime="application/json"
                        )
                        st.success(f"Ready! {lightrag_data['metadata']['total_chunks']} chunks, "
                                  f"{lightrag_data['metadata']['total_entities']} entities")
            else:
                st.caption("Upload a book first")

            st.divider()

            # VIEW MODE SELECTOR (only show when book is loaded)
            if st.session_state.file_uploaded:
                st.subheader("📑 View Mode")
                view_mode = st.radio(
                    "Display Mode",
                    ["Paragraph View", "Group Dashboard"],
                    key="view_mode",
                    help="Toggle between paragraph editing and group visualization",
                    label_visibility="collapsed"
                )

                st.divider()

            # GROUP OVERVIEW SECTION
            st.subheader("📦 Group Overview")

            if st.session_state.get('groups'):
                # Stats summary
                total_groups = len(st.session_state.groups)
                avg_tokens = sum(g['token_count'] for g in st.session_state.groups) / total_groups if total_groups > 0 else 0
                st.caption(f"{total_groups} groups | Avg: {avg_tokens:.0f} tokens")

                # Regenerate button
                if st.button("🔄 Regenerate Groups", use_container_width=True):
                    generate_groups()
                    st.success("Groups regenerated!")
                    st.rerun()

                st.markdown("---")

                # Validation summary
                optimal = sum(1 for g in st.session_state.groups if get_group_validation_status(g) == 'optimal')
                acceptable = sum(1 for g in st.session_state.groups if get_group_validation_status(g) == 'acceptable')
                warning = sum(1 for g in st.session_state.groups if get_group_validation_status(g) == 'warning')
                st.caption(f"🟢 {optimal} optimal | 🟡 {acceptable} acceptable | 🔴 {warning} needs review")

                st.markdown("**Groups:**")

                # Scrollable group list
                for group in st.session_state.groups:
                    col_cb, col_info = st.columns([0.5, 4.5])

                    with col_cb:
                        # Checkbox for merge selection
                        is_selected = group['group_id'] in st.session_state.selected_groups
                        if st.checkbox("", value=is_selected, key=f"sel_{group['group_id']}",
                                      label_visibility="collapsed"):
                            st.session_state.selected_groups.add(group['group_id'])
                        else:
                            st.session_state.selected_groups.discard(group['group_id'])

                    with col_info:
                        # Group info with validation color
                        status = get_group_validation_status(group)
                        token_color = "🟢" if status == 'optimal' else "🟡" if status == 'acceptable' else "🔴"

                        # Clickable group label
                        if st.button(
                            f"{token_color} **{group['group_id']}** | {group['token_count']}t | "
                            f"{len(group['para_ids'])}p | {group.get('page_start', '?')}-{group.get('page_end', '?')}",
                            key=f"nav_{group['group_id']}",
                            use_container_width=True
                        ):
                            st.session_state.scroll_to_group = group['group_id']
                            st.rerun()

                # Merge button (appears when exactly 2 groups selected)
                selected_count = len(st.session_state.selected_groups)
                if selected_count == 2:
                    st.markdown("---")
                    if st.button("🔗 Merge Selected Groups", use_container_width=True, type="primary"):
                        g1, g2 = list(st.session_state.selected_groups)
                        merge_groups(g1, g2)
                        st.session_state.selected_groups.clear()
                        st.success("Groups merged!")
                        st.rerun()
                elif selected_count > 2:
                    st.info("ℹ️ Select exactly 2 groups to merge")

            else:
                st.caption("No groups yet")
                if st.button("📦 Generate Groups", use_container_width=True, type="primary"):
                    generate_groups()
                    st.success("Groups created!")
                    st.rerun()

            st.divider()

        # Footnotes section
        if st.session_state.file_uploaded:
            all_footnotes = st.session_state.document_footnotes + st.session_state.endnotes
            if all_footnotes:
                st.subheader(f"📑 Footnotes ({len(all_footnotes)})")
                with st.expander("View all footnotes"):
                    for fn in all_footnotes:
                        fn_type = fn.get('type', 'other')
                        type_emoji = {
                            'quran': '🟢',
                            'hadith': '🔵',
                            'book': '📚',
                            'other': '📝'
                        }.get(fn_type, '❓')
                        st.markdown(f"{type_emoji} **[{fn['id']}]** {fn['text'][:80]}{'...' if len(fn['text']) > 80 else ''}")

        st.divider()

        # Submit button for annotators (green rounded style)
        if st.session_state.get('user_role') == 'annotator':
            st.markdown("---")
            st.subheader("Submit Work")
            st.markdown('<div class="submit-btn">', unsafe_allow_html=True)
            if st.button("📤 Submit for Approval", use_container_width=True):
                submit_book_for_review()
                st.success("Book submitted for admin approval!")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # Color legend
        st.subheader("Color Legend")
        st.markdown("""
        **Highlights:**
        - 🟢 **Green**: Quran references
        - 🔵 **Blue**: Hadith references
        - 🩵 **Cyan**: Years/Dates
        - 🟠 **Orange**: Keywords
        - 🟣 **Purple**: Numbers
        - 📑 **Footnote markers**: [1], [2], etc.

        **Structure Types:**
        - 📘 **Chapter**: Dark blue, bold, centered
        - 📗 **Subheading**: Blue, bold
        - 💬 **Quote**: Gray, italic, indented
        - 📄 **Paragraph**: Normal text
        """)



@st.fragment
def render_group(group_idx: int):
    """Render an entire group with header and paragraphs."""
    if group_idx >= len(st.session_state.groups):
        return

    group = st.session_state.groups[group_idx]

    # Alternating background colors
    bg_color = "#f0f9ff" if group_idx % 2 == 0 else "#f8fafc"

    # Group container with ID for scrolling
    st.markdown(f"""
    <div id='group-{group['group_id']}' class='group-container' style='
        background-color:{bg_color};
        padding:20px;
        border-radius:12px;
        margin-bottom:20px;
        border: 1px solid #e2e8f0;
    '>
    </div>
    """, unsafe_allow_html=True)

    # Group header
    col1, col2, col3, col4 = st.columns([2, 1.5, 1, 0.5])

    with col1:
        st.markdown(f"### 📦 {group['group_id'].upper()}")

    with col2:
        # Token count with validation color
        status = get_group_validation_status(group)
        if status == 'optimal':
            st.success(f"✓ {group['token_count']} tokens")
        elif status == 'acceptable':
            st.warning(f"⚠ {group['token_count']} tokens")
        else:
            st.error(f"⚠ {group['token_count']} tokens")

    with col3:
        para_count = len(group['para_ids'])
        page_range = f"{group.get('page_start', '?')}-{group.get('page_end', '?')}"
        st.caption(f"**{para_count}** paras | p.{page_range}")

    with col4:
        # Collapse/expand toggle
        collapse_key = f"toggle_{group['group_id']}"
        is_collapsed = group.get('collapsed', False)
        if st.button("▼" if not is_collapsed else "►", key=collapse_key):
            group['collapsed'] = not is_collapsed
            st.rerun(scope="fragment")

    # Validation warnings
    tokens = group['token_count']
    if tokens > 800:
        if tokens > 1000:
            st.error(f"⚠️ Group too large ({tokens} tokens) - Target: 512-800 tokens")
        else:
            st.warning(f"⚠️ Group size acceptable but large ({tokens} tokens)")
    elif tokens < 200:
        st.info(f"ℹ️ Group too small ({tokens} tokens) - Consider merging")

    # Render paragraphs (if not collapsed)
    if not group.get('collapsed', False):
        st.markdown("---")
        for para_id in group['para_ids']:
            para_idx = find_paragraph_index(para_id)
            if para_idx >= 0:
                render_paragraph(para_idx)

    st.markdown("</div>", unsafe_allow_html=True)


# Callback functions for Add Reference UI (prevents race conditions)
def toggle_add_ref_form(para_id: str):
    """Callback to show add reference form."""
    add_ref_key = f"show_add_ref_{para_id}"
    st.session_state[add_ref_key] = True

def close_add_ref_form(para_id: str):
    """Callback to close add reference form."""
    add_ref_key = f"show_add_ref_{para_id}"
    st.session_state[add_ref_key] = False


@st.fragment
def render_paragraph(para_idx: int):
    """Render a single paragraph with its annotations (fragment for fast updates)."""
    para = st.session_state.paragraphs[para_idx]
    para_id = para['id']
    detected = st.session_state.detected_refs.get(para_id, {'quran': [], 'hadith': []})

    # Check if paragraph is part of a group or deleted
    if para.get('grouped_into') or para.get('deleted'):
        return  # Skip rendering

    # Paragraph container
    with st.container():
        token_info = count_tokens(para['text'])
        has_refs = bool(detected['quran'] or detected['hadith'] or detected.get('year') or
                       para.get('quran_refs') or para.get('hadith_refs') or para.get('year_refs'))
        ref_indicator = "📌" if has_refs else ""

        # Get current paragraph type
        para_type = para.get('type', 'paragraph')
        para_level = para.get('level')
        quote_type = para.get('quote_type')

        # Row 1: Header | Type | Page | Group Controls
        # Layout: [Paragraph X • [80w·482c]] [Type ▼] [p.5 ✏️] [Group ▼]
        if st.session_state.get('groups'):
            col_header, col_type, col_page, col_group = st.columns([3, 1.5, 1.2, 1.8])
        else:
            col_header, col_type, col_page = st.columns([4, 2, 1.5])

        with col_header:
            junk_badge = "🔴 " if para.get('potential_delete') else ""
            reviewed_dot = "•" if not para.get('reviewed') else "✓"
            # Highlight if this is the last read paragraph
            is_last_read = st.session_state.get('last_read_para') == para_id
            bookmark_style = "background:#3b82f6;color:white;" if is_last_read else ""
            st.markdown(
                f"### {junk_badge}Paragraph {para_id} {ref_indicator} "
                f"<span style='font-size:0.7em;background:#334155;color:#94a3b8;padding:2px 8px;border-radius:4px;{bookmark_style}'>"
                f"{token_info['words']}w · {token_info['chars']}c</span> "
                f"<span style='font-size:0.7em;color:#64748b;'>{reviewed_dot}</span>",
                unsafe_allow_html=True
            )

        with col_type:
            # Type dropdown for structure classification
            type_options = ["paragraph", "chapter_heading", "subheading", "quote"]
            current_idx = type_options.index(para_type) if para_type in type_options else 0
            new_type = st.selectbox(
                "Type",
                type_options,
                index=current_idx,
                key=f"type_{para_id}",
                label_visibility="collapsed"
            )
            if new_type != para_type:
                para['type'] = new_type
                # Set default level for headings
                if new_type == 'chapter_heading':
                    para['level'] = 1
                elif new_type == 'subheading':
                    para['level'] = 2
                else:
                    para['level'] = None
                mark_activity(para_id)
                save_progress()  # Auto-save on type change

        with col_page:
            # Page number with edit button - simple inline layout
            page_info = para.get('page_info', {})
            current_page = page_info.get('page_number', 1)
            edit_key = f"edit_page_{para_id}"
            saved_key = f"page_saved_{para_id}"

            if st.session_state.get(edit_key) and st.session_state.pdf_loaded:
                # Edit mode: show input + save button
                pc1, pc2 = st.columns([2, 1])
                with pc1:
                    new_page = st.number_input(f"p.", value=current_page, min_value=1,
                                               key=f"page_{para_id}", label_visibility="collapsed")
                with pc2:
                    if st.button("✓", key=f"psave_{para_id}", help="Save"):
                        if new_page != current_page:
                            para['page_info'] = {'page_number': new_page, 'confidence': 1.0, 'match_type': 'manual'}
                        save_progress()
                        st.session_state[edit_key] = False
                        st.session_state[saved_key] = True
                        st.rerun(scope="fragment")
            else:
                # Display mode: show page button
                if st.session_state.pdf_loaded:
                    # Show toast notification if just saved
                    if st.session_state.get(saved_key):
                        st.toast(f"Page {current_page} saved!", icon="✅")
                        st.session_state[saved_key] = False
                    # Toggle edit mode inline
                    if st.button(f"p.{current_page} ✏️", key=f"pedit_{para_id}"):
                        st.session_state[edit_key] = True
                        st.rerun(scope="fragment")
                else:
                    st.caption(f"p.{current_page}")

        # Group controls (move to group, split button)
        if st.session_state.get('groups'):
            with col_group:
                current_group_id = para.get('group_id')
                group_ids = [g['group_id'] for g in st.session_state.groups]

                if current_group_id in group_ids:
                    current_idx = group_ids.index(current_group_id)
                else:
                    current_idx = 0 if group_ids else -1

                if group_ids:
                    selected_group = st.selectbox(
                        "Move to",
                        group_ids,
                        index=max(0, current_idx),
                        key=f"move_group_{para_id}",
                        label_visibility="collapsed"
                    )

                    if selected_group != current_group_id:
                        move_paragraph_to_group(para_id, selected_group)
                        st.rerun(scope="fragment")

                    # Split button (only if group has 2+ paragraphs and not first para)
                    if current_group_id:
                        group = find_group(current_group_id)
                        if group and len(group['para_ids']) > 1 and para_id != group['para_ids'][0]:
                            if st.button("✂️", key=f"split_{para_id}", help="Split group here"):
                                split_group_at_paragraph(para_id)
                                st.success("Group split!")
                                st.rerun(scope="fragment")

        # Additional options for quotes
        if para.get('type') == 'quote':
            col_qt1, col_qt2 = st.columns([1, 3])
            with col_qt1:
                quote_options = ["other", "quran", "hadith"]
                current_qt_idx = quote_options.index(quote_type) if quote_type in quote_options else 0
                new_quote_type = st.selectbox(
                    "Quote type",
                    quote_options,
                    index=current_qt_idx,
                    key=f"quote_type_{para_id}",
                    format_func=lambda x: x.capitalize()
                )
                if new_quote_type != quote_type:
                    para['quote_type'] = new_quote_type

        # Build CSS classes for paragraph box
        css_classes = ["paragraph-box"]
        if para.get('reviewed'):
            css_classes.append("reviewed")
        if para.get('potential_delete'):
            css_classes.append("junk-paragraph")
        css_classes.append(f"type-{para.get('type', 'paragraph')}")
        if para.get('type') == 'quote' and para.get('quote_type'):
            css_classes.append(f"quote-{para.get('quote_type')}")

        # Display text with highlights
        keywords = st.session_state.custom_keywords if st.session_state.highlight_keywords else None
        highlighted_text = highlight_text_simple(
            para['text'],
            detected['quran'],
            detected['hadith'],
            keywords=keywords,
            highlight_numbers=st.session_state.highlight_numbers,
            highlight_years=st.session_state.highlight_years
        )

        # Row 2: Paragraph text with DEL and GRP buttons on right
        txt_col, del_col, grp_col = st.columns([7, 1, 1])
        with txt_col:
            st.markdown(
                f'<div id="para-{para_id}" class="{" ".join(css_classes)}">{highlighted_text}</div>',
                unsafe_allow_html=True
            )
        with del_col:
            is_marked = para.get('potential_delete', False)
            del_checked = st.checkbox("🗑 DEL", value=is_marked, key=f"pdel_{para_id}",
                                      help="Mark for deletion")
            if del_checked and not is_marked:
                para['potential_delete'] = True
                para['delete_reason'] = "manual"
                mark_activity(para_id)
                save_progress()
                st.rerun()
            elif not del_checked and is_marked and para.get('delete_reason') == 'manual':
                para['potential_delete'] = False
                mark_activity(para_id)
                save_progress()
                st.rerun()
        with grp_col:
            is_selected = para_id in st.session_state.selected_for_grouping
            # Use checkbox instead of button to avoid white text issue
            grp_label = "📎 GRP ✓" if is_selected else "📎 GRP"
            if st.checkbox(grp_label, value=is_selected, key=f"grp_{para_id}"):
                st.session_state.selected_for_grouping.add(para_id)
            else:
                st.session_state.selected_for_grouping.discard(para_id)

        # Auto-detected references section
        year_refs = detected.get('year', [])
        footnote_refs = detected.get('footnotes', [])
        if detected['quran'] or detected['hadith'] or year_refs or footnote_refs:
            st.markdown("**Auto-detected references:**")

            # Quran references
            for i, ref in enumerate(detected['quran']):
                ref_key = f"quran_{para_id}_{i}"
                col1, col2, col3 = st.columns([0.3, 5, 0.3], gap="small")
                with col1:
                    # Find corresponding ref in paragraph data
                    verified = False
                    if i < len(para['quran_refs']):
                        verified = para['quran_refs'][i].get('verified', False)
                    new_verified = st.checkbox(
                        "",
                        value=verified,
                        key=ref_key,
                        label_visibility="collapsed"
                    )
                    if i < len(para['quran_refs']):
                        if para['quran_refs'][i].get('verified') != new_verified:
                            para['quran_refs'][i]['verified'] = new_verified
                            save_progress()  # Auto-save on verify
                            st.rerun(scope="fragment")  # Instant UI update
                with col2:
                    ref_text = format_quran_ref(ref)
                    quoted = ref.get('quoted_text', '')
                    if quoted:
                        st.markdown(f'🟢 **{ref_text}** - "{quoted[:50]}..."' if len(quoted) > 50 else f'🟢 **{ref_text}** - "{quoted}"')
                    else:
                        st.markdown(f'🟢 **{ref_text}**')
                with col3:
                    if st.button("❌", key=f"del_quran_{para_id}_{i}", help="Delete this reference"):
                        button_logger.info(f"[DELETE_REF] type=quran para={para_id} idx={i} before_count={len(para['quran_refs'])}")
                        if i < len(para['quran_refs']):
                            ref_deleted = para['quran_refs'][i]
                            para['quran_refs'].pop(i)
                            mark_activity(para_id)
                            save_progress()
                            button_logger.info(f"[DELETE_REF] success type=quran para={para_id} after_count={len(para['quran_refs'])} rerun=fragment ref={ref_deleted.get('surah')}:{ref_deleted.get('ayah_start')}")
                            st.rerun(scope="fragment")
                        else:
                            button_logger.error(f"[DELETE_REF] FAILED type=quran para={para_id} idx={i} out_of_bounds list_len={len(para['quran_refs'])}")

            # Hadith references
            for i, ref in enumerate(detected['hadith']):
                ref_key = f"hadith_{para_id}_{i}"
                col1, col2, col3 = st.columns([0.3, 5, 0.3], gap="small")
                with col1:
                    verified = False
                    if i < len(para['hadith_refs']):
                        verified = para['hadith_refs'][i].get('verified', False)
                    new_verified = st.checkbox(
                        "",
                        value=verified,
                        key=ref_key,
                        label_visibility="collapsed"
                    )
                    if i < len(para['hadith_refs']):
                        if para['hadith_refs'][i].get('verified') != new_verified:
                            para['hadith_refs'][i]['verified'] = new_verified
                            save_progress()  # Auto-save on verify
                            st.rerun(scope="fragment")  # Instant UI update
                with col2:
                    ref_text = format_hadith_ref(ref)
                    st.markdown(f'🔵 **{ref_text}**')
                with col3:
                    if st.button("❌", key=f"del_hadith_{para_id}_{i}", help="Delete this reference"):
                        button_logger.info(f"[DELETE_REF] type=hadith para={para_id} idx={i} before_count={len(para['hadith_refs'])}")
                        if i < len(para['hadith_refs']):
                            ref_deleted = para['hadith_refs'][i]
                            para['hadith_refs'].pop(i)
                            mark_activity(para_id)
                            save_progress()
                            button_logger.info(f"[DELETE_REF] success type=hadith para={para_id} after_count={len(para['hadith_refs'])} rerun=fragment ref={ref_deleted.get('collection')}:{ref_deleted.get('number')}")
                            st.rerun(scope="fragment")
                        else:
                            button_logger.error(f"[DELETE_REF] FAILED type=hadith para={para_id} idx={i} out_of_bounds list_len={len(para['hadith_refs'])}")

            # Year/Date references
            for i, ref in enumerate(year_refs):
                ref_key = f"year_{para_id}_{i}"
                col1, col2, col3 = st.columns([0.3, 5, 0.3], gap="small")
                with col1:
                    verified = False
                    if i < len(para.get('year_refs', [])):
                        verified = para['year_refs'][i].get('verified', False)
                    new_verified = st.checkbox(
                        "",
                        value=verified,
                        key=ref_key,
                        label_visibility="collapsed"
                    )
                    if i < len(para.get('year_refs', [])):
                        if para['year_refs'][i].get('verified') != new_verified:
                            para['year_refs'][i]['verified'] = new_verified
                            save_progress()  # Auto-save on verify
                            st.rerun(scope="fragment")  # Instant UI update
                with col2:
                    # Get year text - prefer stored 'text' field, fallback to slicing
                    import re
                    if isinstance(ref, dict):
                        year_text = ref.get('text', '')
                        if not year_text:
                            start = ref.get('start_pos', ref.get('start', 0))
                            end = ref.get('end_pos', ref.get('end', 0))
                            year_text = para['text'][start:end] if start < len(para['text']) else str(ref)
                    else:
                        year_text = para['text'][ref[0]:ref[1]] if ref[0] < len(para['text']) else str(ref)
                    # Extract just the year number for cleaner display
                    year_match = re.search(r'\d{3,4}', year_text)
                    display_text = f"Year: {year_match.group()}" if year_match else year_text
                    st.markdown(f'🩵 **{display_text}**')
                with col3:
                    if st.button("❌", key=f"del_year_{para_id}_{i}", help="Delete this reference"):
                        button_logger.info(f"[DELETE_REF] type=year para={para_id} idx={i} before_count={len(para.get('year_refs', []))}")
                        if i < len(para.get('year_refs', [])):
                            ref_deleted = para['year_refs'][i]
                            para['year_refs'].pop(i)
                            mark_activity(para_id)
                            save_progress()
                            button_logger.info(f"[DELETE_REF] success type=year para={para_id} after_count={len(para['year_refs'])} rerun=fragment")
                            st.rerun(scope="fragment")
                        else:
                            button_logger.error(f"[DELETE_REF] FAILED type=year para={para_id} idx={i} out_of_bounds")

            # Footnote references
            footnote_refs = detected.get('footnotes', [])
            for i, ref in enumerate(footnote_refs):
                ref_key = f"footnote_{para_id}_{i}"
                col1, col2, col3 = st.columns([0.3, 5, 0.3], gap="small")
                with col1:
                    verified = False
                    if i < len(para.get('footnote_refs', [])):
                        verified = para['footnote_refs'][i].get('verified', False)
                    new_verified = st.checkbox(
                        "",
                        value=verified,
                        key=ref_key,
                        label_visibility="collapsed"
                    )
                    if i < len(para.get('footnote_refs', [])):
                        if para['footnote_refs'][i].get('verified') != new_verified:
                            para['footnote_refs'][i]['verified'] = new_verified
                            save_progress()  # Auto-save on verify
                            st.rerun(scope="fragment")  # Instant UI update
                with col2:
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
                        display_text = linked[:100] + '...' if len(linked) > 100 else linked
                        st.markdown(f'{type_emoji} **{marker}** → _{display_text}_')
                    else:
                        st.markdown(f'❓ **{marker}** _(unlinked footnote)_')
                with col3:
                    if st.button("❌", key=f"del_footnote_{para_id}_{i}", help="Delete this reference"):
                        button_logger.info(f"[DELETE_REF] type=footnote para={para_id} idx={i} before_count={len(para.get('footnote_refs', []))}")
                        if i < len(para.get('footnote_refs', [])):
                            ref_deleted = para['footnote_refs'][i]
                            para['footnote_refs'].pop(i)
                            mark_activity(para_id)
                            save_progress()
                            button_logger.info(f"[DELETE_REF] success type=footnote para={para_id} after_count={len(para['footnote_refs'])} rerun=fragment")
                            st.rerun(scope="fragment")
                        else:
                            button_logger.error(f"[DELETE_REF] FAILED type=footnote para={para_id} idx={i} out_of_bounds")

        # LLM Extraction Tags (inline display with pill styling)
        if para.get('extraction_status') == 'extracted':
            concepts = para.get('concepts', [])
            verse_aspects = para.get('verse_aspects', [])
            people = para.get('people', [])
            places = para.get('places', [])
            islamic_terms = para.get('islamic_terms', [])

            if concepts or verse_aspects or people or places or islamic_terms:
                st.markdown("**LLM Extracted:**")

                # Build inline tag display using CSS classes
                tags_html = ['<div class="llm-tags">']

                # Concepts (teal tags)
                for c in concepts:
                    tags_html.append(f'<span class="llm-tag tag-concept">{c}</span>')

                # Verse aspects (purple tags)
                for va in verse_aspects:
                    ref = va.get('ref', '?')
                    aspect = va.get('aspect', '?')
                    interp = va.get('interpretation', '')
                    title = f'{ref}: {interp}' if interp else ref
                    tags_html.append(f'<span class="llm-tag tag-aspect" title="{title}">{ref}→{aspect}</span>')

                # People (red tags)
                for p in people:
                    tags_html.append(f'<span class="llm-tag tag-people">👤 {p}</span>')

                # Places (blue tags)
                for pl in places:
                    tags_html.append(f'<span class="llm-tag tag-places">📍 {pl}</span>')

                # Islamic terms (amber tags)
                for t in islamic_terms:
                    tags_html.append(f'<span class="llm-tag tag-hadith">{t}</span>')

                tags_html.append('</div>')
                st.markdown(''.join(tags_html), unsafe_allow_html=True)

        elif para.get('extraction_status') == 'error':
            st.caption(f"⚠️ Extraction error: {para.get('extraction_error', 'Unknown')[:50]}")

        # Manual tag section with + button
        add_ref_key = f"show_add_ref_{para_id}"
        tag_type = None  # Initialize

        # Show + button or the form
        if not st.session_state.get(add_ref_key, False):
            st.button(
                "➕ Add Reference",
                key=f"btn_add_ref_{para_id}",
                help="Add Quran, Hadith, Seerah or other reference",
                on_click=toggle_add_ref_form,
                args=(para_id,)
            )
        else:
            st.markdown("**Add Reference:** *(select type below)*")
            close_col, type_col = st.columns([1, 5])
            with close_col:
                st.button(
                    "✖",
                    key=f"close_add_ref_{para_id}",
                    help="Close",
                    on_click=close_add_ref_form,
                    args=(para_id,)
                )

            col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

            with col1:
                # Remember last selected type for adding multiple refs
                last_type_key = f"last_tag_type_{para_id}"
                default_idx = 0
                if last_type_key in st.session_state:
                    options = ["Quran", "Hadith", "Seerah", "Other Book"]
                    if st.session_state[last_type_key] in options:
                        default_idx = options.index(st.session_state[last_type_key])

                tag_type = st.selectbox(
                    "Type",
                    ["Quran", "Hadith", "Seerah", "Other Book"],
                    index=default_idx,
                    key=f"tag_type_{para_id}",
                    help="Select reference type"
                )
                st.session_state[last_type_key] = tag_type

            if tag_type == "Quran":
                with col2:
                    surah = st.number_input(
                        "Surah",
                        min_value=1,
                        max_value=114,
                        value=1,
                        key=f"surah_{para_id}"
                    )
                with col3:
                    ayah_start = st.number_input(
                        "Ayah (from)",
                        min_value=1,
                        value=1,
                        key=f"ayah_start_{para_id}"
                    )
                with col4:
                    ayah_end = st.number_input(
                        "Ayah (to)",
                        min_value=0,
                        value=0,
                        help="Leave 0 for single ayah",
                        key=f"ayah_end_{para_id}"
                    )

                if st.button("✓ Add", key=f"add_quran_{para_id}", type="primary"):
                    new_ref = {
                        'surah': surah,
                        'ayah_start': ayah_start,
                        'ayah_end': ayah_end if ayah_end > 0 else None,
                        'quoted_text': '',
                        'detection': 'manual',
                        'verified': True
                    }
                    para['quran_refs'].append(new_ref)
                    para['reviewed'] = True
                    mark_activity(para_id)
                    save_progress()
                    st.success(f"Added Quran {surah}:{ayah_start}" + (f"-{ayah_end}" if ayah_end > 0 else ""))
                    st.rerun(scope="fragment")

            elif tag_type == "Hadith":
                with col2:
                    collection = st.selectbox(
                        "Collection",
                        get_collection_list(),
                        key=f"collection_{para_id}"
                    )
                with col3:
                    hadith_num = st.number_input(
                        "Hadith No.",
                        min_value=1,
                        value=1,
                        key=f"hadith_num_{para_id}"
                    )
                with col4:
                    if collection == "Other":
                        custom_collection = st.text_input(
                            "Name",
                            key=f"custom_collection_{para_id}",
                            placeholder="Collection name"
                        )
                    else:
                        custom_collection = None

                if st.button("✓ Add", key=f"add_hadith_{para_id}", type="primary"):
                    final_collection = custom_collection if collection == "Other" and custom_collection else collection
                    if collection == "Other" and not custom_collection:
                        st.error("Please enter a collection name")
                    else:
                        new_ref = {
                            'collection': final_collection,
                            'number': hadith_num,
                            'narrator': None,
                            'detection': 'manual',
                            'verified': True
                        }
                        para['hadith_refs'].append(new_ref)
                        para['reviewed'] = True
                        mark_activity(para_id)
                        save_progress()
                        st.success(f"Added {final_collection}, No. {hadith_num}")
                        st.rerun(scope="fragment")

            elif tag_type == "Seerah":
                with col2:
                    seerah_note = st.text_input(
                        "Seerah note",
                        key=f"seerah_note_{para_id}",
                        placeholder="Enter reference note"
                    )
                if st.button("✓ Add", key=f"add_seerah_{para_id}", type="primary"):
                    if 'seerah_refs' not in para:
                        para['seerah_refs'] = []
                    para['seerah_refs'].append({
                        'note': seerah_note,
                        'detection': 'manual',
                        'verified': True
                    })
                    para['reviewed'] = True
                    mark_activity(para_id)
                    save_progress()
                    st.success("Added Seerah reference")
                    st.rerun(scope="fragment")

            elif tag_type == "Other Book":
                with col2:
                    book_name = st.text_input(
                        "Book Name",
                        key=f"other_book_name_{para_id}",
                        placeholder="Book name"
                    )
                with col3:
                    page_or_ref = st.text_input(
                        "Page/Ref",
                        key=f"other_book_ref_{para_id}",
                        placeholder="Page 45"
                    )

                if st.button("✓ Add", key=f"add_other_book_{para_id}", type="primary"):
                    if not book_name:
                        st.error("Please enter a book name")
                    else:
                        if 'other_book_refs' not in para:
                            para['other_book_refs'] = []
                        para['other_book_refs'].append({
                            'book_name': book_name,
                            'reference': page_or_ref,
                            'detection': 'manual',
                            'verified': True
                        })
                        para['reviewed'] = True
                        mark_activity(para_id)
                        save_progress()
                        st.success(f"Added: {book_name}")
                        st.rerun(scope="fragment")

        # Display manually added references with delete buttons
        manual_quran = [r for r in para.get('quran_refs', []) if r.get('detection') == 'manual']
        manual_hadith = [r for r in para.get('hadith_refs', []) if r.get('detection') == 'manual']
        manual_seerah = para.get('seerah_refs', [])
        manual_other_books = para.get('other_book_refs', [])

        if manual_quran or manual_hadith or manual_seerah or manual_other_books:
            st.markdown("**Added references:**")

            # CSS to make delete button tight next to text
            st.markdown('''<style>
                .ref-row { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
                .ref-text { flex: 1; }
                .ref-del button { padding: 0 6px !important; min-height: 24px !important; font-size: 12px !important; }
            </style>''', unsafe_allow_html=True)

            # Quran refs with tight delete button
            for i, ref in enumerate(manual_quran):
                ayah_text = f"{ref['surah']}:{ref['ayah_start']}"
                if ref.get('ayah_end'):
                    ayah_text += f"-{ref['ayah_end']}"
                ref_col, del_col = st.columns([0.85, 0.15], gap="small")
                with ref_col:
                    st.markdown(f"🟢 **Quran {ayah_text}**")
                with del_col:
                    # Unique key includes surah and ayah info
                    ref_key = f"{ref['surah']}_{ref['ayah_start']}_{ref.get('ayah_end', 0)}"
                    if st.button("❌", key=f"del_quran_{para_id}_{i}_{ref_key}", help="Delete"):
                        para['quran_refs'] = [r for r in para.get('quran_refs', []) if r != ref]
                        mark_activity(para_id)
                        save_progress()
                        st.rerun(scope="fragment")

            # Hadith refs with tight delete button
            for i, ref in enumerate(manual_hadith):
                ref_col, del_col = st.columns([0.85, 0.15], gap="small")
                with ref_col:
                    st.markdown(f"🔵 **{ref.get('collection', 'Unknown')}**, No. {ref.get('number', '?')}")
                with del_col:
                    # Unique key includes collection and number
                    ref_key = f"{ref.get('collection', 'x')}_{ref.get('number', 0)}"
                    if st.button("❌", key=f"del_hadith_{para_id}_{i}_{ref_key}", help="Delete"):
                        para['hadith_refs'] = [r for r in para.get('hadith_refs', []) if r != ref]
                        mark_activity(para_id)
                        save_progress()
                        st.rerun(scope="fragment")

            # Seerah refs with tight delete button
            for i, ref in enumerate(manual_seerah):
                ref_col, del_col = st.columns([0.85, 0.15], gap="small")
                with ref_col:
                    st.markdown(f"📜 **Seerah**: {ref.get('note', '')}")
                with del_col:
                    # Unique key includes note hash
                    ref_key = hash(ref.get('note', ''))
                    if st.button("❌", key=f"del_seerah_{para_id}_{i}_{ref_key}", help="Delete"):
                        para['seerah_refs'] = [r for r in para.get('seerah_refs', []) if r != ref]
                        mark_activity(para_id)
                        save_progress()
                        st.rerun(scope="fragment")

            # Other book refs with tight delete button
            for i, ref in enumerate(manual_other_books):
                ref_col, del_col = st.columns([0.85, 0.15], gap="small")
                with ref_col:
                    st.markdown(f"📚 **{ref.get('book_name', 'Unknown')}**: {ref.get('reference', '')}")
                with del_col:
                    # Unique key includes book name and reference
                    ref_key = hash(f"{ref.get('book_name', '')}_{ref.get('reference', '')}")
                    if st.button("❌", key=f"del_book_{para_id}_{i}_{ref_key}", help="Delete"):
                        para['other_book_refs'] = [r for r in para.get('other_book_refs', []) if r != ref]
                        mark_activity(para_id)
                        save_progress()
                        st.rerun(scope="fragment")

        st.divider()




def render_portal():
    """Render role-based portal/dashboard with book library."""
    role = st.session_state.get('user_role', 'annotator')
    user = st.session_state.get('current_user', 'guest')

    # Custom header banner with Islamic design
    role_labels = {'admin': ('🔴 Admin', 'role-admin'), 'annotator': ('🟢 Annotator', 'role-annotator'), 'reviewer': ('🔵 Reviewer', 'role-reviewer')}
    role_label, role_class = role_labels.get(role, ('⚪ Guest', ''))

    st.markdown(f'''
    <div class="custom-header pattern-bg">
        <h1>Book Annotation Tool</h1>
    </div>
    ''', unsafe_allow_html=True)

    # Role badge with styling
    st.markdown(f'''
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <span class="{role_class}">{role_label} Portal</span>
        <span style="color: #5d6d7e; font-size: 0.9rem;">Welcome, <strong>{user}</strong></span>
    </div>
    ''', unsafe_allow_html=True)

    st.markdown('<div class="islamic-divider"></div>', unsafe_allow_html=True)

    # Get library books and saved progress
    library_books = get_library_books()
    saved_books = get_saved_books()

    if role == 'admin':
        # ============= ADMIN VIEW =============
        st.subheader("📊 Dashboard")

        # Check for newly approved books (within last 24 hours)
        from datetime import timedelta
        new_approvals = []
        for book in library_books:
            if book.get('status') == 'approved' and book.get('approved_at'):
                try:
                    approved_at = datetime.fromisoformat(book['approved_at'])
                    if datetime.now() - approved_at < timedelta(hours=24):
                        new_approvals.append(book)
                except:
                    pass

        if new_approvals:
            st.success(f"🔔 **{len(new_approvals)} New Approval(s)!** - Ready for JSON export")
            for book in new_approvals:
                st.write(f"  ✅ {book['title']} (by {book.get('approved_by', '?')})")
            st.divider()

        # Stats from library - clear breakdown
        not_started = len([b for b in library_books if b.get('status') == 'pending' and not b.get('locked_by')])
        with_annotator = len([b for b in library_books if b.get('status') == 'in_progress' or b.get('locked_by')])
        pending_approval = len([b for b in library_books if b.get('status') == 'submitted'])
        approved = len([b for b in library_books if b.get('status') == 'approved'])

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("📚 Total", len(library_books))
        with col2:
            st.metric("⚪ Not Started", not_started)
        with col3:
            st.metric("🟢 Annotating", with_annotator)
        with col4:
            st.metric("🔵 To Approve", pending_approval)
        with col5:
            st.metric("✅ Done", approved)

        st.divider()

        # Add new book to library
        st.subheader("📤 Add Book to Library")
        col1, col2 = st.columns(2)
        with col1:
            docx_file = st.file_uploader("📄 DOCX File (required)", type=['docx'], key='lib_docx')
        with col2:
            pdf_file = st.file_uploader("📕 PDF File (required)", type=['pdf'], key='lib_pdf')

        # Auto-extract title from DOCX filename
        default_title = ""
        if docx_file:
            default_title = docx_file.name.replace('.docx', '').replace('_', ' ').replace('-', ' ')

        book_title = st.text_input("Book Title (auto-filled from filename)", value=default_title, key="new_book_title")

        # Show status and button
        if docx_file and pdf_file:
            st.success("✅ Both files uploaded - ready to add!")
            if st.button("📥 Add to Library", type="primary"):
                # Use title or filename
                title = book_title.strip() or default_title or "Untitled Book"

                # Create slug from title
                import re
                slug = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
                book_dir = os.path.join(BOOKS_DIR, slug)
                os.makedirs(book_dir, exist_ok=True)

                # Save files
                with open(os.path.join(book_dir, 'document.docx'), 'wb') as f:
                    f.write(docx_file.read())
                with open(os.path.join(book_dir, 'document.pdf'), 'wb') as f:
                    f.write(pdf_file.read())

                # Save metadata
                meta = {
                    "title": title,
                    "status": "pending",
                    "locked_by": None,
                    "locked_at": None,
                    "progress": 0,
                    "created_at": datetime.now().isoformat()
                }
                save_meta(slug, meta)
                st.success(f"✅ Added '{title}' to library!")
                st.rerun()
        elif docx_file or pdf_file:
            missing = []
            if not docx_file:
                missing.append("DOCX")
            if not pdf_file:
                missing.append("PDF")
            st.warning(f"⚠️ Please upload: {', '.join(missing)}")

        st.divider()

        # Book Library Table
        st.subheader("📚 Book Library")
        if library_books:
            # Table header
            cols = st.columns([3, 1, 1, 1, 1, 0.5])
            cols[0].markdown("**Book Name**")
            cols[1].markdown("**PDF**")
            cols[2].markdown("**DOCX**")
            cols[3].markdown("**Status**")
            cols[4].markdown("**Action**")
            cols[5].markdown("**Del**")

            for book in library_books:
                cols = st.columns([3, 1, 1, 1, 1, 0.5])
                status = book.get('status', 'pending')
                status_icons = {
                    'pending': '⚪',
                    'in_progress': f"🔵 {book.get('progress', 0)}%",
                    'submitted': '🟡 Review',
                    'approved': '✅ Done'
                }

                cols[0].write(book.get('title', book['folder']))
                cols[1].write("✅" if book.get('has_pdf') else "❌")
                cols[2].write("✅" if book.get('has_docx') else "❌")
                cols[3].write(status_icons.get(status, status))

                # Action button
                if status == 'approved':
                    if cols[4].button("📥", key=f"dl_{book['folder']}", help="Download JSON"):
                        st.info(f"Export JSON for {book['title']}")
                else:
                    if cols[4].button("👁", key=f"view_{book['folder']}", help="View"):
                        with st.spinner(f"Loading {book['title']}..."):
                            load_book_from_library(book['folder'])
                        st.rerun()

                # Delete button
                if cols[5].button("🗑", key=f"del_{book['folder']}", help="Delete"):
                    with st.spinner("Deleting..."):
                        delete_book(book['folder'])
                    st.rerun()
        else:
            st.info("No books in library. Add one above.")

        # ============= APPROVAL SECTION =============
        submitted_books = [b for b in library_books if b.get('status') == 'submitted']
        if submitted_books:
            st.divider()
            st.subheader(f"🔵 Pending Approval ({len(submitted_books)} books)")

            # Initialize selection state
            if 'selected_for_approval' not in st.session_state:
                st.session_state.selected_for_approval = set()

            # Bulk actions
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                if st.button("☑️ Select All"):
                    st.session_state.selected_for_approval = {b['folder'] for b in submitted_books}
                    st.rerun()
            with col2:
                if st.button("☐ Clear Selection"):
                    st.session_state.selected_for_approval = set()
                    st.rerun()
            with col3:
                selected_count = len(st.session_state.selected_for_approval)
                if selected_count > 0:
                    if st.button(f"✅ Approve Selected ({selected_count})", type="primary"):
                        with st.spinner(f"Approving {selected_count} book(s)..."):
                            for folder in list(st.session_state.selected_for_approval):
                                approve_book(folder)
                            st.session_state.selected_for_approval = set()
                        st.success(f"✅ Approved {selected_count} book(s)!")
                        st.rerun()

            # List submitted books with checkboxes
            for book in submitted_books:
                col1, col2, col3, col4 = st.columns([0.5, 3, 1, 1])
                with col1:
                    is_selected = book['folder'] in st.session_state.selected_for_approval
                    if st.checkbox("", value=is_selected, key=f"sel_{book['folder']}", label_visibility="collapsed"):
                        st.session_state.selected_for_approval.add(book['folder'])
                    else:
                        st.session_state.selected_for_approval.discard(book['folder'])
                with col2:
                    st.write(f"**{book['title']}**")
                    st.caption(f"By: {book.get('annotated_by', '?')} | Submitted: {book.get('submitted_at', '?')[:10] if book.get('submitted_at') else '?'}")
                with col3:
                    if st.button("👁 View", key=f"view_sub_{book['folder']}"):
                        with st.spinner(f"Loading {book['title']}..."):
                            load_book_from_library(book['folder'])
                        st.rerun()
                with col4:
                    if st.button("✅", key=f"approve_{book['folder']}", help="Approve"):
                        with st.spinner("Approving..."):
                            approve_book(book['folder'])
                        st.success(f"✅ Approved: {book['title']}")
                        st.rerun()

        # Approved books section
        approved_books = [b for b in library_books if b.get('status') == 'approved']
        if approved_books:
            st.divider()
            st.subheader("✅ Approved Books (Ready for Export)")
            for book in approved_books:
                st.write(f"✅ **{book['title']}**")
                st.caption(f"Approved by: {book.get('approved_by', '?')}")

    elif role == 'annotator':
        # ============= ANNOTATOR VIEW =============
        st.subheader("📚 Available Books")

        # Check if annotator is currently working on a book
        current_book = st.session_state.get('current_book_folder')
        my_locked_book = None

        for book in library_books:
            if book.get('locked_by') == user:
                my_locked_book = book
                break

        if my_locked_book:
            st.info(f"📖 Currently working on: **{my_locked_book['title']}** ({my_locked_book.get('progress', 0)}%)")
            if st.button("📂 Continue Working", type="primary"):
                with st.spinner(f"Loading {my_locked_book['title']}..."):
                    load_book_from_library(my_locked_book['folder'])
                st.rerun()
            if st.button("🔓 Release Book"):
                with st.spinner("Releasing..."):
                    release_lock(my_locked_book['folder'])
                st.rerun()
            st.divider()

        # Show all books with status
        st.markdown("**Select a book to annotate:**")

        # Table header
        cols = st.columns([3, 2, 2, 1])
        cols[0].markdown("**Book**")
        cols[1].markdown("**Progress**")
        cols[2].markdown("**Status**")
        cols[3].markdown("**Action**")

        for book in library_books:
            if book.get('status') == 'approved':
                continue  # Skip approved books

            cols = st.columns([3, 2, 2, 1])
            status = book.get('status', 'pending')
            locked_by = book.get('locked_by')
            progress = book.get('progress', 0)

            cols[0].write(book.get('title', book['folder']))

            # Progress bar
            progress_bar = '█' * (progress // 10) + '░' * (10 - progress // 10)
            cols[1].write(f"{progress_bar} {progress}%")

            # Status
            if locked_by == user:
                cols[2].write("🔒 **Your book**")
            elif locked_by:
                cols[2].write(f"🔒 {locked_by}")
            elif status == 'submitted':
                cols[2].write("🟡 In Review")
            else:
                cols[2].write("🟢 Available")

            # Action
            if locked_by == user:
                if cols[3].button("📂", key=f"open_{book['folder']}", help="Continue"):
                    with st.spinner("Loading..."):
                        load_book_from_library(book['folder'])
                    st.rerun()
            elif locked_by is None and status not in ['submitted', 'approved']:
                if cols[3].button("📖", key=f"pick_{book['folder']}", help="Pick"):
                    with st.spinner("Loading..."):
                        if can_lock_book(book['folder'], user):
                            load_book_from_library(book['folder'])
                            st.rerun()
                        else:
                            st.error("Book is locked by another user")

    # Reviewer role removed - Admin handles approvals directly


def load_auth_config():
    """Load authentication configuration."""
    config_path = os.path.join(DATA_DIR, 'users.yaml')
    if not os.path.exists(config_path):
        # Fallback for local development
        config_path = os.path.join(os.path.dirname(__file__), 'data', 'users.yaml')

    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    return None


def main():
    """Main application entry point."""
    # Load auth config
    config = load_auth_config()

    if config:
        # Initialize authenticator
        authenticator = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days']
        )

        # Show styled login header
        if not st.session_state.get('authentication_status'):
            st.markdown('''
            <style>
            /* Center login form with max-width */
            [data-testid="stForm"] {
                max-width: 400px !important;
                margin: 0 auto !important;
            }
            section[data-testid="stSidebar"] { display: none !important; }
            </style>
            <div style="text-align: center; padding: 2rem 0; max-width: 400px; margin: 0 auto;">
                <h1 style="color: #f1f5f9; font-size: 2rem;">Book Annotation Tool</h1>
            </div>
            ''', unsafe_allow_html=True)

        # Login form (new API: location as keyword argument)
        authenticator.login(location='main')

        if st.session_state.get('authentication_status') is False:
            st.error('Username/password is incorrect')
            st.stop()
        elif st.session_state.get('authentication_status') is None:
            st.markdown('<p style="text-align: center; color: #94a3b8; margin-top: 1rem;">Please sign in to continue</p>', unsafe_allow_html=True)
            st.stop()

        # Get auth info from session state
        name = st.session_state.get('name', '')
        username = st.session_state.get('username', '')

        # Store user info in session state
        st.session_state.current_user = username
        st.session_state.user_role = config['credentials']['usernames'][username].get('role', 'annotator')

        # Show logout button in sidebar
        with st.sidebar:
            st.write(f"**User:** {name}")
            st.write(f"**Role:** {st.session_state.user_role.capitalize()}")
            authenticator.logout(location='sidebar')
            st.divider()
    else:
        # No auth config, skip login
        st.session_state.current_user = 'guest'
        st.session_state.user_role = 'admin'

    init_session_state()

    # Auto-restore book from query params (navigation persistence)
    if not st.session_state.file_uploaded:
        try:
            # Try modern API first
            book_from_url = st.query_params.get("book")
        except AttributeError:
            # Fallback for older Streamlit versions
            params = st.experimental_get_query_params()
            book_from_url = params.get("book", [None])[0]

        if book_from_url:
            # User had a book open before refresh - restore it
            try:
                with st.spinner(f"Restoring your session..."):
                    load_book_from_library(book_from_url)
                    logger.info(f"[NAV_RESTORE] book={book_from_url}")
                st.rerun()
            except Exception as e:
                # Book not found or error - clear query params and show portal
                logger.error(f"[NAV_RESTORE] failed for book={book_from_url}, error={str(e)}")
                try:
                    st.query_params.clear()
                except AttributeError:
                    st.experimental_set_query_params()
                st.warning(f"Could not restore session for '{book_from_url}'. Showing dashboard.")

    # Show role-based portal if no book loaded
    if not st.session_state.file_uploaded:
        render_portal()
        return

    # Book is loaded - show annotation view
    # Back button to return to dashboard
    back_col, title_col = st.columns([1, 5])
    with back_col:
        if st.button("← Back to Dashboard"):
            with st.spinner("Returning..."):
                # Save progress before leaving
                save_progress()
                # Clear ALL book-related state to return to portal
                st.session_state.file_uploaded = False
                st.session_state.current_book_folder = None
                st.session_state.paragraphs = []
                st.session_state.groups = []
                st.session_state.detected_refs = {}
                st.session_state.pdf_pages = []
                st.session_state.pdf_loaded = False
                st.session_state.book_title = ''
                st.session_state.author = 'Maulana Wahiduddin Khan'
                st.session_state.current_group_index = 0
                st.session_state.book_slug = ''

                # Clear query params for navigation persistence
                try:
                    st.query_params.clear()
                    logger.info("[NAV_RESTORE] panel=dashboard")
                except AttributeError:
                    # Fallback for older Streamlit versions
                    st.experimental_set_query_params()
                    logger.info("[NAV_RESTORE] panel=dashboard")
            st.rerun()

    render_sidebar()
    render_header()
    render_progress()

    # Check for auto-save (every 30 seconds after activity)
    check_auto_save()

    # Handle scroll to paragraph (if set from previous action)
    scroll_target = st.session_state.get('scroll_to_para')
    if scroll_target:
        # Use components.html which CAN execute JavaScript (unlike st.markdown)
        components.html(
            f'''<script>
            console.log("[SCROLL] Starting scroll to para-{scroll_target}");
            var attempts = 0;
            var maxAttempts = 10;
            var interval = setInterval(function(){{
                attempts++;
                console.log("[SCROLL] Attempting to find para-{scroll_target}, attempt " + attempts);
                var el = parent.document.getElementById("para-{scroll_target}");
                if(el) {{
                    el.scrollIntoView({{behavior: "smooth", block: "center"}});
                    console.log("[SCROLL] Found and scrolled to para-{scroll_target}");
                    clearInterval(interval);
                }} else if(attempts >= maxAttempts) {{
                    clearInterval(interval);
                    console.log("[SCROLL] FAILED to find para-{scroll_target} after 10 attempts");
                }}
            }}, 100);  // Check every 100ms
            </script>''',
            height=0
        )
        st.session_state.scroll_to_para = None  # Clear after use

    # Handle scroll to group (if set from sidebar navigation)
    scroll_group = st.session_state.get('scroll_to_group')
    if scroll_group:
        components.html(
            f'''<script>
            setTimeout(function(){{
                var el = parent.document.getElementById("group-{scroll_group}");
                if(el) {{
                    el.scrollIntoView({{behavior: "smooth", block: "start"}});
                    el.style.border = "3px solid #3b82f6";
                    setTimeout(function(){{ el.style.border = "1px solid #e2e8f0"; }}, 2000);
                }}
            }}, 300);
            </script>''',
            height=0
        )
        st.session_state.scroll_to_group = None  # Clear after use

    # Jump to last worked paragraph button
    last_para = st.session_state.get('last_worked_para')
    if last_para:
        jump_col1, jump_col2 = st.columns([1, 5])
        with jump_col1:
            if st.button(f"📍 Jump to Para {last_para}", help="Go to last edited paragraph"):
                button_logger.info(f"[JUMP_TO_PARA] triggered para={last_para}")
                st.session_state.scroll_to_para = last_para
                st.rerun()  # Rerun to inject the scroll JS

    # Junk cleanup panel (only in paragraph view)
    if st.session_state.get('view_mode') != "Group Dashboard":
        render_junk_approval()

    # Render content based on view mode
    if st.session_state.get('view_mode') == "Group Dashboard":
        # Show world-class group dashboard
        render_group_dashboard()
    else:
        # Render all paragraphs (by groups if available)
        if st.session_state.get('groups'):
            # Render by groups
            for i in range(len(st.session_state.groups)):
                render_group(i)
        else:
            # Fallback: render paragraphs without groups
            for i in range(len(st.session_state.paragraphs)):
                render_paragraph(i)

    # Status workflow buttons (for annotator/reviewer)
    st.markdown("---")
    book_status = st.session_state.get('book_status', 'pending')

    status_col1, status_col2, status_col3 = st.columns([2, 2, 2])
    with status_col1:
        st.caption(f"Status: **{book_status.replace('_', ' ').title()}**")

    if st.session_state.user_role == 'annotator' and book_status in ['pending', 'needs_revision']:
        with status_col2:
            if st.button("✓ Submit for Review", type="primary"):
                with st.spinner("Submitting..."):
                    st.session_state.book_status = 'annotated'
                    save_progress()
                st.success("Submitted for review!")
                st.rerun()

    if st.session_state.user_role == 'reviewer' and book_status == 'annotated':
        with status_col2:
            if st.button("✓ Approve", type="primary"):
                with st.spinner("Approving..."):
                    st.session_state.book_status = 'approved'
                    save_progress()
                st.success("Approved!")
                st.rerun()
        with status_col3:
            if st.button("↩ Return for Revision"):
                with st.spinner("Processing..."):
                    st.session_state.book_status = 'needs_revision'
                    save_progress()
                st.warning("Returned for revision")
                st.rerun()

    # Footer with summary
    st.markdown("---")
    reviewed, total = get_progress()
    quran_count = sum(len(p.get('quran_refs', [])) for p in st.session_state.paragraphs)
    hadith_count = sum(len(p.get('hadith_refs', [])) for p in st.session_state.paragraphs)

    # Count structure types
    chapter_count = sum(1 for p in st.session_state.paragraphs if p.get('type') == 'chapter_heading' and not p.get('grouped_into'))
    quote_count = sum(1 for p in st.session_state.paragraphs if p.get('type') == 'quote' and not p.get('grouped_into'))

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total", total)
    with col2:
        st.metric("Reviewed", reviewed)
    with col3:
        st.metric("Chapters", chapter_count)
    with col4:
        st.metric("Quotes", quote_count)
    with col5:
        st.metric("Quran Refs", quran_count)
    with col6:
        st.metric("Hadith Refs", hadith_count)


if __name__ == "__main__":
    main()
