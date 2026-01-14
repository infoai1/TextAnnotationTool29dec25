"""
Islamic Text Annotation Tool - Main Streamlit Application

A tool for annotating Quran and Hadith references in DOCX documents.
Run with: streamlit run app.py
"""

import json
from datetime import datetime
from typing import TypedDict

import streamlit as st

from config import app_config, get_colors
from extractors import parse_docx, detect_quran_refs, detect_hadith_refs
from utils.highlighter import highlight_references, HighlightConfig


# === Type Definitions ===

class QuranRefDict(TypedDict):
    surah: int
    ayah_start: int
    ayah_end: int | None
    quoted_text: str
    detection: str
    verified: bool


class HadithRefDict(TypedDict):
    collection: str | None
    number: int | None
    detection: str
    verified: bool


class ParagraphData(TypedDict):
    id: int
    text: str
    reviewed: bool
    quran_refs: list[QuranRefDict]
    hadith_refs: list[HadithRefDict]
    manual_notes: str


# === Cached Functions (Performance Optimization) ===

@st.cache_data(show_spinner="Parsing document...")
def load_document(file_bytes: bytes) -> list[str]:
    """Parse DOCX and return paragraphs. Cached to avoid re-parsing on rerun."""
    return parse_docx(file_bytes)


@st.cache_data(show_spinner="Detecting references...")
def detect_all_references(paragraphs: tuple[str, ...]) -> dict:
    """
    Detect all references in all paragraphs. Cached for performance.

    Args:
        paragraphs: Tuple of paragraph texts (tuple for hashability)

    Returns:
        Dict with 'quran' and 'hadith' keys, each containing list of refs per paragraph
    """
    quran_refs = []
    hadith_refs = []

    for para in paragraphs:
        if app_config.enable_quran_detection:
            quran_refs.append(detect_quran_refs(para))
        else:
            quran_refs.append([])

        if app_config.enable_hadith_detection:
            hadith_refs.append(detect_hadith_refs(para))
        else:
            hadith_refs.append([])

    return {"quran": quran_refs, "hadith": hadith_refs}


# === Session State Initialization ===

def init_session_state():
    """Initialize session state with defaults. Only stores user-generated data."""
    if "reviews" not in st.session_state:
        st.session_state.reviews = {}  # {para_id: bool}

    if "rejected_refs" not in st.session_state:
        st.session_state.rejected_refs = set()  # {(para_id, ref_type, ref_idx)}

    if "manual_tags" not in st.session_state:
        st.session_state.manual_tags = {}  # {para_id: [tags]}

    if "book_title" not in st.session_state:
        st.session_state.book_title = ""

    if "annotator_name" not in st.session_state:
        st.session_state.annotator_name = ""


# === UI Components ===

def render_header():
    """Render the app header with upload and metadata inputs."""
    st.title(app_config.app_title)

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload DOCX file",
            type=["docx"],
            help="Upload a Word document to annotate"
        )

    with col2:
        st.session_state.book_title = st.text_input(
            "Book Title",
            value=st.session_state.book_title,
            placeholder="Enter book title"
        )
        st.session_state.annotator_name = st.text_input(
            "Annotator",
            value=st.session_state.annotator_name,
            placeholder="Your name"
        )

    return uploaded_file


def render_progress_bar(total: int, reviewed: int):
    """Render progress indicator."""
    if not app_config.enable_progress_tracking:
        return

    progress = reviewed / total if total > 0 else 0
    st.progress(progress, text=f"Progress: {reviewed}/{total} paragraphs reviewed")


