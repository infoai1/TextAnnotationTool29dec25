# Performance Guidelines for Islamic Text Annotation Tool

This document outlines performance anti-patterns to avoid and best practices to follow during implementation.

---

## 1. Regex Pattern Compilation

### Anti-Pattern
```python
# Compiling regex on every function call
def detect_quran(text):
    pattern = re.compile(r'\((\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\)')
    return pattern.findall(text)
```

### Best Practice
```python
# Compile once at module level
QURAN_PATTERNS = [
    re.compile(r'\((\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\)'),
    re.compile(r'Surah\s+[\w\-]+\s+(\d{1,3}):(\d{1,3})', re.IGNORECASE),
    re.compile(r'verse\s+(\d{1,3}):(\d{1,3})', re.IGNORECASE),
]

def detect_quran(text):
    results = []
    for pattern in QURAN_PATTERNS:
        results.extend(pattern.findall(text))
    return results
```

**Impact**: With 45+ paragraphs and multiple patterns, avoiding recompilation saves significant CPU cycles.

---

## 2. Streamlit Caching

### Anti-Pattern
```python
# No caching - recalculates on every UI interaction
def load_and_process_docx(file):
    doc = Document(file)
    paragraphs = [p.text for p in doc.paragraphs]
    return detect_all_references(paragraphs)
```

### Best Practice
```python
from io import BytesIO

@st.cache_data
def load_and_process_docx(file_bytes: bytes):
    """Cache DOCX processing to avoid re-parsing on every interaction."""
    doc = Document(BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return detect_all_references(paragraphs)

# Usage: pass file.read() instead of file object
if uploaded_file:
    file_bytes = uploaded_file.read()
    data = load_and_process_docx(file_bytes)
```

**Impact**: Every checkbox click triggers a Streamlit rerun. Without caching, this re-parses the entire DOCX.

---

## 3. String Building

### Anti-Pattern
```python
# O(n²) string concatenation
def highlight_text(text, refs):
    result = ""
    for segment in segments:
        result += f"<span>{segment}</span>"  # Creates new string each iteration
    return result
```

### Best Practice
```python
# O(n) using list join
def highlight_text(text, refs):
    parts = []
    for segment in segments:
        parts.append(f"<span>{segment}</span>")
    return ''.join(parts)

# Or using StringIO for very large texts
from io import StringIO

def highlight_text(text, refs):
    buffer = StringIO()
    for segment in segments:
        buffer.write(f"<span>{segment}</span>")
    return buffer.getvalue()
```

**Impact**: String concatenation creates a new string object each iteration, causing O(n²) memory allocations.

---

## 4. Session State Management

### Anti-Pattern
```python
# Storing large objects in session state
st.session_state['document'] = {
    'paragraphs': [...],  # Full text of all paragraphs
    'all_refs': [...],    # All detected references
    'highlights': [...],  # Pre-rendered HTML for each paragraph
}
```

### Best Practice
```python
# Store only user-generated state changes
st.session_state['reviews'] = {}        # {para_id: bool}
st.session_state['rejected_refs'] = set()  # {(para_id, ref_id)}
st.session_state['manual_tags'] = {}    # {para_id: [tags]}

# Derive everything else from cached functions
@st.cache_data
def get_document_data(file_bytes):
    return parse_and_detect(file_bytes)

# Combine cached data with session state at render time
def get_paragraph_state(para_id, cached_data):
    return {
        'text': cached_data['paragraphs'][para_id],
        'refs': cached_data['refs'][para_id],
        'reviewed': st.session_state['reviews'].get(para_id, False),
    }
```

**Impact**: Large session state increases memory usage and serialization overhead between reruns.

---

## 5. Batch Processing vs N+1 Calls

### Anti-Pattern
```python
# Separate processing for each paragraph
for para in paragraphs:
    quran = detect_quran(para)      # N calls
    hadith = detect_hadith(para)    # N calls
    highlight = make_highlight(para, quran, hadith)  # N calls
```

### Best Practice
```python
# Process all paragraphs together where possible
def detect_all_references(paragraphs):
    results = []
    for i, para in enumerate(paragraphs):
        results.append({
            'id': i,
            'text': para,
            'quran': detect_quran(para),
            'hadith': detect_hadith(para),
        })
    return results

# Or use list comprehensions for simple transformations
quran_refs = [detect_quran(p) for p in paragraphs]
```

