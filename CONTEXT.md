# Islamic Text Annotation Tool - Context Reference

## Purpose
Processing 145 Islamic books for LightRAG integration. Tool enables:
- Auto-detection of Quran/Hadith references
- Footnote extraction and linking
- Junk paragraph detection (cover pages, index, copyright)
- Page number matching via PDF upload
- JSON export for downstream processing

## Current Status: v2.5.3 (2026-01-04)

### v2.5.3 Changelog
- **FIX**: Expander icons - JavaScript injection replaces "keyboard_double_arrow_*" with ▶/▼
- **FIX**: Last Read button now shows text ("📖 Last" / "📄 Mark")
- **FIX**: Duplicate key error for delete buttons (added unique ref identifiers)
- **REMOVED**: CSS hacks for icons (don't work with Streamlit Material Icons)

### v2.5.2 Changelog
- **FIX**: Dropdown menus now have visible white text on dark background
- **FIX**: Auto-detected reference rows properly aligned (checkbox + text + delete button)
- **CSS**: Added explicit dropdown popup styling for [data-baseweb] components

---

## LightRAG Integration Status

### Completed (2026-01-04)
1. **LightRAG Export Format Fixed** - `lightrag_export.py` now produces correct format:
   - Uses `relationships` key (not `relations`)
   - Chunks include `source_chunk_index`
   - Relationships include `keywords`, `source_id`, `weight`

2. **LightRAG API Enhanced** - `/root/lightrag/app.py`:
   - Added `/insert_custom_kg` endpoint for injecting pre-built knowledge graphs
   - Added `/query/data` endpoint for chunk retrieval (Islamic Demo compatibility)
   - Endpoint reads from `kv_store_text_chunks.json` for keyword-based search

3. **Network Configuration Fixed**:
   - Islamic Demo now connects to LightRAG via `lightrag_default` network on port 8081
   - Nginx updated: `graph.spiritualmessage.org` → port 8081 (was 9621)

4. **Apps Tested & Working**:
   - **Islamic Demo** (https://learn.spiritualmessage.org) - ✅ Connected to LightRAG
   - **Spiritual Reflections** (https://spiritual-reflections.vercel.app) - ✅ Uses graph.spiritualmessage.org
   - **LightRAG API** (https://graph.spiritualmessage.org) - ✅ Health: healthy, RAG: ready

### LightRAG Stats (Current Index)
- **Chunks**: 6,329
- **Entities**: 1,754
- **Relationships**: 33,186

### Key Files
| File | Purpose |
|------|---------|
| `/root/lightrag/app.py` | LightRAG FastAPI with custom endpoints |
| `/root/lightrag/docker-compose.yml` | LightRAG container config |
| `/root/islamic_app_demo/docker-compose.yml` | Islamic Demo → LightRAG connection |
| `/etc/nginx/sites-enabled/graph` | graph.spiritualmessage.org proxy |
| `/root/annotation_tool/lightrag_export.py` | Export annotations for LightRAG |

### Next Steps
- Process more books through annotation tool
- Export annotated books to LightRAG using `lightrag_export.py`
- Monitor LightRAG query quality as more content is added

---

## Citation System Enhancement (2026-01-04)

### BookViewerPanel - YouVersion-Style Book Reader

Both Islamic Demo and Spiritual Reflections now have slide-over book viewer panels for citations.

#### Features
- **Slide-over panel**: 45-65% width on desktop, 80% on mobile
- **Chapter navigation**: Collapsible sidebar with chapter tree
- **Quote highlighting**: Auto-scroll to cited passage with yellow highlight
- **Keyboard navigation**: ESC to close, arrow keys for prev/next chapter
- **Cross-origin support**: Spiritual Reflections can access Islamic Demo books API

#### Implementation Files

**Islamic Demo** (`/root/islamic_app_demo/`):
| File | Purpose |
|------|---------|
| `frontend/components/BookViewerPanel.tsx` | Slide-over panel component |
| `frontend/components/chatbot/ChatInterface.tsx` | Uses BookViewerPanel for citations |
| `backend/app/main.py` | CORS headers for cross-origin access |

**Spiritual Reflections** (`/root/spiritual-reflections/`):
| File | Purpose |
|------|---------|
| `components/BookViewerPanel.js` | Dark-themed slide-over panel |
| `components/SpiritualInterpretation.js` | Integration with fallback to CitationModal |
| `lib/claude.js` | Added `bookSlug` field to citations |

#### API Flow
```
Citation Click → Check book exists in DB → BookViewerPanel OR CitationModal fallback
```

#### Cross-Origin API
- Spiritual Reflections calls `https://learn.spiritualmessage.org/api/books/{slug}`
- CORS configured for `spiritual-reflections.vercel.app`

### Sentence-Level Citation Highlighting

Citations now support precise sentence-level highlighting in addition to string matching.

#### Citation Object Fields
```python
class Citation:
    sentence_idx: Optional[int]       # Single sentence index (0-based)
    sentence_range: Optional[List[int]]  # [start_idx, end_idx] for groups
    is_summary: bool                  # True if summarizing multiple sentences
```

#### Highlighting Cases
1. **Sentence range**: Highlights block of sentences (for summaries)
2. **Single sentence**: Highlights exact sentence by index
3. **String matching**: Fallback to text search (existing behavior)

#### Files Modified
- `backend/app/services/citation_service.py` - `find_sentence_indices()` function
- `backend/app/schemas/chat.py` - Added sentence indexing fields
- `frontend/components/chatbot/CitationModal.tsx` - Multi-case highlighting

---

## v2.1 Simplified Workflow (Admin + Annotator Only)

### Two Roles Only
| Role | Capabilities |
|------|-------------|
| **Admin** | Upload books, view stats, approve submissions, delete books, export JSON |
| **Annotator** | Pick book, annotate paragraphs, submit for approval |

### Workflow
```
Admin uploads DOCX+PDF → Annotator picks & works → Annotator submits → Admin approves → Done
```

---

## Role-Based Portals

### 🔴 Admin Portal
- **Dashboard Stats**: Total | Not Started | Annotating | To Approve | Done
- **Add Book**: Upload paired DOCX + PDF (auto-extracts title from filename)
- **Book Library Table**: Name | PDF | DOCX | Status | Action | Delete
- **Approval Section**: Select books → Bulk approve or individual approve
- **Approved Books**: Download JSON exports
- **Notifications**: 🔔 badge shows newly approved books (last 24h)

### 🟢 Annotator Portal
- **Book List**: Shows all books with progress bars
- **Locking**: Pick a book → locked to you (others see 🔒)
- **Resume**: "Continue Working" button for your locked book
- **Release**: Can release book if needed
- **Submit**: Send completed work to Admin for approval

---

## Data Structure

### Book Library
```
/app/books/
├── quran_guidance/
│   ├── document.docx    # Source file
│   ├── document.pdf     # Page reference
│   └── meta.json        # Metadata + status
```

### meta.json Schema
```json
{
    "title": "Quran Guidance",
    "status": "in_progress",
    "locked_by": "annotator",
    "locked_at": "2026-01-03T14:30:00",
    "progress": 40,
    "annotated_by": null,
    "submitted_at": null,
    "approved_by": null,
    "approved_at": null,
    "created_at": "2026-01-03T10:00:00"
}
```

### Status Flow
```
pending → in_progress → submitted → approved
            ↓
        (release lock)
```

---

## Features

### Core Features
1. **DOCX Processing** - Extract paragraphs with metadata
2. **Quran Detection** - API-verified verse references (Al-Quran Cloud API)
3. **Hadith Detection** - Major collections (Bukhari, Muslim, etc.)
4. **Footnote Handling** - Extract and link markers to footnotes
5. **Keyword Highlighting** - Islamic terms, numbers, years
6. **PDF Page Matching** - Page number extraction from PDF
7. **Deletion Queue** - Bulk approve/reject junk paragraphs
8. **JSON Export** - Schema per ANNOTATION_TOOL_SPEC.md

### v2.0+ Features
9. **User Authentication** - streamlit-authenticator
10. **Book Library** - Admin uploads paired DOCX+PDF
11. **Book Locking** - One annotator per book (2-hour timeout)
12. **Progress Tracking** - % complete per book
13. **Bulk Approval** - Admin can approve multiple books at once
14. **Book Deletion** - Admin can remove books from library
15. **Default Author** - "Maulana Wahiduddin Khan"

### v2.3+ LLM Extraction Features
16. **Concept Extraction** - LLM extracts concepts from Maulana taxonomy
17. **Provider Selection** - Switch between DeepSeek and Gemini
18. **Gemini Key Rotation** - 3 API keys for ~40 RPM
19. **Verse Aspect Extraction** - Multi-aspect discovery (same verse, different themes)
20. **Inline Tag Display** - Concepts, aspects, people, places shown per paragraph
21. **LightRAG Export** - Merged 512-token chunks with entity/relation mapping
22. **Extraction Filtering** - Skips headers, deleted, and already-extracted paragraphs

---

## Architecture
```
/root/annotation_tool/
├── app.py                    # Main Streamlit app (v2.4.0)
├── concept_extractor.py      # LLM extraction (Gemini/DeepSeek)
├── lightrag_export.py        # Export for LightRAG custom_kg
├── Dockerfile
├── docker-compose.yml
├── requirements.txt          # streamlit-authenticator, pyyaml, bcrypt
├── .env                      # API keys (Gemini x3, DeepSeek)
├── data/
│   └── users.yaml            # User credentials (admin, annotator)
├── books/                    # Book library (DOCX+PDF+meta.json)
├── taxonomy/
│   └── maulana_taxonomy.yaml # 16 categories, 200+ subcategories
├── extractors/
│   ├── docx_parser.py
│   ├── quran_detector.py
│   └── hadith_detector.py
├── services/
│   ├── pdf_handler.py
│   └── llm_detector.py
├── utils/
│   └── highlighter.py
└── exports/                  # JSON output directory
```

---

## Deployment
- **URL**: https://annotate.spiritualmessage.org
- **Port**: 8502 (Docker) → nginx proxy
- **SSL**: Let's Encrypt (auto-renewal)

---

## Credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| annotator | annotator123 | Annotator |

---

## Admin Dashboard Stats

```
┌────────┬────────────┬────────────┬─────────────┬────────┐
│ 📚     │ ⚪ Not     │ 🟢         │ 🔵 To       │ ✅     │
│ Total  │ Started    │ Annotating │ Approve     │ Done   │
└────────┴────────────┴────────────┴─────────────┴────────┘
```

---

## Key Decisions

1. **Reviewer role removed** - Admin handles approvals directly
2. **Two-tier workflow** - Simpler: Admin → Annotator → Admin
3. **PDF viewer removed** - Performance issues, kept only page extraction
4. **Deletion queued** - Allows bulk review + undo
5. **Book locking** - 2-hour timeout prevents stale locks
6. **Bulk approval** - Select multiple books, approve at once
7. **Default author** - "Maulana Wahiduddin Khan" pre-filled
8. **Old Dashboard removed** - Single unified app with auth

---

## Commands

```bash
# Rebuild and deploy
cd /root/annotation_tool
docker compose down && docker compose up -d --build

# View logs
docker logs islamic_annotation_tool -f

# Check health
curl http://127.0.0.1:8502/_stcore/health

# Generate password hash for new user
python3 -c "import bcrypt; print(bcrypt.hashpw('password'.encode(), bcrypt.gensalt()).decode())"
```

## LLM Extraction Usage

### In the UI
1. Load a book from library
2. In sidebar, select provider (DeepSeek recommended when Gemini quota exceeded)
3. Click "Extract 10" to process next 10 paragraphs
4. Click "Extract All" to process entire book
5. View inline tags showing extracted concepts, aspects, people, places

### Export to LightRAG
1. After extraction, click "Export for LightRAG" in sidebar
2. Downloads JSON with merged 512-token chunks
3. Import into LightRAG:
```python
import json
from lightrag import LightRAG

rag = LightRAG(working_dir="./maulana_rag")

with open("book_lightrag.json") as f:
    data = json.load(f)

# IMPORTANT: rename key for LightRAG
data["relationships"] = data.pop("relations")

await rag.ainsert_custom_kg(data)
```

---

## Adding New Users

Edit `/root/annotation_tool/data/users.yaml`:
```yaml
credentials:
  usernames:
    newuser:
      name: New User
      password: $2b$12$...  # bcrypt hash
      role: annotator  # or admin
```
Then rebuild: `docker compose up -d --build`

---

## Changelog

### v2.5.1 (2026-01-04) - UI Cleanup
- **Renamed app** - Changed from "Islamic Text Annotation Tool" to "Book Annotation Tool"
- **Removed Arabic text** - Removed bismillah from login and portal headers
- **Login form centered** - Max-width 400px, centered with margin auto
- **Dark mode enforced** - Added `[theme] base = "dark"` to config.toml
- **Expander icon fix** - JavaScript injection replaces Material Icons text with Unicode ▶/▼

### v2.5.0 (2026-01-04) - Feature Enhancements
- **Admin-only LLM extraction** - LLM Extraction and LightRAG Export sections now only visible to admins
- **Delete buttons for auto-detected refs** - Quran, Hadith, Year, and Footnote references now have ❌ delete buttons
  - Tighter layout with `gap="small"` and column ratios [0.3, 5, 0.3]
  - CSS for centered alignment and smaller delete buttons
- **Year format improved** - Years now display as "Year: YYYY" instead of raw matched text
  - Bug fix: Now correctly reads `text` field or falls back to `start_pos`/`end_pos` keys
- **Mark as Last Read feature** - Click 📖 button to mark reading progress per book
  - Auto-scrolls to last read position on book load
  - Reading position saved per user per book in `last_read_{user}.json`

### v2.4.0 (2026-01-04) - Modern UI Redesign
- **Complete UI overhaul** with modern dark theme
- Background: Slate dark (#1e293b)
- Cards: White with shadows and hover lift effects
- Annotator accent: Blue (#3b82f6)
- Admin accent: Green (#10b981)
- **LLM tags as colored pills**:
  - Concepts: Teal with 20% opacity background
  - Verse aspects: Purple
  - People: Red
  - Places: Blue
  - Hadith/Islamic terms: Amber
- **Submit button**: Green rounded pill with shadow
- Expanders styled as white cards with hover effects
- Improved contrast and readability
- Clean Inter font throughout

### v2.3.1 (2026-01-03) - Bug Fixes
- **Fixed admin login** - Regenerated password hash, new cookie key to invalidate old sessions
- **Added submit button** - Annotators can now submit work via "Submit for Approval" button in sidebar
- **Added auto-detect toggle** - Checkbox to enable/disable Quran/Hadith auto-detection on book load
- Disabled auto-detect skips Quran/Hadith but keeps year/footnote detection
- Created sample_lightrag_output.json for reference
- Fixed .env file corruption

### v2.3.0 (2026-01-03) - LLM Concept Extraction
- **NEW: LLM-based concept extraction** with Gemini/DeepSeek providers
- Added "Extract 10" and "Extract All" buttons in sidebar
- Added inline tag display showing extracted concepts, aspects, people, places
- Added provider selector (DeepSeek/Gemini) - use DeepSeek when Gemini quota exceeded
- Added Gemini API key rotation (3 keys for ~40 RPM)
- Added verse aspect extraction (multi-aspect discovery for same Quran verse)
- **NEW: LightRAG export** with merged 512-token chunks
- Created `concept_extractor.py` - 7-paragraph context window extraction
- Created `lightrag_export.py` - Export for LightRAG `ainsert_custom_kg()`
- **Bug fix**: Skip chapter_heading and subheading types during extraction
- **Bug fix**: "Extract 10" now correctly counts only extractable paragraphs
- **Bug fix**: Deleted/grouped paragraphs properly filtered from extraction count
- Added extraction_status tracking per paragraph (pending/extracted)
- Added extraction stats in sidebar (concepts, aspects, people, places)
- Uses Maulana taxonomy: 16 categories, 200+ subcategories

### v2.2.3 (2026-01-03) - Material Icons Fix
- **Fixed Material Icons showing as text** (keyboard_double_arrow_right/down)
- Root cause: `@import` loads fonts late, Streamlit renders before font ready
- Solution: Use `<link>` tag which loads fonts earlier (higher priority)
- Added Material Icons link tag before CSS block
- Removed duplicate @import for Material Icons

### v2.2.2 (2026-01-03) - Badge & Link Fixes
- Fixed word/token badge invisible on dark theme
- Changed badge colors to dark-compatible (#334155 bg, #94a3b8 text)
- Fixed deletion queue link colors (now #6ee7b7 emerald)
- Added Material Icons @import (superseded by v2.2.3)

### v2.2.1 (2026-01-03) - Dark Theme
- **Dark elegant theme** - easier on eyes, reduces strain
- Deep charcoal backgrounds (#0f0f1a, #1a1a2e)
- Light text (#f1f5f9) with high contrast
- Emerald green (#10b981) and gold (#f59e0b) accents
- Fixed white-on-white text issues from v2.2.0
- Simplified CSS for reliability
- Inter font for clean modern UI
- Amiri font for Arabic text

### v2.2.0 (2026-01-03) - UI Beautification
- **Complete visual overhaul** with Islamic-inspired design
- Google Fonts: Poppins (UI), Amiri (Arabic), Noto Naskh Arabic
- Islamic color palette: Emerald green, gold accents, cream backgrounds
- Custom header banners with gradient backgrounds and decorative elements
- Bismillah Arabic text on login and portal headers
- Card-style containers with shadows and hover effects
- Styled buttons with gradients and animations
- Custom scrollbars matching theme colors
- Role badges with distinct styling (Admin/Annotator)
- Reference tags with gradient backgrounds
- Islamic geometric pattern backgrounds
- Responsive design for mobile
- Custom file uploader styling
- Enhanced metrics/stats display

### v2.1.2 (2026-01-03)
- Fixed jump to paragraph using `st.components.v1.html()` (st.markdown blocks scripts)
- Fixed delete button gap with `gap="small"` parameter + tighter [0.85, 0.15] ratio

### v2.1.1 (2026-01-03)
- Fixed delete reference button spacing (now closer to text with [0.9, 0.1] ratio)
- Fixed jump to paragraph (removed meta refresh that caused page reload)
- Added loading spinners on action buttons
- Added back button in annotation view
- Improved word count badge visibility (black text)
- Added 30-second auto-save after activity
- Added toast notifications for page save feedback
- Performance: Added caching for DOCX, PDF, Quran/Hadith detection
- Performance: Added @st.fragment for partial reruns
- Performance: Increased Docker limits to 2 CPU / 1GB RAM
- Multiple reference additions now work correctly
- Faster book loading (skip PDF if already loaded)
- Added "Jump to Last Para" feature with session-based scroll

### v2.1.0 (2026-01-03)
- Removed Reviewer role (Admin handles approvals)
- Added bulk approval for Admin
- Added delete book functionality
- Set default author to "Maulana Wahiduddin Khan"
- Removed old Dashboard page (no-auth security issue)
- Updated stats: Not Started | Annotating | To Approve | Done

### v2.0.0 (2026-01-03)
- Added Book Library system (paired DOCX+PDF)
- Added book locking mechanism
- Added role-based portals (Admin/Annotator/Reviewer)
- Added progress tracking per book

### v1.5.0 (2026-01-03)
- Added user authentication
- Added auto-save after upload
- UI fixes (stats badge, group button, page edit)