def render_paragraph(
    para_id: int,
    text: str,
    quran_refs: list,
    hadith_refs: list,
):
    """
    Render a single paragraph with its references and controls.

    Args:
        para_id: Paragraph index
        text: Paragraph text
        quran_refs: List of QuranReference objects
        hadith_refs: List of HadithReference objects
    """
    colors = get_colors()
    is_reviewed = st.session_state.reviews.get(para_id, False)

    # Container styling based on review status
    bg_color = colors.reviewed_bg if is_reviewed else colors.pending_bg
    border_color = "#28a745" if is_reviewed else "#dee2e6"

    with st.container():
        st.markdown(
            f"""<div style="
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1rem;
            ">""",
            unsafe_allow_html=True
        )

        # Paragraph header
        status_icon = "✓" if is_reviewed else "○"
        st.markdown(f"**Paragraph {para_id + 1}** {status_icon}")

        # Highlighted text
        if app_config.enable_auto_highlight:
            config = HighlightConfig(
                quran_bg_color=colors.quran_bg,
                quran_text_color=colors.quran_text,
                hadith_bg_color=colors.hadith_bg,
                hadith_text_color=colors.hadith_text,
            )
            highlighted = highlight_references(text, quran_refs, hadith_refs, config)
            st.markdown(highlighted, unsafe_allow_html=True)
        else:
            st.write(text)

        # Auto-detected references section
        if quran_refs or hadith_refs:
            st.markdown("**Auto-detected:**")

            # Quran references
            for idx, ref in enumerate(quran_refs):
                ref_key = (para_id, "quran", idx)
                is_accepted = ref_key not in st.session_state.rejected_refs

                ayah_str = f"{ref.surah}:{ref.ayah_start}"
                if ref.ayah_end:
                    ayah_str += f"-{ref.ayah_end}"

                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    if st.checkbox(
                        "Accept",
                        value=is_accepted,
                        key=f"quran_{para_id}_{idx}",
                        label_visibility="collapsed"
                    ):
                        st.session_state.rejected_refs.discard(ref_key)
                    else:
                        st.session_state.rejected_refs.add(ref_key)

                with col2:
                    st.markdown(
                        f'<span style="color: {colors.quran_text};">📗 Quran {ayah_str}</span>',
                        unsafe_allow_html=True
                    )

            # Hadith references
            for idx, ref in enumerate(hadith_refs):
                ref_key = (para_id, "hadith", idx)
                is_accepted = ref_key not in st.session_state.rejected_refs

                hadith_str = ref.collection or "Unknown"
                if ref.hadith_number:
                    hadith_str += f" #{ref.hadith_number}"

                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    if st.checkbox(
                        "Accept",
                        value=is_accepted,
                        key=f"hadith_{para_id}_{idx}",
                        label_visibility="collapsed"
                    ):
                        st.session_state.rejected_refs.discard(ref_key)
                    else:
                        st.session_state.rejected_refs.add(ref_key)

                with col2:
                    st.markdown(
                        f'<span style="color: {colors.hadith_text};">📘 {hadith_str}</span>',
                        unsafe_allow_html=True
                    )

        # Manual tagging section
        render_manual_tag_input(para_id)

        # Review button
        if st.button(
            "✓ Mark as Reviewed" if not is_reviewed else "↩ Unmark",
            key=f"review_{para_id}",
            type="primary" if not is_reviewed else "secondary"
        ):
            st.session_state.reviews[para_id] = not is_reviewed
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


