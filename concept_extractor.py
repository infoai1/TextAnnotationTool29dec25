"""
Concept Extractor for Maulana's Literature
Uses LLM (Gemini or DeepSeek) to extract concepts, people, places, historical events,
and verse aspects (what teaching a Quran/Hadith reference illustrates).
Processes paragraphs with context window (3 above + target + 3 below).

Created: January 3, 2025
Updated: January 3, 2025 - Added Gemini support + verse aspect extraction
"""

import json
import asyncio
import yaml
import os
import re
from typing import List, Dict, Any, Optional, Literal
from openai import AsyncOpenAI
import google.generativeai as genai

# Load taxonomy
TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), 'taxonomy', 'maulana_taxonomy.yaml')

# Gemini API key rotation for free tier (15 RPM per key)
class GeminiKeyRotator:
    """Rotate through multiple Gemini API keys for higher throughput."""

    def __init__(self):
        self.keys = []
        for i in range(1, 4):
            key = os.environ.get(f'GEMINI_API_KEY_{i}') or os.environ.get(f'GEMINI_API_KEY')
            if key:
                self.keys.append(key)
        self.index = 0

    def get_next_key(self) -> Optional[str]:
        if not self.keys:
            return None
        key = self.keys[self.index % len(self.keys)]
        self.index += 1
        return key

    def has_keys(self) -> bool:
        return len(self.keys) > 0

gemini_rotator = GeminiKeyRotator()

_TAXONOMY_CACHE = None

def load_taxonomy() -> Dict:
    """Load the concept taxonomy from YAML file (cached)."""
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is None:
        with open(TAXONOMY_PATH, 'r') as f:
            _TAXONOMY_CACHE = yaml.safe_load(f)
    return _TAXONOMY_CACHE

def get_concept_list() -> List[str]:
    """Get flat list of all concepts (main + sub) from taxonomy."""
    taxonomy = load_taxonomy()
    concepts = []

    for category_key, category_data in taxonomy.get('categories', {}).items():
        # Add main category
        concepts.append(category_key.lower())
        # Add subcategories
        for sub in category_data.get('subcategories', []):
            concepts.append(sub.lower())

    return concepts

def get_people_list() -> List[str]:
    """Get list of known people from taxonomy."""
    taxonomy = load_taxonomy()
    people = []

    entity_types = taxonomy.get('entity_types', {})
    people_data = entity_types.get('people', {})

    for category, names in people_data.items():
        people.extend(names)

    return people

def get_places_list() -> List[str]:
    """Get list of known places from taxonomy."""
    taxonomy = load_taxonomy()
    places = []

    entity_types = taxonomy.get('entity_types', {})
    places_data = entity_types.get('places', {})

    for category, names in places_data.items():
        places.extend(names)

    return places


# Build prompt with concept list
CONCEPT_LIST = get_concept_list()
PEOPLE_LIST = get_people_list()
PLACES_LIST = get_places_list()

EXTRACTION_PROMPT = """You are analyzing Islamic spiritual literature by Maulana Wahiduddin Khan.

I will give you 7 paragraphs for CONTEXT. Extract entities ONLY from the TARGET paragraph (marked with >>>).

## CONTEXT PARAGRAPHS:
{context}

## INSTRUCTIONS:

1. **concepts**: Select ONLY from this list (use exact spelling):
{concepts}

2. **people**: Identify people mentioned. Use these canonical names if matching:
{people}
For others, use full name as written.

3. **places**: Identify locations. Use these canonical names if matching:
{places}

4. **historical_events**: If a year/date is mentioned, extract:
   - year: The year (e.g., "1947", "7th century", "622 AH")
   - event_summary: Brief description (max 10 words)
   - Use the CONTEXT to understand what the year refers to

5. **islamic_terms**: Arabic/Islamic terms used (e.g., tawakkul, sabr, shukr)

6. **verse_aspects**: For EACH Quran or Hadith reference in the paragraph:
   - ref: The reference (e.g., "3:195", "Bukhari:1234")
   - aspect: What teaching/theme is being illustrated (1-3 words, e.g., "patience", "divine_response")
   - interpretation: Brief description of Maulana's interpretation angle (max 15 words)

   IMPORTANT: Same verse can appear in different books with DIFFERENT aspects. Extract what THIS paragraph uses it for.

## OUTPUT FORMAT (JSON only, no explanation):
{{
  "concepts": [],
  "people": [],
  "places": [],
  "historical_events": [
    {{"year": "1947", "event_summary": "Partition of India and Pakistan"}}
  ],
  "islamic_terms": [],
  "verse_aspects": [
    {{"ref": "3:195", "aspect": "patience", "interpretation": "Using companions' migration to illustrate patience in adversity"}}
  ]
}}

If nothing found, return empty arrays. ONLY extract from TARGET paragraph, use context for understanding."""


