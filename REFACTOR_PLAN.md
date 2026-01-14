# Annotation Tool Refactor Plan

## Guidelines for Claude Code

**RULES:**
1. Read ONE section at a time
2. Complete that section fully
3. Verify with the checklist
4. Ask user "Ready for next section?" before proceeding
5. If anything breaks → STOP → Fix → Then continue
6. Commit after each section

**NEVER:**
- Skip verification steps
- Do multiple sections at once
- Proceed without user confirmation

---

## Section 0: Backup & Baseline (5 min)

### Commands
```bash
cd /root/annotation_tool

# Backup
cp app.py app.py.backup.$(date +%Y%m%d_%H%M%S)

# Git snapshot
git add -A && git commit -m "Pre-refactor snapshot" || echo "Nothing to commit"

# Baseline metrics
echo "=== BASELINE ===" > REFACTOR_LOG.md
echo "Date: $(date)" >> REFACTOR_LOG.md
echo "Lines: $(wc -l < app.py)" >> REFACTOR_LOG.md
echo "Functions: $(grep -c '^def ' app.py)" >> REFACTOR_LOG.md
cat REFACTOR_LOG.md
```

### Checklist
- [ ] Backup file exists (ls app.py.backup.*)
- [ ] REFACTOR_LOG.md created
- [ ] Git committed

### Done?
Ask user: "Section 0 complete. Backup created. Ready for Section 1?"

---

## Section 1: Map All Functions (15 min)

### Purpose
Understand what exists before changing anything.

### Commands
```bash
cd /root/annotation_tool

# List all functions with line numbers
grep -n "^def " app.py > /tmp/all_functions.txt
cat /tmp/all_functions.txt

# Count by category
echo "=== Save/Load functions ===" 
grep "def save_\|def load_\|def get_saved" /tmp/all_functions.txt

echo "=== Render functions ===" 
grep "def render_" /tmp/all_functions.txt

echo "=== Process functions ===" 
grep "def process_\|def extract_\|def match_" /tmp/all_functions.txt

# Session state keys
grep -o "session_state\.[a-zA-Z_]*" app.py | sort -u | head -30
```

### Create ARCHITECTURE.md
Create file with this structure:

```markdown
# Annotation Tool Architecture

## Metrics
- Lines: [X]
- Functions: [X]

## Function Map

### Data/Persistence (→ db.py)
| Function | Line | Purpose |
|----------|------|---------|
| save_progress | ? | Save to JSON |
| load_saved_book | ? | Load from JSON |
| get_saved_books | ? | List saved books |
| (add others found) | | |

### UI/Rendering (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| render_paragraph | ? | Display paragraph |
| render_group | ? | Display group |
| (add others found) | | |

### Processing (→ processors.py later)
| Function | Line | Purpose |
|----------|------|---------|
| process_pdf | ? | Parse PDF |
| (add others found) | | |

### Utilities (→ utils.py)
| Function | Line | Purpose |
|----------|------|---------|
| slugify | ? | Make URL-safe string |
| (add others found) | | |
```

### Checklist
- [ ] /tmp/all_functions.txt has all functions
- [ ] ARCHITECTURE.md created
- [ ] Functions categorized into 4 groups

### Done?
Show user the function counts per category. Ask: "Section 1 complete. Found X functions. Ready for Section 2?"

---

## Section 2: Create config.py (10 min)

### Purpose
All constants in one place. Easy to change later.

### Commands
```bash
# Find hardcoded paths
grep -n "'/root\|/data/\|/app/" app.py | head -10

# Find hardcoded numbers  
grep -n "= 30\|= 60\|= 10\|ttl=" app.py | head -10
```

### Create config.py
```python
"""
Configuration constants for Annotation Tool.
"""
from pathlib import Path

# Paths
BASE_DIR = Path("/root/annotation_tool")
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"
VERSIONS_DIR = DATA_DIR / "versions"

# Ensure directories exist
for d in [DATA_DIR, EXPORTS_DIR, LOGS_DIR, VERSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Timing
AUTO_SAVE_INTERVAL = 10  # seconds
VERSION_KEEP_COUNT = 10
LOCK_TIMEOUT_HOURS = 2

# UI defaults
DEFAULT_COLLAPSED = True
```