def render_manual_tag_input(para_id: int):
    """Render manual tag input controls for a paragraph."""
    with st.expander("➕ Add Manual Tag"):
        tag_type = st.selectbox(
            "Reference Type",
            ["None", "Quran", "Hadith", "Seerah"],
            key=f"tag_type_{para_id}"
        )

        if tag_type == "Quran":
            col1, col2, col3 = st.columns(3)
            with col1:
                surah = st.number_input(
                    "Surah",
                    min_value=1,
                    max_value=114,
                    key=f"surah_{para_id}"
                )
            with col2:
                ayah_start = st.number_input(
                    "Ayah Start",
                    min_value=1,
                    key=f"ayah_start_{para_id}"
                )
            with col3:
                ayah_end = st.number_input(
                    "Ayah End (optional)",
                    min_value=0,
                    key=f"ayah_end_{para_id}",
                    help="Leave 0 for single ayah"
                )

            if st.button("Add Quran Reference", key=f"add_quran_{para_id}"):
                if para_id not in st.session_state.manual_tags:
                    st.session_state.manual_tags[para_id] = []
                st.session_state.manual_tags[para_id].append({
                    "type": "quran",
                    "surah": surah,
                    "ayah_start": ayah_start,
                    "ayah_end": ayah_end if ayah_end > 0 else None,
                })
                st.success("Quran reference added!")

        elif tag_type == "Hadith":
            col1, col2 = st.columns(2)
            with col1:
                collection = st.selectbox(
                    "Collection",
                    [
                        "Sahih al-Bukhari", "Sahih Muslim", "Sunan at-Tirmidhi",
                        "Sunan Abi Dawood", "Sunan an-Nasa'i", "Sunan Ibn Majah",
                        "Musnad Ahmad", "Muwatta Malik", "Other"
                    ],
                    key=f"collection_{para_id}"
                )
            with col2:
                hadith_num = st.number_input(
                    "Hadith Number",
                    min_value=1,
                    key=f"hadith_num_{para_id}"
                )

            if st.button("Add Hadith Reference", key=f"add_hadith_{para_id}"):
                if para_id not in st.session_state.manual_tags:
                    st.session_state.manual_tags[para_id] = []
                st.session_state.manual_tags[para_id].append({
                    "type": "hadith",
                    "collection": collection,
                    "number": hadith_num,
                })
                st.success("Hadith reference added!")

        elif tag_type == "Seerah":
            note = st.text_input("Seerah Note", key=f"seerah_note_{para_id}")
            if st.button("Add Seerah Reference", key=f"add_seerah_{para_id}"):
                if para_id not in st.session_state.manual_tags:
                    st.session_state.manual_tags[para_id] = []
                st.session_state.manual_tags[para_id].append({
                    "type": "seerah",
                    "note": note,
                })
                st.success("Seerah reference added!")

        # Show existing manual tags
        if para_id in st.session_state.manual_tags and st.session_state.manual_tags[para_id]:
            st.markdown("**Manual tags:**")
            for i, tag in enumerate(st.session_state.manual_tags[para_id]):
                st.write(f"- {tag}")


# === Export Functions ===

def build_export_data(
    paragraphs: list[str],
    detected_refs: dict,
) -> dict:
    """
    Build the export JSON structure.

    Args:
        paragraphs: List of paragraph texts
        detected_refs: Dict with detected references

    Returns:
        Complete export data structure
    """
    paragraph_data = []

    for i, text in enumerate(paragraphs):
        quran_refs = detected_refs["quran"][i]
        hadith_refs = detected_refs["hadith"][i]

        # Build Quran refs list
        quran_list = []
        for idx, ref in enumerate(quran_refs):
            ref_key = (i, "quran", idx)
            quran_list.append({
                "surah": ref.surah,
                "ayah_start": ref.ayah_start,
                "ayah_end": ref.ayah_end,
                "quoted_text": ref.matched_text,
                "detection": "auto",
                "verified": ref_key not in st.session_state.rejected_refs,
            })

        # Build Hadith refs list
        hadith_list = []
        for idx, ref in enumerate(hadith_refs):
            ref_key = (i, "hadith", idx)
            hadith_list.append({
                "collection": ref.collection,
                "number": ref.hadith_number,
                "detection": "auto",
                "verified": ref_key not in st.session_state.rejected_refs,
            })

        # Add manual tags
        manual_tags = st.session_state.manual_tags.get(i, [])
        for tag in manual_tags:
            if tag["type"] == "quran":
                quran_list.append({
                    "surah": tag["surah"],
                    "ayah_start": tag["ayah_start"],
                    "ayah_end": tag.get("ayah_end"),
                    "quoted_text": "",
                    "detection": "manual",
                    "verified": True,
                })
            elif tag["type"] == "hadith":
                hadith_list.append({
                    "collection": tag["collection"],
                    "number": tag["number"],
                    "detection": "manual",
                    "verified": True,
                })

        # Build paragraph entry
        para_entry = {
            "id": i + 1,
            "text": text,
            "reviewed": st.session_state.reviews.get(i, False),
            "quran_refs": quran_list,
            "hadith_refs": hadith_list,
            "seerah_refs": [t for t in manual_tags if t["type"] == "seerah"],
            "manual_notes": "",
        }

        # Include based on config
        if app_config.include_unreviewed or para_entry["reviewed"]:
            paragraph_data.append(para_entry)

    # Calculate summary
    reviewed_count = sum(1 for p in paragraph_data if p["reviewed"])
    quran_count = sum(len(p["quran_refs"]) for p in paragraph_data)
    hadith_count = sum(len(p["hadith_refs"]) for p in paragraph_data)
    seerah_count = sum(len(p["seerah_refs"]) for p in paragraph_data)

    return {
        "book_title": st.session_state.book_title,
        "author": "",
        "processed_date": datetime.now().strftime("%Y-%m-%d"),
        "annotator": st.session_state.annotator_name,
        "paragraphs": paragraph_data,
        "summary": {
            "total_paragraphs": len(paragraphs),
            "reviewed_paragraphs": reviewed_count,
            "quran_refs_count": quran_count,
            "hadith_refs_count": hadith_count,
            "seerah_refs_count": seerah_count,
        }
    }


