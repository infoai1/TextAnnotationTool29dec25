# Islamic Text Annotation Tool - Scope Document

**Version:** 0.1  
**Purpose:** Streamlit app to display DOCX books, auto-detect Quran/Hadith references, and enable manual annotation for hired annotators.

---

## 1. Goal

Upload book → See text with auto-highlights → Review/correct detections → Add manual tags → Export JSON

---

## 2. Core Workflow

```
Upload DOCX → Split into paragraphs → Auto-detect refs → Display with highlights → Annotator reviews → Export JSON
```

---

## 3. Features (Priority Order)

### 3.1 Must Have (Edition 1)

| Feature | Description |
|---------|-------------|
| DOCX Upload | Single file upload |
| Text Display | Show full book split by paragraphs |
| Auto-detect Quran | Regex: `(X:Y)`, `(X:Y-Z)`, "Surah" patterns |
| Auto-detect Hadith | Regex: `Hadith No.`, collection names |
| Highlight Display | Color-coded: 🟢 Quran, 🔵 Hadith |
| Accept/Reject | Checkbox per auto-detection |
| Manual Tag | Dropdown per paragraph to add missed refs |
| Export JSON | Download structured output |

### 3.2 Should Have (Edition 2)

| Feature | Description |
|---------|-------------|
| Chapter Detection | Auto-detect chapter headings |
| Entity Tagging | Person, Location, Concept dropdowns |
| Book Metadata | Title, author input form |
| Progress Save | Save work-in-progress to file |

### 3.3 Could Have (Edition 3)

| Feature | Description |
|---------|-------------|
| Multi-book management | List of processed books |
| Entity deduplication | Merge same entities across books |
| Relationship mapping | Link entities to each other |

---

## 4. UI Layout (Single Page)

```
┌─────────────────────────────────────────────────────────┐
│ [Upload DOCX]  [Book Title: ___________]  [Export JSON] │
├─────────────────────────────────────────────────────────┤
│ Progress: 12/45 paragraphs reviewed                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ PARAGRAPH 1                                             │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ A study of the Quran and Hadith tells us that a    │ │
│ │ woman enjoys the same status... (3:195)            │ │
│ │                                        ↑ GREEN     │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ Auto-detected:                                          │
│ ☑ Quran 3:195 "You are members, one of another"        │
│                                                         │
│ Add manual tag: [Dropdown: None/Quran/Hadith/Seerah]   │
│ If Quran: Surah [__] Ayah [__] to [__]                 │
│ If Hadith: Collection [________] Number [____]         │
│                                                         │
│ [Mark as Reviewed ✓]                                    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ PARAGRAPH 2                                             │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Auto-Detection Patterns

### 5.1 Quran Patterns

```python
QURAN_PATTERNS = [
    r'\((\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\)',  # (3:195) or (4:11-12)
    r'Surah\s+[\w\-]+\s+(\d{1,3}):(\d{1,3})',   # Surah Al-Baqarah 2:153
    r'verse\s+(\d{1,3}):(\d{1,3})',              # verse 3:195
]
```

### 5.2 Hadith Patterns

```python
HADITH_COLLECTIONS = [
    "Sahih al-Bukhari", "Sahih Muslim", "Sunan at-Tirmidhi",
    "Sunan Abi Dawood", "Sunan an-Nasa'i", "Sunan Ibn Majah",
    "Musnad Ahmad", "Muwatta Malik", "Musnad Al-Bazzar",
    "Musnad Al-Shihab", "Al-Tabarani"
]

HADITH_PATTERNS = [
    r'\*([^*]+)\*,?\s*Hadith\s*No\.?\s*(\d+)',  # *Sahih al-Bukhari*, Hadith No. 5971
    r'Hadith\s*No\.?\s*(\d+)',                   # Hadith No. 236
]
```

---

## 6. Output JSON Schema

```json
{
  "book_title": "Guiding Lights",
  "author": "Maulana Wahiduddin Khan",
  "processed_date": "2024-12-29",
  "annotator": "Name",
  
  "paragraphs": [
    {
      "id": 1,
      "text": "A study of the Quran and Hadith tells us...",
      "reviewed": true,
      "quran_refs": [
        {
          "surah": 3,
          "ayah_start": 195,
          "ayah_end": null,
          "quoted_text": "You are members, one of another.",
          "detection": "auto",
          "verified": true
        }
      ],
      "hadith_refs": [],
      "seerah_refs": [],
      "manual_notes": ""
    }
  ],
  
  "summary": {
    "total_paragraphs": 45,
    "reviewed_paragraphs": 45,
    "quran_refs_count": 12,
    "hadith_refs_count": 8,
    "seerah_refs_count": 3
  }
}
```

---

## 7. Tech Stack

| Component | Choice |
|-----------|--------|
| Framework | Streamlit |
| DOCX Parsing | python-docx |
| Pattern Matching | regex (re module) |
| Data Storage | JSON files |
| Hosting | Streamlit Cloud / Local |

---

## 8. File Structure

```
/islamic-annotation-tool
├── app.py                    # Main Streamlit app
├── requirements.txt
├── README.md
│
├── extractors/
│   ├── __init__.py
│   ├── docx_parser.py        # Extract paragraphs from DOCX
│   ├── quran_detector.py     # Quran regex patterns
│   └── hadith_detector.py    # Hadith regex patterns
│
├── utils/
│   ├── __init__.py
│   └── highlighter.py        # Format text with highlights
│
├── data/
│   └── hadith_collections.json
│
└── exports/                  # Output JSON files
    └── .gitkeep
```

---

## 9. Development Phases

| Phase | Deliverable | Est. Time |
|-------|-------------|-----------|
| 1 | DOCX upload + paragraph display | 2-3 hrs |
| 2 | Quran auto-detection + highlight | 2-3 hrs |
| 3 | Hadith auto-detection + highlight | 1-2 hrs |
| 4 | Accept/reject checkboxes | 2-3 hrs |
| 5 | Manual tag dropdowns + inputs | 3-4 hrs |
| 6 | Export JSON | 1-2 hrs |
| 7 | Testing + bug fixes | 2-3 hrs |

**Total: ~15-20 hours**

---

## 10. Annotator Workflow

1. Upload DOCX file
2. Enter book title + annotator name
3. Scroll through paragraphs
4. For each paragraph:
   - Review auto-detected refs (green/blue highlights)
   - Check ☑ to confirm correct detections
   - Uncheck ☐ to reject wrong detections
   - Use dropdown to add missed refs
   - Click "Mark as Reviewed"
5. Export JSON when complete

---

## 11. Success Criteria

| Metric | Target |
|--------|--------|
| Quran auto-detection | >80% recall |
| Hadith auto-detection | >70% recall |
| Annotator speed | <2 min per paragraph |
| Export validity | 100% valid JSON |

---

## 12. Known Limitations

| Limitation | Workaround |
|------------|------------|
| No text selection | Paragraph-level tagging |
| No offline save | Export frequently |
| Single book at a time | Process sequentially |
| No undo | Refresh re-loads DOCX |

---

## 13. Future Enhancements (Out of Scope)

- Text selection for sub-paragraph tagging
- Entity tagging (Person, Location, Concept)
- Relationship mapping between entities
- Multi-user collaboration
- Arabic text support
- Direct Quran/Hadith database linking

---

## 14. Dependencies

```txt
streamlit>=1.28.0
python-docx>=0.8.11
```

---

**Ready for Claude Code development.**
