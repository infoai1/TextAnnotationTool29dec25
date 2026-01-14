# Annotation Tool - Developer Guide
**For non-coders adding new features**

---

## 🎯 Quick Start

The annotation tool has been refactored for maintainability. Instead of one 4,547-line file, it's now organized into clean modules:

```
annotation_tool/
├── app.py (~1,200 lines)          # Main Streamlit UI
├── modules/
│   ├── state.py                   # BookState - all session data
│   ├── index.py                   # ParagraphIndex - fast lookups
│   ├── grouping.py                # GroupManager - grouping algorithms
│   ├── persistence.py             # BookLibrary - save/load operations
│   ├── quality.py                 # QualityControl - junk detection
│   └── logger.py                  # Debugging logs
├── extractors/                    # PDF/DOCX/Quran/Hadith detection
├── concept_extractor.py           # LLM-based extraction
└── lightrag_export.py             # LightRAG export format
```

---

## 🔑 Key Concepts

### 1. BookState - Central Data Hub

**All annotation data lives here**. No more scattered `st.session_state` variables!

```python
from modules.state import BookState

# Create state
state = BookState()
state.book_title = "Peace in Kashmir"
state.paragraphs = [...]
state.groups = [...]

# Track changes
state.mark_activity(para_id="p_001")

# Check if needs auto-save
if state.needs_auto_save():
    library.save_progress(book_folder, state)
```

**When to modify**: Adding new book metadata fields (e.g., `publisher`, `year`)

---

### 2. ParagraphIndex - Fast O(1) Lookups

**Problem**: Old code was SLOW (O(n) linear search):
```python
# OLD - Slow ❌
for p in paragraphs:
    if p['id'] == para_id:
        return p
```

**Solution**: Use index for instant lookup:
```python
# NEW - Fast ✅
from modules.index import ParagraphIndex

index = ParagraphIndex(paragraphs, groups)
para = index.get_para('p_001')  # O(1) instant!
group = index.get_group('g_005')  # O(1) instant!
```

**When to use**: Searching for paragraphs/groups by ID

---

### 3. GroupManager - Smart Grouping

**Handles all group operations**:

```python
from modules.grouping import GroupManager

manager = GroupManager(min_tokens=512, max_tokens=800)

# Create groups for chapter
groups, next_counter = manager.create_groups_for_chapter(
    paragraphs=chapter_paras,
    chapter_title="Introduction",
    group_counter_start=0
)

# Validate group
status = manager.validate_group(group)  # 'optimal', 'acceptable', 'warning'

# Merge two groups
paragraphs, groups = manager.merge_groups('g_001', 'g_002', paragraphs, groups)

# Split at paragraph
paragraphs, groups = manager.split_group_at_paragraph('p_050', paragraphs, groups)
```

**When to modify**: Changing grouping algorithm (e.g., different token limits)

---

### 4. BookLibrary - Persistence

**Clean interface for all save/load operations**:

```python
from modules.persistence import BookLibrary
import db

library = BookLibrary(db)

# List books
books = library.get_library_books()

# Lock book for editing
library.lock_book(book_folder, username="junaid")

# Save progress
data = {
    'paragraphs': state.paragraphs,
    'groups': state.groups,
    ...
}
library.save_progress(book_folder, data, username="junaid")

# Load progress
progress = library.load_progress(book_folder)

# Release lock
library.release_lock(book_folder)
```

**When to modify**: Adding new save formats or workflow states

---

### 5. Logger - Debugging

**Structured logs for troubleshooting**:

```python
from modules.logger import setup_logging, read_recent_logs

# Setup (in main app)
logger = setup_logging(debug_mode=True)

# Use throughout code
logger.info(f"Loaded {len(paragraphs)} paragraphs")
logger.debug(f"Group g_001 has {tokens} tokens")
logger.warning(f"Group g_050 exceeds 1000 tokens")
logger.error(f"Failed to save: {error}")

# Display in UI (Streamlit)
if st.checkbox("🐛 Debug Mode"):
    st.code(read_recent_logs(100))
```

**Log file**: `/root/annotation_tool/logs/annotation_tool.log` (10MB max, 5 backups)

---

## 📝 Common Tasks

### Adding a New Field to Paragraphs

**Example**: Add `sentiment` field to paragraphs

1. **Update BookState** (`modules/state.py`):
```python
@dataclass
class BookState:
    # Existing fields...
    paragraph_sentiments: Dict[str, str] = field(default_factory=dict)  # para_id → sentiment
```

2. **Update UI** (`app.py`):
```python
def _render_paragraph_body(para: Dict):
    sentiment = st.selectbox(
        "Sentiment",
        options=["Positive", "Neutral", "Negative"],
        key=f"sentiment_{para['id']}"
    )
    para['sentiment'] = sentiment
```

3. **Update Export** (`modules/persistence.py` or export function):
```python
# Include sentiment in JSON export
para_data = {
    'id': para['id'],
    'text': para['text'],
    'sentiment': para.get('sentiment', 'Neutral')
}
```

**That's it!** Test and deploy.

---

### Adding a New UI Component

**Example**: Add "Quick Stats" panel to sidebar

1. Create function in `app.py`:
```python
def _render_sidebar_quick_stats(state: BookState):
    """Show quick stats in sidebar."""
    st.sidebar.subheader("📊 Quick Stats")
    total_paras = len(state.paragraphs)
    reviewed = sum(1 for p in state.paragraphs if p.get('reviewed'))

    st.sidebar.metric("Total Paragraphs", total_paras)
    st.sidebar.metric("Reviewed", reviewed)
    st.sidebar.progress(reviewed / total_paras if total_paras > 0 else 0)
```

