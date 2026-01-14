"""
LightRAG Export Module
Transforms annotation tool JSON to LightRAG custom_kg format.

Features:
- Merges paragraphs to ~512 tokens with 75 token overlap
- Creates entities: BOOK, QURAN_REF, HADITH_REF, CONCEPT, VERSE_ASPECT
- Creates relationships: CITES, DISCUSSES, ILLUSTRATES, BELONGS_TO
- Preserves paragraph IDs for attribution

Created: January 3, 2025
"""

import json
import re
import os
from typing import List, Dict, Any, Optional, Set, Tuple

# Chunking parameters (evidence-based from research)
TARGET_TOKENS = 512
OVERLAP_TOKENS = 75  # ~15% overlap
CONTEXT_CHARS = 150  # Characters for prev/next context

# Entity normalization
ENTITY_SYNONYMS = {
    # Concepts
    "sabr": "patience",
    "shukr": "gratitude",
    "taqwa": "god_consciousness",
    "akhirah": "hereafter",
    "ijabi": "positive_thinking",
    # People
    "prophet muhammad": "muhammad_pbuh",
    "rasulullah": "muhammad_pbuh",
    "the prophet": "muhammad_pbuh",
}


def estimate_tokens(text: str) -> int:
    """Estimate token count (words * 1.3 for English text)."""
    return int(len(text.split()) * 1.3)


def normalize_entity(name: str, entity_type: str) -> str:
    """Normalize entity name for deduplication."""
    name = name.lower().strip()

    # Apply synonym mapping
    if name in ENTITY_SYNONYMS:
        name = ENTITY_SYNONYMS[name]

    # Type-specific normalization
    if entity_type == "QURAN_REF":
        # Always use "surah:ayah" format
        name = standardize_quran_ref(name)
    elif entity_type == "HADITH_REF":
        # Always use "collection:number" format
        name = standardize_hadith_ref(name)

    return name


def standardize_quran_ref(ref: str) -> str:
    """Standardize Quran reference to surah:ayah format."""
    # Remove any surah names, keep just numbers
    pattern = r'(\d+)[:\-](\d+)(?:\s*-\s*(\d+))?'
    match = re.search(pattern, ref)
    if match:
        surah = match.group(1)
        ayah_start = match.group(2)
        ayah_end = match.group(3)
        if ayah_end:
            return f"{surah}:{ayah_start}-{ayah_end}"
        return f"{surah}:{ayah_start}"
    return ref.lower()


def standardize_hadith_ref(ref: str) -> str:
    """Standardize Hadith reference to collection:number format."""
    ref = ref.lower()
    # Common collection name variations
    collections = {
        'bukhari': 'bukhari',
        'sahih bukhari': 'bukhari',
        'muslim': 'muslim',
        'sahih muslim': 'muslim',
        'tirmidhi': 'tirmidhi',
        'abu dawud': 'abu_dawud',
        'nasai': 'nasai',
        'ibn majah': 'ibn_majah',
    }

    for name, canonical in collections.items():
        if name in ref:
            # Extract number
            num_match = re.search(r'(\d+)', ref)
            if num_match:
                return f"{canonical}:{num_match.group(1)}"

    return ref


def merge_paragraphs_to_chunks(
    paragraphs: List[Dict],
    book_slug: str,
    para_to_group: Dict[int, str] = None
) -> List[Dict]:
    """
    Merge small paragraphs to ~512 tokens with overlap.

    Returns list of chunks with:
    - content: merged text
    - source_ids: list of original paragraph IDs
    - source_id: primary paragraph ID for LightRAG
    - group_id: group ID for citation linking (if available)
    """
    if para_to_group is None:
        para_to_group = {}
    chunks = []
    buffer = []
    buffer_tokens = 0
    buffer_ids = []

    for para in paragraphs:
        # Skip deleted/grouped paragraphs
        if para.get('deleted') or para.get('grouped_into'):
            continue

        text = para.get('text', '')
        para_tokens = estimate_tokens(text)
        para_id = para.get('id', 'unknown')

        # If buffer is getting too large, flush it
        if buffer_tokens + para_tokens > TARGET_TOKENS and buffer:
            # Create chunk from buffer
            chunk_text = "\n\n".join(buffer)
            chunk_data = {
                "content": chunk_text,
                "source_ids": buffer_ids.copy(),
                "source_id": f"{book_slug}/{buffer_ids[0]}",
                "full_doc_id": f"{book_slug}/{buffer_ids[0]}",
                "source_chunk_index": len(chunks)  # LightRAG expects this
            }
            # Add group_id if first paragraph has one
            if buffer_ids[0] in para_to_group:
                chunk_data["group_id"] = para_to_group[buffer_ids[0]]
            chunks.append(chunk_data)

            # Keep overlap: last portion of previous chunk
            overlap_text = get_last_n_tokens(chunk_text, OVERLAP_TOKENS)
            buffer = [overlap_text] if overlap_text else []
            buffer_tokens = estimate_tokens(overlap_text) if overlap_text else 0
            buffer_ids = []

        buffer.append(text)
        buffer_ids.append(para_id)
        buffer_tokens += para_tokens

    # Flush remaining buffer
    if buffer:
        chunk_text = "\n\n".join(buffer)
        chunk_data = {
            "content": chunk_text,
            "source_ids": buffer_ids.copy(),
            "source_id": f"{book_slug}/{buffer_ids[0]}",
            "full_doc_id": f"{book_slug}/{buffer_ids[0]}",
            "source_chunk_index": len(chunks)
        }
        # Add group_id if first paragraph has one
        if buffer_ids[0] in para_to_group:
            chunk_data["group_id"] = para_to_group[buffer_ids[0]]
        chunks.append(chunk_data)

    return chunks