### Test
```bash
docker exec islamic_annotation_tool python3 -c "from config import DATA_DIR; print(f'DATA_DIR: {DATA_DIR}')"
```

### Commit
```bash
git add config.py && git commit -m "Add config.py"
echo "Section 2: config.py - $(date)" >> REFACTOR_LOG.md
```

### Checklist
- [ ] config.py created
- [ ] Import test passes
- [ ] Git committed

### Done?
Ask user: "Section 2 complete. config.py ready. Ready for Section 3?"

---

## Section 3: Create utils.py (10 min)

### Purpose
Pure helper functions. No Streamlit. Easy to test.

### Commands
```bash
# Find utility functions in app.py
grep -n "def slugify\|def humanize\|def validate\|def format_" app.py
```

### Create utils.py
```python
"""
Pure utility functions. No Streamlit, no file I/O.
"""
import re
from datetime import datetime, timedelta

def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '_', slug)
    return slug[:max_length]

def humanize_time_ago(dt: datetime) -> str:
    """Convert datetime to '2 hours ago' format."""
    if not dt:
        return "Never"
    
    diff = datetime.now() - dt
    
    if diff < timedelta(minutes=1):
        return "Just now"
    elif diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f"{mins} min ago"
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} hours ago"
    else:
        return f"{diff.days} days ago"

def validate_para_id(para_id: str) -> bool:
    """Check if paragraph ID format is valid."""
    return bool(re.match(r'^p_\d{3,}$', para_id))

def validate_group_id(group_id: str) -> bool:
    """Check if group ID format is valid."""
    return bool(re.match(r'^g_\d{3,}$', group_id))
```

### Test
```bash
docker exec islamic_annotation_tool python3 -c "
from utils import slugify, humanize_time_ago
print(slugify('Peace in Kashmir'))
from datetime import datetime, timedelta
print(humanize_time_ago(datetime.now() - timedelta(hours=2)))
"
```

### Commit
```bash
git add utils.py && git commit -m "Add utils.py"
echo "Section 3: utils.py - $(date)" >> REFACTOR_LOG.md
```

### Checklist
- [ ] utils.py created
- [ ] Test output: "peace_in_kashmir" and "2 hours ago"
- [ ] Git committed

### Done?
Ask user: "Section 3 complete. utils.py ready. Ready for Section 4?"

---

## Section 4: Create db.py (30 min)

### Purpose
All save/load/version logic in one file. This is the biggest extraction.

### Step 4a: Identify functions to extract
```bash
grep -n "^def save_progress\|^def load_saved_book\|^def get_saved_books\|^def create_version\|^def list_versions\|^def rollback" app.py
```

Note the line numbers. We will COPY these functions, not move yet.