async def extract_from_paragraph(
    client: AsyncOpenAI,
    paragraphs: List[Dict],
    target_idx: int,
    model: str = "deepseek-chat"
) -> Dict[str, Any]:
    """
    Extract entities from a single paragraph using context window.

    Args:
        client: AsyncOpenAI client configured for DeepSeek
        paragraphs: Full list of paragraphs
        target_idx: Index of target paragraph to extract from
        model: Model to use (default: deepseek-chat)

    Returns:
        Dictionary with extracted entities
    """
    # Build context window: 3 above + target + 3 below
    start_idx = max(0, target_idx - 3)
    end_idx = min(len(paragraphs), target_idx + 4)

    context_parts = []
    for i in range(start_idx, end_idx):
        para = paragraphs[i]
        text = para.get('text', '')[:500]  # Limit length

        if i == target_idx:
            context_parts.append(f">>> TARGET PARAGRAPH (p_{para.get('id', i)}):\n{text}")
        else:
            context_parts.append(f"[p_{para.get('id', i)}]:\n{text}")

    context = "\n\n".join(context_parts)

    # Format prompt
    prompt = EXTRACTION_PROMPT.format(
        context=context,
        concepts=", ".join(CONCEPT_LIST[:50]),  # First 50 to fit context
        people=", ".join(PEOPLE_LIST[:30]),
        places=", ".join(PLACES_LIST[:20])
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Extract entities from Islamic text. Return JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )

        result_text = response.choices[0].message.content.strip()

        # Parse JSON (handle markdown code blocks)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)
        result['para_id'] = paragraphs[target_idx].get('id', target_idx)
        return result

    except Exception as e:
        return {
            'para_id': paragraphs[target_idx].get('id', target_idx),
            'error': str(e),
            'concepts': [],
            'people': [],
            'places': [],
            'historical_events': [],
            'islamic_terms': [],
            'verse_aspects': []
        }


async def extract_from_paragraph_gemini(
    paragraphs: List[Dict],
    target_idx: int,
    model: str = "gemini-2.0-flash"
) -> Dict[str, Any]:
    """
    Extract entities using Gemini API with key rotation.

    Args:
        paragraphs: Full list of paragraphs
        target_idx: Index of target paragraph to extract from
        model: Gemini model to use (default: gemini-1.5-flash for free tier)

    Returns:
        Dictionary with extracted entities
    """
    api_key = gemini_rotator.get_next_key()
    if not api_key:
        return {
            'para_id': paragraphs[target_idx].get('id', target_idx),
            'error': 'No Gemini API keys configured',
            'concepts': [], 'people': [], 'places': [],
            'historical_events': [], 'islamic_terms': [], 'verse_aspects': []
        }

    # Build context window: 3 above + target + 3 below
    start_idx = max(0, target_idx - 3)
    end_idx = min(len(paragraphs), target_idx + 4)

    context_parts = []
    for i in range(start_idx, end_idx):
        para = paragraphs[i]
        text = para.get('text', '')[:500]  # Limit length

        if i == target_idx:
            context_parts.append(f">>> TARGET PARAGRAPH (p_{para.get('id', i)}):\n{text}")
        else:
            context_parts.append(f"[p_{para.get('id', i)}]:\n{text}")

    context = "\n\n".join(context_parts)

    # Format prompt
    prompt = EXTRACTION_PROMPT.format(
        context=context,
        concepts=", ".join(CONCEPT_LIST[:50]),
        people=", ".join(PEOPLE_LIST[:30]),
        places=", ".join(PLACES_LIST[:20])
    )

    try:
        genai.configure(api_key=api_key)
        model_instance = genai.GenerativeModel(model)

        response = await asyncio.to_thread(
            model_instance.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500
            )
        )

        result_text = response.text.strip()

        # Parse JSON (handle markdown code blocks)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)
        result['para_id'] = paragraphs[target_idx].get('id', target_idx)
        return result

    except Exception as e:
        return {
            'para_id': paragraphs[target_idx].get('id', target_idx),
            'error': str(e),
            'concepts': [], 'people': [], 'places': [],
            'historical_events': [], 'islamic_terms': [], 'verse_aspects': []
        }