def get_last_n_tokens(text: str, n_tokens: int) -> str:
    """Get approximately last N tokens of text, ending at sentence boundary."""
    words = text.split()
    target_words = int(n_tokens / 1.3)  # Convert tokens back to words

    if len(words) <= target_words:
        return text

    # Get last N words
    last_words = words[-target_words:]
    result = ' '.join(last_words)

    # Try to start at sentence boundary
    sentence_starts = [m.start() for m in re.finditer(r'[.!?]\s+[A-Z]', result)]
    if sentence_starts:
        # Start from the last sentence boundary
        result = result[sentence_starts[-1]+2:]

    return result


def build_contextual_chunk(
    para: Dict,
    all_paras: List[Dict],
    idx: int,
    book_slug: str,
    chunk_index: int = 0,
    para_to_group: Dict[int, str] = None
) -> Dict:
    """
    Build a chunk with contextual snippets (for paragraph-level chunks).
    Adds ~150 chars before and after for context.
    """
    if para_to_group is None:
        para_to_group = {}
    text = para.get('text', '')
    para_id = para.get('id', 'unknown')

    # Get previous context
    prev_text = ""
    if idx > 0:
        prev_para = all_paras[idx - 1]
        if not prev_para.get('deleted') and not prev_para.get('grouped_into'):
            prev_text = prev_para.get('text', '')[-CONTEXT_CHARS:]

    # Get next context
    next_text = ""
    if idx < len(all_paras) - 1:
        next_para = all_paras[idx + 1]
        if not next_para.get('deleted') and not next_para.get('grouped_into'):
            next_text = next_para.get('text', '')[:CONTEXT_CHARS]

    # Build content with context markers
    content = text
    if prev_text:
        content = f"[...{prev_text}]\n\n{content}"
    if next_text:
        content = f"{content}\n\n[{next_text}...]"

    chunk_data = {
        "content": content,
        "source_ids": [para_id],
        "source_id": f"{book_slug}/{para_id}",
        "full_doc_id": f"{book_slug}/{para_id}",
        "source_chunk_index": chunk_index
    }
    # Add group_id if paragraph has one
    if para_id in para_to_group:
        chunk_data["group_id"] = para_to_group[para_id]
    return chunk_data