### Step 4b: Create db.py skeleton
```python
"""
Database/Persistence layer for Annotation Tool.
All file I/O happens here.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import DATA_DIR, VERSIONS_DIR, VERSION_KEEP_COUNT, LOCK_TIMEOUT_HOURS
from utils import slugify

logger = logging.getLogger(__name__)

def get_progress_path(book_folder: str, user: str) -> Path:
    """Get path to progress file."""
    slug = slugify(book_folder)
    return DATA_DIR / f"{slug}_{user}_progress.json"

def progress_exists(book_folder: str, user: str) -> bool:
    """Check if progress file exists."""
    return get_progress_path(book_folder, user).exists()

def save_progress(data: dict, book_folder: str, user: str) -> bool:
    """Save progress to disk with atomic write."""
    path = get_progress_path(book_folder, user)
    temp_path = path.with_suffix('.tmp')
    
    try:
        data['last_saved'] = datetime.now().isoformat()
        data['last_saved_by'] = user
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        temp_path.rename(path)
        logger.info(f"[SAVE] book={book_folder} user={user}")
        return True
    except Exception as e:
        logger.error(f"[SAVE] FAILED: {e}")
        if temp_path.exists():
            temp_path.unlink()
        return False

def load_progress(book_folder: str, user: str) -> Optional[dict]:
    """Load progress from disk."""
    path = get_progress_path(book_folder, user)
    
    if not path.exists():
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[LOAD] FAILED: {e}")
        return None

def list_saved_books(user: str, role: str = 'annotator') -> list:
    """List all saved books for user."""
    saved = []
    
    for path in DATA_DIR.glob("*_progress.json"):
        if f"_{user}_" in path.name or role == 'admin':
            try:
                with open(path) as f:
                    data = json.load(f)
                saved.append({
                    'book_title': data.get('book_title', 'Unknown'),
                    'book_folder': data.get('current_book_folder', ''),
                    'last_saved': data.get('last_saved'),
                    'status': data.get('book_status', 'in_progress')
                })
            except:
                continue
    
    saved.sort(key=lambda x: x.get('last_saved', ''), reverse=True)
    return saved

# === VERSIONS ===

def get_versions_dir(book_folder: str, user: str) -> Path:
    """Get versions directory for book."""
    slug = slugify(book_folder)
    path = VERSIONS_DIR / f"{slug}_{user}"
    path.mkdir(parents=True, exist_ok=True)
    return path

def create_version(book_folder: str, user: str, data: dict) -> Optional[str]:
    """Create version snapshot."""
    versions_dir = get_versions_dir(book_folder, user)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_path = versions_dir / f"v_{timestamp}.json"
    
    try:
        with open(version_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"[VERSION] created {timestamp}")
        cleanup_old_versions(book_folder, user)
        return timestamp
    except Exception as e:
        logger.error(f"[VERSION] FAILED: {e}")
        return None

def list_versions(book_folder: str, user: str) -> list:
    """List available versions."""
    versions_dir = get_versions_dir(book_folder, user)
    versions = []
    
    for path in sorted(versions_dir.glob("v_*.json"), reverse=True):
        timestamp_str = path.stem.replace("v_", "")
        versions.append({
            'id': timestamp_str,
            'path': str(path)
        })
    
    return versions

def rollback_to_version(book_folder: str, user: str, version_id: str) -> bool:
    """Restore from version."""
    versions_dir = get_versions_dir(book_folder, user)
    version_path = versions_dir / f"v_{version_id}.json"
    
    if not version_path.exists():
        return False
    
    try:
        with open(version_path) as f:
            data = json.load(f)
        return save_progress(data, book_folder, user)
    except:
        return False

def cleanup_old_versions(book_folder: str, user: str):
    """Keep only last N versions."""
    versions = list_versions(book_folder, user)
    for old in versions[VERSION_KEEP_COUNT:]:
        try:
            Path(old['path']).unlink()
        except:
            pass
```

### Test db.py
```bash
docker exec islamic_annotation_tool python3 -c "
from db import progress_exists, list_saved_books
print('Testing db.py...')
books = list_saved_books('admin', 'admin')
print(f'Found {len(books)} saved books')
print('db.py OK!')
"
```

### Commit
```bash
git add db.py && git commit -m "Add db.py persistence layer"
echo "Section 4: db.py - $(date)" >> REFACTOR_LOG.md
```

### Checklist
- [ ] db.py created
- [ ] Import test passes
- [ ] list_saved_books returns data
- [ ] Git committed

### Done?
Ask user: "Section 4 complete. db.py ready. Ready for Section 5?"

---

## Section 5: Wire db.py into app.py (20 min)

### Purpose
Make app.py USE db.py instead of inline code.

### Step 5a: Add imports to app.py
At top of app.py, add:
```python
from config import DATA_DIR, AUTO_SAVE_INTERVAL, VERSION_KEEP_COUNT
from utils import slugify, humanize_time_ago
from db import (
    save_progress as db_save,
    load_progress as db_load,
    list_saved_books as db_list_books,
    progress_exists,
    create_version,
    list_versions,
    rollback_to_version
)
```

### Step 5b: Update save_progress() in app.py
Find the existing save_progress() function and replace its BODY (keep the function, change inside):

```python
def save_progress():
    """Save current session to disk."""
    if not st.session_state.book_title or not st.session_state.paragraphs:
        return
    
    data = {
        'book_title': st.session_state.book_title,
        'paragraphs': st.session_state.paragraphs,
        'groups': st.session_state.get('groups', []),
        'book_status': st.session_state.get('book_status', 'in_progress'),
        'current_book_folder': st.session_state.get('current_book_folder', ''),
        'pdf_loaded': st.session_state.get('pdf_loaded', False),
    }
    
    book_folder = st.session_state.get('current_book_folder', '')
    user = st.session_state.get('username', 'admin')
    
    if db_save(data, book_folder, user):
        create_version(book_folder, user, data)
        st.session_state.has_unsaved_changes = False
```