async def extract_batch(
    paragraphs: List[Dict],
    api_key: Optional[str] = None,
    base_url: str = "https://api.deepseek.com",
    batch_size: int = 5,
    model: str = "deepseek-chat",
    provider: Literal["deepseek", "gemini"] = "gemini",
    pause_seconds: float = 1.0,
    progress_callback: Optional[callable] = None
) -> List[Dict]:
    """
    Extract entities from all paragraphs in batches.

    Args:
        paragraphs: List of paragraph dictionaries
        api_key: DeepSeek API key (not needed for Gemini - uses env vars)
        base_url: API base URL (for DeepSeek)
        batch_size: Number of concurrent requests
        model: Model to use
        provider: "gemini" or "deepseek"
        pause_seconds: Delay between batches (for rate limiting)
        progress_callback: Optional callback(processed, total) for UI updates

    Returns:
        List of extraction results for each paragraph
    """
    results = []
    total = len(paragraphs)

    if provider == "deepseek":
        if not api_key:
            api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("DeepSeek API key required")
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    for i in range(0, total, batch_size):
        batch_indices = range(i, min(i + batch_size, total))

        # Create tasks for batch based on provider
        if provider == "gemini":
            tasks = [
                extract_from_paragraph_gemini(paragraphs, idx, model="gemini-2.0-flash")
                for idx in batch_indices
            ]
        else:
            tasks = [
                extract_from_paragraph(client, paragraphs, idx, model)
                for idx in batch_indices
            ]

        # Run batch concurrently
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

        processed = min(i + batch_size, total)
        print(f"Processed {processed}/{total} paragraphs")

        # Callback for UI progress
        if progress_callback:
            progress_callback(processed, total)

        # Rate limit delay
        await asyncio.sleep(pause_seconds)

    return results


async def extract_batch_range(
    paragraphs: List[Dict],
    start_idx: int,
    count: int,
    provider: Literal["deepseek", "gemini"] = "gemini",
    pause_seconds: float = 1.0,
    progress_callback: Optional[callable] = None
) -> List[Dict]:
    """
    Extract entities from a range of paragraphs (for "Extract 10" button).
    Skips deleted paragraphs and non-paragraph types (headers, quotes).

    Args:
        paragraphs: Full list of paragraphs
        start_idx: Starting index
        count: Number of paragraphs to process
        provider: "gemini" or "deepseek"
        pause_seconds: Delay between requests
        progress_callback: Optional callback(processed, total)

    Returns:
        List of extraction results
    """
    # Filter to only extractable paragraphs (not deleted, not grouped, type=paragraph)
    valid_indices = [
        i for i, p in enumerate(paragraphs)
        if not p.get('deleted')
        and not p.get('grouped_into')
        and p.get('type', 'paragraph') == 'paragraph'
        and p.get('extraction_status') != 'extracted'
    ]

    # Start from first valid after start_idx, take up to 'count' items
    valid_indices = [i for i in valid_indices if i >= start_idx][:count]

    if not valid_indices:
        return []

    results = []
    client = None
    if provider == "deepseek":
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    for i, idx in enumerate(valid_indices):
        if provider == "gemini":
            result = await extract_from_paragraph_gemini(paragraphs, idx)
        else:
            result = await extract_from_paragraph(client, paragraphs, idx)

        results.append(result)

        if progress_callback:
            progress_callback(i + 1, len(valid_indices))

        await asyncio.sleep(pause_seconds)

    return results


def merge_extractions_to_paragraphs(
    paragraphs: List[Dict],
    extractions: List[Dict]
) -> List[Dict]:
    """
    Merge extraction results back into paragraph data.

    Args:
        paragraphs: Original paragraph list
        extractions: Extraction results from LLM

    Returns:
        Updated paragraphs with extraction data
    """
    # Build lookup by para_id
    extraction_map = {e['para_id']: e for e in extractions}

    for para in paragraphs:
        para_id = para.get('id')
        if para_id in extraction_map:
            ext = extraction_map[para_id]
            para['concepts'] = ext.get('concepts', [])
            para['people'] = ext.get('people', [])
            para['places'] = ext.get('places', [])
            para['islamic_terms'] = ext.get('islamic_terms', [])
            para['verse_aspects'] = ext.get('verse_aspects', [])

            # Merge historical events into year_refs
            events = ext.get('historical_events', [])
            year_refs = para.get('year_refs', [])

            for event in events:
                year = event.get('year', '')
                summary = event.get('event_summary', '')

                # Try to match with existing year_ref
                matched = False
                for yr in year_refs:
                    if year in yr.get('text', ''):
                        yr['event_summary'] = summary
                        matched = True
                        break

                # If no match, add as new
                if not matched and year:
                    year_refs.append({
                        'text': year,
                        'event_summary': summary,
                        'detection': 'llm',
                        'verified': False
                    })

            para['year_refs'] = year_refs

            # Mark extraction status
            para['extraction_status'] = 'extracted'
            if ext.get('error'):
                para['extraction_status'] = 'error'
                para['extraction_error'] = ext['error']

    return paragraphs