**Impact**: Reduces function call overhead and enables potential future optimizations like parallel processing.

---

## 6. Hadith Collection Matching

### Anti-Pattern
```python
# Linear search with repeated string operations
HADITH_COLLECTIONS = ["Sahih al-Bukhari", "Sahih Muslim", ...]

def find_collection(text):
    text_lower = text.lower()
    for collection in HADITH_COLLECTIONS:
        if collection.lower() in text_lower:  # .lower() called 11 times per search
            return collection
    return None
```

### Best Practice
```python
# Pre-compiled alternation pattern
HADITH_COLLECTIONS = [
    "Sahih al-Bukhari", "Sahih Muslim", "Sunan at-Tirmidhi",
    "Sunan Abi Dawood", "Sunan an-Nasa'i", "Sunan Ibn Majah",
    "Musnad Ahmad", "Muwatta Malik", "Musnad Al-Bazzar",
    "Musnad Al-Shihab", "Al-Tabarani"
]

# Build pattern once at module load
COLLECTION_PATTERN = re.compile(
    r'(' + '|'.join(re.escape(c) for c in HADITH_COLLECTIONS) + r')',
    re.IGNORECASE
)

def find_collection(text):
    match = COLLECTION_PATTERN.search(text)
    return match.group(1) if match else None
```

**Impact**: Single regex search vs 11 substring searches with case conversion.

---

## 7. Lazy Loading for Large Documents

### Anti-Pattern
```python
# Load everything into memory immediately
def parse_docx(file):
    doc = Document(file)
    return [p.text for p in doc.paragraphs]  # All paragraphs in memory
```

### Best Practice
```python
# Generator for memory efficiency (useful for very large docs)
def iter_paragraphs(doc):
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            yield text

# For Streamlit, materialize once and cache
@st.cache_data
def parse_docx(file_bytes):
    doc = Document(BytesIO(file_bytes))
    return [p.text for p in doc.paragraphs if p.text.strip()]
```

**Impact**: For typical book sizes (45-200 paragraphs), full loading is fine. Consider generators for 1000+ paragraph documents.

---

## 8. UI Rendering Optimization

### Anti-Pattern
```python
# Render all paragraphs every time
for para in paragraphs:
    st.markdown(highlight(para))  # Renders 45+ times on every interaction
    st.checkbox("Reviewed")
```

### Best Practice
```python
# Use pagination or virtual scrolling
PARAGRAPHS_PER_PAGE = 10

page = st.number_input("Page", min_value=1, max_value=total_pages)
start_idx = (page - 1) * PARAGRAPHS_PER_PAGE
end_idx = start_idx + PARAGRAPHS_PER_PAGE

for para in paragraphs[start_idx:end_idx]:
    render_paragraph(para)

# Or use st.expander for collapsed sections
for i, para in enumerate(paragraphs):
    with st.expander(f"Paragraph {i+1}", expanded=(i < 5)):
        render_paragraph(para)
```

**Impact**: Streamlit rerenders the entire page on state changes. Fewer visible elements = faster renders.

---

## Summary Checklist

Before submitting code, verify:

- [ ] All regex patterns compiled at module level
- [ ] `@st.cache_data` used for DOCX parsing and reference detection
- [ ] String building uses `''.join()` not `+=`
- [ ] Session state stores only user changes, not derived data
- [ ] No repeated `.lower()` or similar transformations in loops
- [ ] Pagination implemented for large documents
- [ ] Heavy computations wrapped in caching decorators

---

## Performance Testing

To validate performance:

```python
import time

def measure(func, *args):
    start = time.perf_counter()
    result = func(*args)
    elapsed = time.perf_counter() - start
    print(f"{func.__name__}: {elapsed:.3f}s")
    return result

# Test with a large document
paragraphs = load_test_document()  # 100+ paragraphs
measure(detect_all_references, paragraphs)
```

Target benchmarks:
- DOCX parsing: < 1 second for 100 paragraphs
- Reference detection: < 500ms for 100 paragraphs
- UI rerender: < 100ms per interaction