### Step 5c: Test
```bash
docker-compose restart
# Then test in browser: load a book, make change, check if saves
```

### Commit
```bash
git add app.py && git commit -m "Wire db.py into app.py"
echo "Section 5: Wired db.py - $(date)" >> REFACTOR_LOG.md
```

### Checklist
- [ ] Imports added to app.py
- [ ] save_progress() updated
- [ ] Container restarts without error
- [ ] Save still works in browser
- [ ] Git committed

### Done?
Ask user: "Section 5 complete. app.py now uses db.py. Ready for Section 6?"

---

## Section 6: Create DEBUGGING.md (5 min)

### Create /root/annotation_tool/DEBUGGING.md
```markdown
# Debugging Guide

## Log Locations
- App log: /root/annotation_tool/logs/app.log
- Button log: /root/annotation_tool/logs/buttons.log

## Quick Commands

```bash
# Watch logs
tail -f logs/app.log

# Find errors
grep ERROR logs/app.log

# Find saves
grep SAVE logs/app.log | tail -10

# Restart container
docker-compose restart

# Check container
docker ps | grep annotation
docker logs islamic_annotation_tool --tail 20
```

## Common Issues

### Changes not saving
1. Check: `grep SAVE logs/app.log | tail -5`
2. Verify auto-save running every 10s

### Book not loading  
1. Check file exists: `ls data/*progress.json`
2. Check valid JSON: `python3 -c "import json; json.load(open('data/FILE.json'))"`

### Slow UI
1. Check full reruns: `grep "st.rerun()" app.py | grep -v scope`
2. Should use `st.rerun(scope="fragment")` inside fragments

## Rollback

```bash
# Revert last change
git checkout HEAD -- app.py
docker-compose restart

# Full rollback
cp app.py.backup.TIMESTAMP app.py
docker-compose restart
```
```

### Commit
```bash
git add DEBUGGING.md && git commit -m "Add DEBUGGING.md"
```

### Checklist
- [ ] DEBUGGING.md created
- [ ] Git committed

---

## Section 7: Final Verification (5 min)

### Commands
```bash
# Final metrics
echo "=== AFTER REFACTOR ===" >> REFACTOR_LOG.md
echo "Date: $(date)" >> REFACTOR_LOG.md
echo "app.py: $(wc -l < app.py) lines" >> REFACTOR_LOG.md
echo "db.py: $(wc -l < db.py) lines" >> REFACTOR_LOG.md
echo "utils.py: $(wc -l < utils.py) lines" >> REFACTOR_LOG.md
echo "config.py: $(wc -l < config.py) lines" >> REFACTOR_LOG.md

# Test all imports
docker exec islamic_annotation_tool python3 -c "
from config import DATA_DIR
from utils import slugify
from db import save_progress, load_progress
print('All imports OK')
"

# Final commit
git add -A && git commit -m "Complete refactor Phase 1"
git push origin main

cat REFACTOR_LOG.md
```

### Final Checklist
- [ ] config.py exists and works
- [ ] utils.py exists and works
- [ ] db.py exists and works
- [ ] app.py uses new modules
- [ ] ARCHITECTURE.md documents structure
- [ ] DEBUGGING.md has troubleshooting
- [ ] REFACTOR_LOG.md shows before/after
- [ ] Container runs without errors
- [ ] Basic features work (load, save, export)
- [ ] All committed to git

---

## Summary

| File | Purpose | Lines |
|------|---------|-------|
| config.py | Constants, paths | ~30 |
| utils.py | Pure helpers | ~50 |
| db.py | All persistence | ~150 |
| app.py | UI + routing | Reduced |
| ARCHITECTURE.md | Documentation | - |
| DEBUGGING.md | Troubleshooting | - |

---

## Next Phase (Future)

After this is stable:
1. Extract processors.py (PDF parsing, LLM calls)
2. Extract components.py (render_* functions)
3. Add performance fixes (remove saves, fragment scope)
4. Add tests

But FIRST make current refactor stable!