def get_extraction_stats(paragraphs: List[Dict]) -> Dict:
    """Get statistics about extractions."""
    stats = {
        'total': len(paragraphs),
        'extracted': 0,
        'errors': 0,
        'pending': 0,
        'total_concepts': 0,
        'total_verse_aspects': 0,
        'total_people': 0,
        'total_places': 0,
        'total_events': 0
    }

    for para in paragraphs:
        status = para.get('extraction_status', 'pending')
        if status == 'extracted':
            stats['extracted'] += 1
        elif status == 'error':
            stats['errors'] += 1
        else:
            stats['pending'] += 1

        stats['total_concepts'] += len(para.get('concepts', []))
        stats['total_verse_aspects'] += len(para.get('verse_aspects', []))
        stats['total_people'] += len(para.get('people', []))
        stats['total_places'] += len(para.get('places', []))
        stats['total_events'] += len(para.get('year_refs', []))

    return stats


async def process_book(
    book_json_path: str,
    api_key: Optional[str] = None,
    output_path: Optional[str] = None,
    provider: Literal["deepseek", "gemini"] = "gemini"
) -> Dict:
    """
    Process a complete book JSON file.

    Args:
        book_json_path: Path to annotation tool JSON export
        api_key: DeepSeek API key (not needed for Gemini)
        output_path: Optional path to save result (default: adds _enriched suffix)
        provider: "gemini" or "deepseek"

    Returns:
        Enriched book data
    """
    # Load book
    with open(book_json_path, 'r') as f:
        book_data = json.load(f)

    # Flatten paragraphs from structure
    all_paragraphs = []
    for chapter in book_data.get('structure', []):
        for para in chapter.get('paragraphs', []):
            all_paragraphs.append(para)

    print(f"Processing {len(all_paragraphs)} paragraphs with {provider}...")

    # Extract entities
    extractions = await extract_batch(
        all_paragraphs,
        api_key=api_key,
        provider=provider,
        pause_seconds=1.0 if provider == "gemini" else 0.5
    )

    # Merge back
    all_paragraphs = merge_extractions_to_paragraphs(all_paragraphs, extractions)

    # Update book structure
    para_idx = 0
    for chapter in book_data.get('structure', []):
        for i, para in enumerate(chapter.get('paragraphs', [])):
            if para_idx < len(all_paragraphs):
                chapter['paragraphs'][i] = all_paragraphs[para_idx]
                para_idx += 1

    # Save result
    if output_path is None:
        output_path = book_json_path.replace('.json', '_enriched.json')

    with open(output_path, 'w') as f:
        json.dump(book_data, f, indent=2, ensure_ascii=False)

    print(f"Saved enriched data to: {output_path}")

    # Stats
    stats = get_extraction_stats(all_paragraphs)
    print(f"\nExtraction Stats:")
    print(f"  Paragraphs: {stats['extracted']}/{stats['total']} extracted, {stats['errors']} errors")
    print(f"  Concepts: {stats['total_concepts']}")
    print(f"  Verse Aspects: {stats['total_verse_aspects']}")
    print(f"  People: {stats['total_people']}")
    print(f"  Places: {stats['total_places']}")
    print(f"  Historical Events: {stats['total_events']}")

    return book_data


# CLI usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract concepts from annotated book")
    parser.add_argument("book_json", help="Path to annotation JSON file")
    parser.add_argument("--provider", choices=["gemini", "deepseek"], default="gemini",
                        help="LLM provider (default: gemini)")
    parser.add_argument("--api-key", help="DeepSeek API key (or set DEEPSEEK_API_KEY env)")
    parser.add_argument("--output", help="Output path (default: input_enriched.json)")

    args = parser.parse_args()

    if args.provider == "deepseek":
        api_key = args.api_key or os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            print("Error: Provide --api-key or set DEEPSEEK_API_KEY environment variable")
            exit(1)
    else:
        api_key = None
        if not gemini_rotator.has_keys():
            print("Error: Set GEMINI_API_KEY or GEMINI_API_KEY_1/2/3 environment variables")
            exit(1)
        print(f"Using {len(gemini_rotator.keys)} Gemini API key(s) with rotation")

    asyncio.run(process_book(args.book_json, api_key, args.output, args.provider))
