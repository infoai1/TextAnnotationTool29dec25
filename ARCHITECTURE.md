# Annotation Tool Architecture

## Metrics (Baseline - Jan 11, 2026)
- Lines in app.py: **4576**
- Total Functions: **55**

## Function Map

### Data/Persistence (→ db.py in Phase 1)
| Function | Line | Purpose |
|----------|------|---------|
| save_progress | 831 | Save to JSON (atomic write) |
| load_saved_book | 987 | Load from JSON |
| get_saved_books | 944 | List saved books |
| load_last_read_position | 928 | Resume last position |
| save_meta | 1047 | Save book metadata |
| load_meta | 1039 | Load book metadata |
| can_lock_book | 1069 | Check lock availability |
| lock_book | 1093 | Lock book for editing |
| release_lock | 1102 | Release book lock |

**Total: 9 functions → db.py**

---

### UI/Rendering (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| render_junk_approval | 1601 | Junk paragraph approval UI |
| render_group_dashboard | 2003 | Group management UI |
| render_header | 2520 | Top header bar |
| render_progress | 2671 | Progress indicators |
| render_sidebar | 2764 | Left sidebar navigation |
| render_group | 3215 | Single group display |
| render_paragraph | 3300 | Single paragraph display |
| render_portal | 3986 | Main portal/dashboard |

**Total: 8 functions**

---

### Processing (→ processors.py later)
| Function | Line | Purpose |
|----------|------|---------|
| cached_extract_paragraphs | 91 | Extract paragraphs from DOCX |
| cached_detect_quran_refs | 96 | Detect Quran references |
| cached_detect_hadith_refs | 101 | Detect Hadith references |
| detect_junk_paragraphs | 1220 | Detect TOC/junk |
| process_pdf_file | 1286 | Parse PDF for page mapping |
| process_uploaded_file | 1378 | Process DOCX upload |

**Total: 6 functions → processors.py (future)**

---

### Utilities (→ helpers.py in Phase 1)
| Function | Line | Purpose |
|----------|------|---------|
| humanize_time_ago | 907 | Convert datetime to "2 hours ago" |
| generate_slug | 1681 | Make URL-safe slug |
| estimate_tokens | 1691 | Estimate token count |
| count_tokens | 824 | Accurate token count |

**Total: 4 functions → helpers.py**

**Note:** Renamed to helpers.py to avoid conflict with existing utils/ package.

---

### Group Management (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| create_groups_for_chapter | 1698 | Auto-group chapter paragraphs |
| generate_groups | 1850 | Generate all groups |
| cleanup_empty_groups | 1882 | Remove empty groups |
| move_paragraph_to_group | 1900 | Move paragraph between groups |
| merge_groups | 1926 | Merge two groups |
| split_group_at_paragraph | 1952 | Split group at paragraph |
| recalculate_group_stats | 1817 | Update group stats |
| find_paragraph | 1793 | Find paragraph by ID |
| find_paragraph_index | 1801 | Find paragraph index |
| find_group | 1809 | Find group by ID |
| generate_next_group_id | 1839 | Generate unique group ID |
| get_group_validation_status | 1887 | Get group validation status |
| group_selected_paragraphs | 2683 | Group selected paragraphs |

**Total: 13 functions**

---

### Library/Book Management (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| get_library_books | 1053 | List all books in library |
| load_book_from_library | 1109 | Load book from library |
| submit_book_for_review | 1186 | Submit for approval |
| approve_book | 1200 | Approve submitted book |
| delete_book | 1208 | Delete book |

**Total: 5 functions**

---

### Export (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| build_hierarchical_structure | 2283 | Build export structure |
| export_json | 2401 | Export annotated data |

**Total: 2 functions**

---

### Session/State Management (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| init_session_state | 721 | Initialize session vars |
| mark_activity | 800 | Track user activity |
| check_auto_save | 808 | Auto-save check |
| get_progress | 1594 | Get current progress |

**Total: 4 functions**

---

### UI Helpers (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| toggle_add_ref_form | 3288 | Toggle ref form |
| close_add_ref_form | 3293 | Close ref form |

**Total: 2 functions**

---

### Auth/Config (stays in app.py)
| Function | Line | Purpose |
|----------|------|---------|
| load_auth_config | 4300 | Load auth configuration |
| main | 4313 | Entry point |

**Total: 2 functions**

---

## Session State Keys (32 tracked)

```python
session_state.annotator
session_state.author
session_state.auto_detect_enabled
session_state.book_slug
session_state.book_status
session_state.book_title
session_state.current_book_folder
session_state.current_group_index
session_state.current_user
session_state.custom_keywords
session_state.detected_refs
session_state.document_footnotes
session_state.endnotes
session_state.file_uploaded
session_state.groups
session_state.has_unsaved_changes
session_state.highlight_keywords
session_state.highlight_numbers
session_state.highlight_years
session_state.last_read_para
session_state.last_save_time
session_state.last_worked_para
session_state.paragraphs
session_state.pdf_loaded
session_state.pdf_pages
session_state.scroll_to_group
session_state.scroll_to_para
session_state.selected_for_approval
session_state.selected_for_grouping
session_state.selected_groups
session_state.user_role
session_state.view_mode
```

---

## Refactor Strategy

### Phase 1 (COMPLETE): Extract Pure Logic
- [x] Section 0: Backup
- [x] Section 1: Map functions
- [x] Section 2: config.py (paths, constants)
- [x] Section 3: helpers.py (pure helpers)
- [x] Section 4: db.py (persistence)
- [x] Section 5: Wire db.py into app.py
- [x] Section 6: Documentation (DEBUGGING.md)
- [x] Section 7: Verification ✓ ALL TESTS PASSED

### Phase 2 (Future): Extract Processors
- processors.py (PDF, DOCX, LLM extraction)
- components.py (render_* functions as reusable components)

### Phase 3 (Future): Performance
- Remove unnecessary saves
- Fix fragment scopes
- Add async where beneficial

---

## File Structure (Target)

```
annotation_tool/
├── app.py (UI + routing) - ~3000 lines
├── config.py (constants) - ~53 lines ✓
├── helpers.py (pure helpers) - ~185 lines ✓
├── db.py (persistence) - ~465 lines ✓
├── processors.py (future) - ~400 lines
├── components.py (future) - ~500 lines
├── utils/ (existing package)
│   ├── highlighter.py
│   └── text_utils.py
└── ARCHITECTURE.md (this file)
```

---

**Created:** Jan 11, 2026
**Updated:** Jan 11, 2026 - Section 1 complete