def export_for_lightrag(
    book_data: Dict,
    use_merged_chunks: bool = True
) -> Dict:
    """
    Transform annotation JSON to LightRAG custom_kg format.

    Args:
        book_data: Annotation tool JSON export
        use_merged_chunks: If True, merge paragraphs to ~512 tokens.
                          If False, use paragraph-level with context.

    Returns:
        Dictionary with chunks, entities, and relations.
    """
    chunks = []
    entities = []
    relations = []
    seen_entities: Set[str] = set()

    book_meta = book_data.get('book_metadata', {})
    book_slug = book_meta.get('slug', 'unknown-book')
    book_title = book_meta.get('title', 'Unknown Book')
    book_author = book_meta.get('author', 'Unknown Author')

    # Add BOOK entity
    book_entity_id = f"book:{book_slug}"
    entities.append({
        "entity_name": book_slug,
        "entity_type": "BOOK",
        "description": f"{book_title} by {book_author}",
        "source_id": book_entity_id
    })
    seen_entities.add(book_entity_id)

    # Flatten all paragraphs
    all_paras = []
    for chapter in book_data.get('structure', []):
        for para in chapter.get('paragraphs', []):
            all_paras.append(para)

    # Build para_id → group_id mapping from groups
    para_to_group = {}
    for group in book_data.get('groups', []):
        group_id = group.get('id') or group.get('group_id')  # Support both key names
        if group_id:
            for para_id in group.get('paragraph_ids', []) or group.get('para_ids', []):
                para_to_group[para_id] = group_id

    # Build chunks
    if use_merged_chunks:
        chunks = merge_paragraphs_to_chunks(all_paras, book_slug, para_to_group)
    else:
        # Paragraph-level with context
        for idx, para in enumerate(all_paras):
            if para.get('deleted') or para.get('grouped_into'):
                continue
            chunk = build_contextual_chunk(para, all_paras, idx, book_slug, len(chunks), para_to_group)
            chunks.append(chunk)

    # Process each paragraph for entities and relations
    para_to_chunk = {}  # Map paragraph ID to chunk source_id
    for chunk in chunks:
        for pid in chunk.get('source_ids', []):
            para_to_chunk[pid] = chunk['source_id']

    for para in all_paras:
        if para.get('deleted') or para.get('grouped_into'):
            continue

        para_id = para.get('id', 'unknown')
        chunk_id = para_to_chunk.get(para_id, f"{book_slug}/{para_id}")

        # PARAGRAPH → BOOK relation
        relations.append({
            "src_id": chunk_id,
            "tgt_id": book_slug,
            "description": "belongs_to",
            "keywords": "structure, contains",
            "weight": 1.0,
            "source_id": chunk_id
        })

        # Process Quran references
        for ref_data in para.get('quran_refs', []):
            if not ref_data.get('verified', False):
                continue  # Only use verified refs

            ref = ref_data.get('ref', '')
            if not ref:
                continue

            ref_normalized = normalize_entity(ref, "QURAN_REF")
            ref_entity_id = f"quran:{ref_normalized}"

            # Add entity if new
            if ref_entity_id not in seen_entities:
                entities.append({
                    "entity_name": ref_normalized,
                    "entity_type": "QURAN_REF",
                    "description": f"Quran verse {ref_normalized}",
                    "source_id": ref_entity_id
                })
                seen_entities.add(ref_entity_id)

            # CHUNK → QURAN_REF relation
            relations.append({
                "src_id": chunk_id,
                "tgt_id": ref_normalized,
                "description": "cites",
                "keywords": "quran, verse, citation",
                "weight": 1.0,
                "source_id": chunk_id
            })

        # Process Hadith references
        for ref_data in para.get('hadith_refs', []):
            if not ref_data.get('verified', False):
                continue

            ref = ref_data.get('ref', '')
            if not ref:
                continue

            ref_normalized = normalize_entity(ref, "HADITH_REF")
            ref_entity_id = f"hadith:{ref_normalized}"

            if ref_entity_id not in seen_entities:
                entities.append({
                    "entity_name": ref_normalized,
                    "entity_type": "HADITH_REF",
                    "description": f"Hadith {ref_normalized}",
                    "source_id": ref_entity_id
                })
                seen_entities.add(ref_entity_id)

            relations.append({
                "src_id": chunk_id,
                "tgt_id": ref_normalized,
                "description": "cites",
                "keywords": "hadith, prophetic, citation",
                "weight": 1.0,
                "source_id": chunk_id
            })

        # Process concepts
        for concept in para.get('concepts', []):
            concept_normalized = normalize_entity(concept, "CONCEPT")
            concept_entity_id = f"concept:{concept_normalized}"

            if concept_entity_id not in seen_entities:
                entities.append({
                    "entity_name": concept_normalized,
                    "entity_type": "CONCEPT",
                    "description": f"Theme: {concept_normalized}",
                    "source_id": concept_entity_id
                })
                seen_entities.add(concept_entity_id)

            relations.append({
                "src_id": chunk_id,
                "tgt_id": concept_normalized,
                "description": "discusses",
                "keywords": "theme, concept, topic",
                "weight": 1.0,
                "source_id": chunk_id
            })

        # Process verse aspects (multi-aspect discovery)
        for va in para.get('verse_aspects', []):
            ref = va.get('ref', '')
            aspect = va.get('aspect', '')
            interpretation = va.get('interpretation', '')

            if not ref or not aspect:
                continue

            # Normalize the base verse reference
            ref_normalized = normalize_entity(ref, "QURAN_REF")
            aspect_normalized = aspect.lower().replace(' ', '_')

            # Create VERSE_ASPECT entity (e.g., "3:195_patience")
            aspect_entity_name = f"{ref_normalized}_{aspect_normalized}"
            aspect_entity_id = f"verse_aspect:{aspect_entity_name}"

            if aspect_entity_id not in seen_entities:
                entities.append({
                    "entity_name": aspect_entity_name,
                    "entity_type": "VERSE_ASPECT",
                    "description": interpretation or f"{ref_normalized} on {aspect}",
                    "source_id": aspect_entity_id
                })
                seen_entities.add(aspect_entity_id)

            # CHUNK → VERSE_ASPECT relation
            relations.append({
                "src_id": chunk_id,
                "tgt_id": aspect_entity_name,
                "description": "illustrates",
                "keywords": "interpretation, teaching, aspect",
                "weight": 1.0,
                "source_id": chunk_id
            })

            # VERSE_ASPECT → QURAN_REF relation (link aspect to base verse)
            quran_entity_id = f"quran:{ref_normalized}"
            if quran_entity_id not in seen_entities:
                entities.append({
                    "entity_name": ref_normalized,
                    "entity_type": "QURAN_REF",
                    "description": f"Quran verse {ref_normalized}",
                    "source_id": quran_entity_id
                })
                seen_entities.add(quran_entity_id)

            relations.append({
                "src_id": aspect_entity_name,
                "tgt_id": ref_normalized,
                "description": "aspect_of",
                "keywords": "interpretation, meaning",
                "weight": 1.0,
                "source_id": chunk_id
            })

        # Process people
        for person in para.get('people', []):
            person_normalized = normalize_entity(person, "PERSON")
            person_entity_id = f"person:{person_normalized}"

            if person_entity_id not in seen_entities:
                entities.append({
                    "entity_name": person_normalized,
                    "entity_type": "PERSON",
                    "description": f"Person: {person}",
                    "source_id": person_entity_id
                })
                seen_entities.add(person_entity_id)

            relations.append({
                "src_id": chunk_id,
                "tgt_id": person_normalized,
                "description": "mentions",
                "keywords": "person, name, figure",
                "weight": 1.0,
                "source_id": chunk_id
            })

        # Process places
        for place in para.get('places', []):
            place_normalized = place.lower().strip()
            place_entity_id = f"place:{place_normalized}"

            if place_entity_id not in seen_entities:
                entities.append({
                    "entity_name": place_normalized,
                    "entity_type": "PLACE",
                    "description": f"Location: {place}",
                    "source_id": place_entity_id
                })
                seen_entities.add(place_entity_id)

            relations.append({
                "src_id": chunk_id,
                "tgt_id": place_normalized,
                "description": "mentions",
                "keywords": "place, location, geography",
                "weight": 1.0,
                "source_id": chunk_id
            })

    return {
        "chunks": chunks,
        "entities": entities,
        "relationships": relations,  # LightRAG expects "relationships" not "relations"
        "metadata": {
            "book_slug": book_slug,
            "book_title": book_title,
            "total_chunks": len(chunks),
            "total_entities": len(entities),
            "total_relationships": len(relations),
            "use_merged_chunks": use_merged_chunks,
            "target_tokens": TARGET_TOKENS,
            "overlap_tokens": OVERLAP_TOKENS
        }
    }