def render_export_button(paragraphs: list[str], detected_refs: dict):
    """Render the export JSON button."""
    if not app_config.enable_export:
        return

    export_data = build_export_data(paragraphs, detected_refs)

    if app_config.pretty_print_json:
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
    else:
        json_str = json.dumps(export_data, ensure_ascii=False)

    filename = f"{st.session_state.book_title or 'annotations'}_{datetime.now().strftime('%Y%m%d')}.json"

    st.download_button(
        label="📥 Export JSON",
        data=json_str,
        file_name=filename,
        mime="application/json",
    )


# === Main App ===

def main():
    """Main application entry point."""
    st.set_page_config(
        page_title=app_config.app_title,
        page_icon="📚",
        layout="wide",
    )

    init_session_state()

    # Header with upload
    uploaded_file = render_header()

    if uploaded_file is None:
        st.info("👆 Upload a DOCX file to begin annotating.")
        return

    # Load and process document (cached)
    file_bytes = uploaded_file.read()
    paragraphs = load_document(file_bytes)

    if not paragraphs:
        st.warning("No paragraphs found in the document.")
        return

    # Detect references (cached) - convert to tuple for hashability
    detected_refs = detect_all_references(tuple(paragraphs))

    # Progress bar
    reviewed_count = sum(1 for v in st.session_state.reviews.values() if v)
    render_progress_bar(len(paragraphs), reviewed_count)

    # Export button in sidebar
    with st.sidebar:
        st.header("Export")
        render_export_button(paragraphs, detected_refs)

        st.divider()
        st.header("Statistics")
        total_quran = sum(len(refs) for refs in detected_refs["quran"])
        total_hadith = sum(len(refs) for refs in detected_refs["hadith"])
        st.metric("Quran References", total_quran)
        st.metric("Hadith References", total_hadith)
        st.metric("Paragraphs", len(paragraphs))

    # Pagination
    if app_config.paragraphs_per_page > 0:
        total_pages = (len(paragraphs) + app_config.paragraphs_per_page - 1) // app_config.paragraphs_per_page
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
        start_idx = (page - 1) * app_config.paragraphs_per_page
        end_idx = min(start_idx + app_config.paragraphs_per_page, len(paragraphs))
        display_range = range(start_idx, end_idx)
    else:
        display_range = range(len(paragraphs))

    # Render paragraphs
    for i in display_range:
        render_paragraph(
            para_id=i,
            text=paragraphs[i],
            quran_refs=detected_refs["quran"][i],
            hadith_refs=detected_refs["hadith"][i],
        )


if __name__ == "__main__":
    main()
