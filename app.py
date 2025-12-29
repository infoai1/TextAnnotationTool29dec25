"""
Islamic Text Annotation Tool
A Streamlit app to display DOCX books, auto-detect Quran/Hadith references,
and enable manual annotation.
"""

import streamlit as st
import json
from datetime import datetime
from io import BytesIO

from extractors import extract_paragraphs, detect_quran_refs, detect_hadith_refs
from extractors.docx_parser import get_document_metadata
from extractors.quran_detector import format_quran_ref
from extractors.hadith_detector import format_hadith_ref, get_collection_list
from utils.highlighter import get_highlight_css, highlight_text_simple, DEFAULT_KEYWORDS


# Page configuration
st.set_page_config(
    page_title="Islamic Text Annotation Tool",
    page_icon="📖",
    layout="wide"
)

# Apply custom CSS
st.markdown(get_highlight_css(), unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'paragraphs' not in st.session_state:
        st.session_state.paragraphs = []
    if 'book_title' not in st.session_state:
        st.session_state.book_title = ""
    if 'author' not in st.session_state:
        st.session_state.author = ""
    if 'annotator' not in st.session_state:
        st.session_state.annotator = ""
    if 'file_uploaded' not in st.session_state:
        st.session_state.file_uploaded = False
    if 'detected_refs' not in st.session_state:
        st.session_state.detected_refs = {}  # paragraph_id -> {'quran': [], 'hadith': []}
    # Keyword highlighting settings
    if 'highlight_keywords' not in st.session_state:
        st.session_state.highlight_keywords = True
    if 'highlight_numbers' not in st.session_state:
        st.session_state.highlight_numbers = True
    if 'highlight_years' not in st.session_state:
        st.session_state.highlight_years = True
    if 'custom_keywords' not in st.session_state:
        st.session_state.custom_keywords = DEFAULT_KEYWORDS.copy()
    # Paragraph grouping
    if 'selected_for_grouping' not in st.session_state:
        st.session_state.selected_for_grouping = set()


def count_tokens(text: str) -> dict:
    """Count words and characters in text."""
    words = len(text.split())
    chars = len(text)
    return {'words': words, 'chars': chars}


def process_uploaded_file(uploaded_file):
    """Process the uploaded DOCX file."""
    file_content = BytesIO(uploaded_file.getvalue())

    # Extract paragraphs
    paragraphs = extract_paragraphs(file_content)

    # Get metadata
    file_content.seek(0)
    metadata = get_document_metadata(file_content)

    # Auto-detect references for each paragraph
    detected_refs = {}
    for para in paragraphs:
        para_id = para['id']
        quran_refs = detect_quran_refs(para['text'])
        hadith_refs = detect_hadith_refs(para['text'])

        # Store detected refs
        detected_refs[para_id] = {
            'quran': quran_refs,
            'hadith': hadith_refs
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

    st.session_state.paragraphs = paragraphs
    st.session_state.detected_refs = detected_refs
    st.session_state.file_uploaded = True

    if metadata.get('title'):
        st.session_state.book_title = metadata['title']
    if metadata.get('author'):
        st.session_state.author = metadata['author']


def get_progress():
    """Calculate review progress."""
    total = len(st.session_state.paragraphs)
    reviewed = sum(1 for p in st.session_state.paragraphs if p.get('reviewed', False))
    return reviewed, total


def export_json():
    """Generate JSON export of annotations."""
    reviewed, total = get_progress()

    # Count all references
    quran_count = sum(len(p.get('quran_refs', [])) for p in st.session_state.paragraphs)
    hadith_count = sum(len(p.get('hadith_refs', [])) for p in st.session_state.paragraphs)
    seerah_count = sum(len(p.get('seerah_refs', [])) for p in st.session_state.paragraphs)
    other_book_count = sum(len(p.get('other_book_refs', [])) for p in st.session_state.paragraphs)

    # Filter out grouped paragraphs for cleaner export
    active_paragraphs = [p for p in st.session_state.paragraphs if not p.get('grouped_into')]

    export_data = {
        "book_title": st.session_state.book_title,
        "author": st.session_state.author,
        "processed_date": datetime.now().strftime("%Y-%m-%d"),
        "annotator": st.session_state.annotator,
        "paragraphs": active_paragraphs,
        "summary": {
            "total_paragraphs": len(active_paragraphs),
            "reviewed_paragraphs": reviewed,
            "quran_refs_count": quran_count,
            "hadith_refs_count": hadith_count,
            "seerah_refs_count": seerah_count,
            "other_book_refs_count": other_book_count
        }
    }

    return json.dumps(export_data, indent=2, ensure_ascii=False)


def render_header():
    """Render the header section with upload and metadata."""
    st.title("📖 Islamic Text Annotation Tool")

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload DOCX file",
            type=['docx'],
            key='file_uploader'
        )
        if uploaded_file is not None and not st.session_state.file_uploaded:
            with st.spinner("Processing document..."):
                process_uploaded_file(uploaded_file)
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
            # Mark as grouped
            para['grouped_into'] = first_para['id']

    # Update first paragraph with merged content
    first_para['text'] = '\n\n'.join(merged_text_parts)
    first_para['quran_refs'] = merged_quran_refs
    first_para['hadith_refs'] = merged_hadith_refs
    first_para['seerah_refs'] = merged_seerah_refs
    first_para['other_book_refs'] = merged_other_book_refs
    first_para['grouped_from'] = grouped_para_ids

    # Update detected refs for the merged paragraph
    from extractors import detect_quran_refs, detect_hadith_refs
    quran_refs = detect_quran_refs(first_para['text'])
    hadith_refs = detect_hadith_refs(first_para['text'])
    st.session_state.detected_refs[first_para['id']] = {
        'quran': quran_refs,
        'hadith': hadith_refs
    }

    # Clear selection
    st.session_state.selected_for_grouping = set()


def render_sidebar():
    """Render the sidebar with highlighting options."""
    with st.sidebar:
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

        # Color legend
        st.subheader("Color Legend")
        st.markdown("""
        - 🟢 **Green**: Quran references
        - 🔵 **Blue**: Hadith references
        - 🩵 **Cyan**: Years/Dates
        - 🟠 **Orange**: Keywords
        - 🟣 **Purple**: Numbers
        - 📌 Has references
        """)


def render_paragraph(para_idx: int):
    """Render a single paragraph with its annotations."""
    para = st.session_state.paragraphs[para_idx]
    para_id = para['id']
    detected = st.session_state.detected_refs.get(para_id, {'quran': [], 'hadith': []})

    # Check if paragraph is part of a group
    if para.get('grouped_into'):
        return  # Skip rendering if merged into another paragraph

    # Paragraph container
    with st.container():
        # Header with word count
        reviewed_icon = "✅" if para.get('reviewed') else "⬜"
        token_info = count_tokens(para['text'])
        has_refs = bool(detected['quran'] or detected['hadith'] or para.get('quran_refs') or para.get('hadith_refs'))
        ref_indicator = "📌" if has_refs else ""

        col_header, col_stats, col_group = st.columns([3, 2, 1])
        with col_header:
            st.subheader(f"{reviewed_icon} Paragraph {para_id} {ref_indicator}")
        with col_stats:
            st.caption(f"📝 {token_info['words']} words | {token_info['chars']} chars")
        with col_group:
            # Grouping checkbox
            is_selected = para_id in st.session_state.selected_for_grouping
            if st.checkbox("Group", value=is_selected, key=f"group_select_{para_id}", help="Select to group with adjacent paragraphs"):
                st.session_state.selected_for_grouping.add(para_id)
            else:
                st.session_state.selected_for_grouping.discard(para_id)

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
        st.markdown(
            f'<div class="paragraph-box {"reviewed" if para.get("reviewed") else ""}">{highlighted_text}</div>',
            unsafe_allow_html=True
        )

        # Auto-detected references section
        if detected['quran'] or detected['hadith']:
            st.markdown("**Auto-detected references:**")

            # Quran references
            for i, ref in enumerate(detected['quran']):
                ref_key = f"quran_{para_id}_{i}"
                col1, col2 = st.columns([0.1, 0.9])
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
                        para['quran_refs'][i]['verified'] = new_verified
                with col2:
                    ref_text = format_quran_ref(ref)
                    quoted = ref.get('quoted_text', '')
                    if quoted:
                        st.markdown(f'🟢 **{ref_text}** - "{quoted[:50]}..."' if len(quoted) > 50 else f'🟢 **{ref_text}** - "{quoted}"')
                    else:
                        st.markdown(f'🟢 **{ref_text}**')

            # Hadith references
            for i, ref in enumerate(detected['hadith']):
                ref_key = f"hadith_{para_id}_{i}"
                col1, col2 = st.columns([0.1, 0.9])
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
                        para['hadith_refs'][i]['verified'] = new_verified
                with col2:
                    ref_text = format_hadith_ref(ref)
                    st.markdown(f'🔵 **{ref_text}**')

        # Manual tag section
        st.markdown("**Add manual tag:**")
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

        with col1:
            tag_type = st.selectbox(
                "Reference type",
                ["None", "Quran", "Hadith", "Seerah", "Other Book"],
                key=f"tag_type_{para_id}",
                label_visibility="collapsed"
            )

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

            if st.button("Add Quran Reference", key=f"add_quran_{para_id}"):
                new_ref = {
                    'surah': surah,
                    'ayah_start': ayah_start,
                    'ayah_end': ayah_end if ayah_end > 0 else None,
                    'quoted_text': '',
                    'detection': 'manual',
                    'verified': True
                }
                para['quran_refs'].append(new_ref)
                para['reviewed'] = True  # Auto-mark as reviewed
                st.success(f"Added Quran {surah}:{ayah_start}" + (f"-{ayah_end}" if ayah_end > 0 else ""))
                st.rerun()

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
                # Show custom input when "Other" is selected
                if collection == "Other":
                    custom_collection = st.text_input(
                        "Collection Name",
                        key=f"custom_collection_{para_id}",
                        placeholder="Enter collection name"
                    )
                else:
                    custom_collection = None

            if st.button("Add Hadith Reference", key=f"add_hadith_{para_id}"):
                # Use custom collection name if "Other" was selected
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
                    para['reviewed'] = True  # Auto-mark as reviewed
                    st.success(f"Added {final_collection}, Hadith No. {hadith_num}")
                    st.rerun()

        elif tag_type == "Seerah":
            with col2:
                seerah_note = st.text_input(
                    "Seerah reference note",
                    key=f"seerah_note_{para_id}"
                )
            if st.button("Add Seerah Reference", key=f"add_seerah_{para_id}"):
                if 'seerah_refs' not in para:
                    para['seerah_refs'] = []
                para['seerah_refs'].append({
                    'note': seerah_note,
                    'detection': 'manual',
                    'verified': True
                })
                para['reviewed'] = True  # Auto-mark as reviewed
                st.success("Added Seerah reference")
                st.rerun()

        elif tag_type == "Other Book":
            with col2:
                book_name = st.text_input(
                    "Book Name",
                    key=f"other_book_name_{para_id}",
                    placeholder="Enter book name"
                )
            with col3:
                page_or_ref = st.text_input(
                    "Page/Reference",
                    key=f"other_book_ref_{para_id}",
                    placeholder="e.g., Page 45 or Ch. 3"
                )
            with col4:
                pass  # Alignment

            if st.button("Add Book Reference", key=f"add_other_book_{para_id}"):
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
                    para['reviewed'] = True  # Auto-mark as reviewed
                    st.success(f"Added reference from {book_name}")
                    st.rerun()

        # Display manually added references
        manual_quran = [r for r in para.get('quran_refs', []) if r.get('detection') == 'manual']
        manual_hadith = [r for r in para.get('hadith_refs', []) if r.get('detection') == 'manual']
        manual_seerah = para.get('seerah_refs', [])
        manual_other_books = para.get('other_book_refs', [])

        if manual_quran or manual_hadith or manual_seerah or manual_other_books:
            st.markdown("**Manually added references:**")
            for ref in manual_quran:
                ayah_text = f"{ref['surah']}:{ref['ayah_start']}"
                if ref.get('ayah_end'):
                    ayah_text += f"-{ref['ayah_end']}"
                st.markdown(f"🟢 Quran {ayah_text} *(manual)*")
            for ref in manual_hadith:
                st.markdown(f"🔵 {ref.get('collection', 'Unknown')}, Hadith No. {ref.get('number', '?')} *(manual)*")
            for ref in manual_seerah:
                st.markdown(f"📜 Seerah: {ref.get('note', '')} *(manual)*")
            for ref in manual_other_books:
                st.markdown(f"📚 {ref.get('book_name', 'Unknown')}: {ref.get('reference', '')} *(manual)*")

        # Notes section
        notes = st.text_area(
            "Notes",
            value=para.get('manual_notes', ''),
            key=f"notes_{para_id}",
            height=68
        )
        para['manual_notes'] = notes

        # Mark as reviewed button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(
                "✓ Mark as Reviewed" if not para.get('reviewed') else "↩ Unmark",
                key=f"review_{para_id}",
                type="primary" if not para.get('reviewed') else "secondary"
            ):
                para['reviewed'] = not para.get('reviewed', False)
                st.rerun()

        st.divider()


def main():
    """Main application entry point."""
    init_session_state()

    render_sidebar()
    render_header()
    render_progress()

    if not st.session_state.file_uploaded:
        st.info("👆 Upload a DOCX file to begin annotation")
        st.markdown("""
        ### How to use this tool:
        1. **Upload** a DOCX file using the uploader above
        2. **Review** auto-detected Quran (🟢) and Hadith (🔵) references
        3. **Check** the boxes to verify correct detections
        4. **Add** any missed references using the manual tag dropdowns
        5. **Mark** each paragraph as reviewed when done
        6. **Export** your annotations as JSON when complete
        """)
    else:
        # Render all paragraphs
        for i in range(len(st.session_state.paragraphs)):
            render_paragraph(i)

        # Footer with summary
        st.markdown("---")
        reviewed, total = get_progress()
        quran_count = sum(len(p.get('quran_refs', [])) for p in st.session_state.paragraphs)
        hadith_count = sum(len(p.get('hadith_refs', [])) for p in st.session_state.paragraphs)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Paragraphs", total)
        with col2:
            st.metric("Reviewed", reviewed)
        with col3:
            st.metric("Quran References", quran_count)
        with col4:
            st.metric("Hadith References", hadith_count)


if __name__ == "__main__":
    main()