2. Call from sidebar:
```python
def render_sidebar():
    _render_sidebar_filters()
    _render_sidebar_quick_stats(state)  # Add here
    _render_sidebar_export()
    ...
```

**Done!** The new panel appears in sidebar.

---

### Debugging Issues

**Step 1**: Enable debug mode in sidebar
- Check "🐛 Debug Mode" checkbox

**Step 2**: Check logs in UI
- Logs appear in sidebar when debug mode is on

**Step 3**: Check full logs
```bash
tail -f /root/annotation_tool/logs/annotation_tool.log
```

**Common errors**:

| Error | Cause | Fix |
|-------|-------|-----|
| `KeyError: 'group_id'` | Paragraph missing group assignment | Check grouping logic, rebuild index |
| `IndexError` | ParagraphIndex out of sync | Call `index.rebuild(paragraphs, groups)` |
| `TypeError: 'NoneType'` | Missing state initialization | Check `init_session_state()` called |
| Slow UI responsiveness | Using O(n) loops instead of index | Replace loops with `index.get_para()` |

---

## ⚡ Performance Tips

1. **Use Index for Lookups**
   ```python
   # Slow ❌
   para = [p for p in paragraphs if p['id'] == para_id][0]

   # Fast ✅
   para = index.get_para(para_id)
   ```

2. **Cache Token Counts**
   ```python
   # Slow ❌
   for para in paragraphs:
       tokens = helpers.count_tokens(para['text'])

   # Fast ✅
   for para in paragraphs:
       tokens = state.get_tokens(para['text'], helpers)  # Cached!
   ```

3. **Batch Operations**
   ```python
   # Update multiple paragraphs
   for para in selected_paras:
       para['reviewed'] = True

   # Then rebuild index once
   index.rebuild(paragraphs, groups)
   ```

4. **Profile Slow Code**
   ```python
   import time
   start = time.time()
   # ... your code ...
   logger.debug(f"Operation took {time.time() - start:.2f}s")
   ```

---

## 📂 File Structure Reference

| File | Lines | Purpose | Modify When... |
|------|-------|---------|----------------|
| `app.py` | ~1,200 | Main UI | Adding UI features |
| `modules/state.py` | 150 | Data structure | Adding fields |
| `modules/index.py` | 80 | Fast lookups | Never (stable) |
| `modules/grouping.py` | 250 | Grouping algorithms | Changing token limits |
| `modules/persistence.py` | 200 | Save/load | Adding storage formats |
| `modules/quality.py` | 100 | Junk detection | Improving detection |
| `modules/logger.py` | 50 | Debugging | Never (stable) |

**Total**: ~2,030 lines (vs 4,547 before) = **55% reduction**

---

## 🚀 Integration Example

**How to use new modules in app.py**:

```python
import streamlit as st
from modules.state import BookState
from modules.index import ParagraphIndex
from modules.grouping import GroupManager
from modules.persistence import BookLibrary
from modules.logger import setup_logging
import db
import helpers

# Initialize logger
logger = setup_logging(debug_mode=st.session_state.get('debug_mode', False))

# Initialize modules
library = BookLibrary(db)
manager = GroupManager(min_tokens=512, max_tokens=800)

# Load state
if 'paragraphs' in st.session_state:
    # Build index for fast lookups
    index = ParagraphIndex(
        st.session_state.paragraphs,
        st.session_state.groups
    )

    # Find paragraph (O(1) instead of O(n))
    para = index.get_para('p_001')

    # Generate groups
    if st.button("Generate Groups"):
        all_groups = manager.generate_groups(st.session_state.paragraphs)
        st.session_state.groups = all_groups
        index.rebuild(st.session_state.paragraphs, all_groups)
        logger.info(f"Generated {len(all_groups)} groups")

    # Save progress
    if st.button("Save"):
        data = {
            'paragraphs': st.session_state.paragraphs,
            'groups': st.session_state.groups,
            ...
        }
        library.save_progress(book_folder, data, username)
        logger.info("Progress saved")
```

---

## ✅ Testing Checklist

After making changes, test these:

- [ ] Upload DOCX file - paragraphs extracted?
- [ ] Upload PDF file - page numbers matched?
- [ ] Generate groups - correct token ranges?
- [ ] Move paragraph between groups - updates correctly?
- [ ] Save and reload - data persisted?
- [ ] Search paragraph by ID - instant?
- [ ] Debug mode - logs appear?

---

## 🆘 Getting Help

1. **Check logs**: `/root/annotation_tool/logs/annotation_tool.log`
2. **Enable debug mode**: See detailed logs in UI
3. **Test in isolation**: Create test script with modules only
4. **Read module docstrings**: All functions documented

---

## 📋 Next Steps

**To fully integrate modules into app.py**:

1. Replace `init_session_state()` with `BookState.from_session_state()`
2. Replace all `find_paragraph()` calls with `index.get_para()`
3. Replace direct `db.*` calls with `library.*`
4. Add `index.rebuild()` after bulk updates
5. Add logging to key operations

**Future improvements**:
- Unit tests for each module
- CLI version (reuse business logic)
- API endpoint (FastAPI wrapper)
- Automated testing pipeline

---

**Questions?** Check module docstrings - every function is documented with examples!