def export_book_file(
    input_path: str,
    output_path: Optional[str] = None,
    use_merged_chunks: bool = True
) -> str:
    """
    Export a book JSON file to LightRAG format.

    Args:
        input_path: Path to annotation JSON file
        output_path: Output path (default: adds _lightrag suffix)
        use_merged_chunks: If True, merge paragraphs to ~512 tokens

    Returns:
        Path to output file
    """
    with open(input_path, 'r') as f:
        book_data = json.load(f)

    lightrag_data = export_for_lightrag(book_data, use_merged_chunks)

    if output_path is None:
        output_path = input_path.replace('.json', '_lightrag.json')

    with open(output_path, 'w') as f:
        json.dump(lightrag_data, f, indent=2, ensure_ascii=False)

    print(f"Exported to: {output_path}")
    print(f"  Chunks: {lightrag_data['metadata']['total_chunks']}")
    print(f"  Entities: {lightrag_data['metadata']['total_entities']}")
    print(f"  Relations: {lightrag_data['metadata']['total_relationships']}")

    return output_path


# CLI usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export annotation JSON to LightRAG format")
    parser.add_argument("input_json", help="Path to annotation JSON file")
    parser.add_argument("--output", help="Output path (default: input_lightrag.json)")
    parser.add_argument("--no-merge", action="store_true",
                        help="Use paragraph-level chunks instead of merged chunks")

    args = parser.parse_args()

    export_book_file(
        args.input_json,
        args.output,
        use_merged_chunks=not args.no_merge
    )
