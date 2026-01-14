#!/usr/bin/env python3
"""
Fast Text Matcher Benchmark Script

Tests DOCX ↔ PDF matching performance with real data.

Usage:
    python test_fast_matcher.py --benchmark        # Use Peace in Kashmir
    python test_fast_matcher.py --docx <path> --pdf <path>
"""

import sys
import time
import argparse
from io import BytesIO
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from extractors.docx_parser import extract_paragraphs
from services.pdf_handler import extract_pdf_pages
from services.fast_text_matcher import match_paragraphs, get_match_statistics


def test_peace_in_kashmir():
    """Benchmark with Peace in Kashmir book."""
    print("=" * 70)
    print("FAST TEXT MATCHER BENCHMARK - Peace in Kashmir")
    print("=" * 70)

    # File paths
    docx_path = '/root/islamic_app_demo/data/peace_in_kashmir_book/document.docx'
    pdf_path = '/root/islamic_app_demo/data/peace_in_kashmir_book/document.pdf'

    # Check files exist
    if not Path(docx_path).exists():
        print(f"❌ DOCX file not found: {docx_path}")
        return False

    if not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return False

    print(f"\n📄 Loading files...")
    print(f"  DOCX: {docx_path}")
    print(f"  PDF:  {pdf_path}")

    # Load DOCX
    try:
        with open(docx_path, 'rb') as f:
            docx_bytes = BytesIO(f.read())
        paragraphs = extract_paragraphs(docx_bytes)
        print(f"  ✅ Extracted {len(paragraphs)} paragraphs from DOCX")
    except Exception as e:
        print(f"  ❌ Failed to extract DOCX: {e}")
        return False

    # Load PDF
    try:
        with open(pdf_path, 'rb') as f:
            pdf_bytes = BytesIO(f.read())
        pdf_pages = extract_pdf_pages(pdf_bytes)
        print(f"  ✅ Extracted {len(pdf_pages)} pages from PDF")
    except Exception as e:
        print(f"  ❌ Failed to extract PDF: {e}")
        return False

    # Extract texts
    para_texts = [p['text'] for p in paragraphs if p.get('type') == 'paragraph']
    page_texts = [pg['text'] for pg in pdf_pages]

    print(f"\n🔍 Matching {len(para_texts)} paragraphs against {len(page_texts)} PDF pages...")

    # Benchmark matching
    start = time.time()
    matches = match_paragraphs(para_texts, page_texts, threshold=70)
    elapsed = time.time() - start

    # Calculate statistics
    stats = get_match_statistics(matches)

    # Print results
    print(f"\n" + "=" * 70)
    print(f"RESULTS")
    print("=" * 70)

    print(f"\n⏱️  Performance:")
    print(f"  Total time:    {elapsed:.2f}s")
    print(f"  Per paragraph: {elapsed/len(para_texts)*1000:.1f}ms")
    print(f"  Throughput:    {len(para_texts)/elapsed:.1f} paras/second")

    print(f"\n✅ Matching:")
    print(f"  Matched:   {stats['total']:3d}/{len(para_texts)} ({stats['total']/len(para_texts)*100:.1f}%)")
    print(f"  Unmatched: {len(para_texts) - stats['total']:3d}")
    print(f"  Avg score: {stats['avg_score']:.1f}")

    print(f"\n📊 Method Breakdown:")
    print(f"  Exact:  {stats['exact']:3d} ({stats['exact_pct']:.1f}%)")
    print(f"  Token:  {stats['token']:3d} ({stats['token_pct']:.1f}%)")
    print(f"  Fuzzy:  {stats['fuzzy']:3d} ({stats['fuzzy_pct']:.1f}%)")

    # Show sample matches
    print(f"\n📝 Sample Matches (first 5):")
    for i, match in enumerate(matches[:5], 1):
        print(f"\n  [{i}] Para {match['docx_idx']} → Page {match['pdf_idx']+1}")
        print(f"      Score: {match['score']}% ({match['method']})")
        print(f"      DOCX: {match['docx_text_preview'][:70]}...")
        print(f"      PDF:  {match['pdf_text_preview'][:70]}...")

    # Success criteria
    print(f"\n" + "=" * 70)
    print("EVALUATION")
    print("=" * 70)

    success = True

    if elapsed > 3.0:
        print(f"  ⚠️  SLOW: Expected <3s, got {elapsed:.2f}s")
        success = False
    else:
        print(f"  ✅ FAST: {elapsed:.2f}s (target: <3s)")

    if stats['total'] / len(para_texts) < 0.8:
        print(f"  ⚠️  LOW MATCH RATE: {stats['total']/len(para_texts)*100:.1f}% (target: >80%)")
        success = False
    else:
        print(f"  ✅ GOOD MATCH RATE: {stats['total']/len(para_texts)*100:.1f}%")

    if stats['avg_score'] < 85:
        print(f"  ⚠️  LOW CONFIDENCE: {stats['avg_score']:.1f} (target: >85)")
    else:
        print(f"  ✅ HIGH CONFIDENCE: {stats['avg_score']:.1f}")

    return success


def test_custom_files(docx_path: str, pdf_path: str):
    """Test with custom DOCX and PDF files."""
    print("=" * 70)
    print(f"FAST TEXT MATCHER BENCHMARK - Custom Files")
    print("=" * 70)

    # Check files exist
    if not Path(docx_path).exists():
        print(f"❌ DOCX file not found: {docx_path}")
        return False

    if not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return False

    print(f"\n📄 Loading files...")
    print(f"  DOCX: {docx_path}")
    print(f"  PDF:  {pdf_path}")

    # Load DOCX
    try:
        with open(docx_path, 'rb') as f:
            docx_bytes = BytesIO(f.read())
        paragraphs = extract_paragraphs(docx_bytes)
        print(f"  ✅ Extracted {len(paragraphs)} paragraphs from DOCX")
    except Exception as e:
        print(f"  ❌ Failed to extract DOCX: {e}")
        return False

    # Load PDF
    try:
        with open(pdf_path, 'rb') as f:
            pdf_bytes = BytesIO(f.read())
        pdf_pages = extract_pdf_pages(pdf_bytes)
        print(f"  ✅ Extracted {len(pdf_pages)} pages from PDF")
    except Exception as e:
        print(f"  ❌ Failed to extract PDF: {e}")
        return False

    # Extract texts (only paragraph type)
    para_texts = [p['text'] for p in paragraphs if p.get('type') == 'paragraph']
    page_texts = [pg['text'] for pg in pdf_pages]

    print(f"\n🔍 Matching {len(para_texts)} paragraphs against {len(page_texts)} PDF pages...")

    # Benchmark matching
    start = time.time()
    matches = match_paragraphs(para_texts, page_texts, threshold=70)
    elapsed = time.time() - start

    # Calculate statistics
    stats = get_match_statistics(matches)

    # Print results
    print(f"\n✅ Matched {stats['total']}/{len(para_texts)} paragraphs in {elapsed:.2f}s")
    print(f"   Average: {elapsed/len(para_texts)*1000:.1f}ms per paragraph")
    print(f"\n   Exact:  {stats['exact']:3d} ({stats['exact_pct']:.1f}%)")
    print(f"   Token:  {stats['token']:3d} ({stats['token_pct']:.1f}%)")
    print(f"   Fuzzy:  {stats['fuzzy']:3d} ({stats['fuzzy_pct']:.1f}%)")

    return True


def unit_test():
    """Quick unit test with synthetic data."""
    print("=" * 70)
    print("UNIT TEST")
    print("=" * 70)

    # Test data
    docx = [
        'This is paragraph one with some text.',
        'This is paragraph two with more text.',
        'A third paragraph here.',
        'Fourth paragraph content.'
    ]

    pdf = [
        'This is paragraph one with some text.',          # Exact match
        'This  is  paragraph two  with more  text.',      # Extra spaces (should token match)
        'A third  paragraph here.',                       # Minor variation
        'Fourth para graph content.'                       # Word split (should fuzzy match)
    ]

    print(f"\nTesting {len(docx)} paragraphs...")

    matches = match_paragraphs(docx, pdf, threshold=70)
    stats = get_match_statistics(matches)

    print(f"\nResults:")
    print(f"  Matched: {stats['total']}/{len(docx)}")
    print(f"  Exact:   {stats['exact']}")
    print(f"  Token:   {stats['token']}")
    print(f"  Fuzzy:   {stats['fuzzy']}")

    # Verify expected matches
    assert len(matches) == 4, f"Expected 4 matches, got {len(matches)}"
    assert matches[0]['method'] in ['exact', 'token'], "First match should be exact or token"

    print(f"\n✅ Unit test passed!")
    return True


def main():
    parser = argparse.ArgumentParser(description='Benchmark fast text matcher')
    parser.add_argument('--benchmark', action='store_true',
                       help='Run benchmark with Peace in Kashmir')
    parser.add_argument('--docx', type=str, help='Path to DOCX file')
    parser.add_argument('--pdf', type=str, help='Path to PDF file')
    parser.add_argument('--unit-test', action='store_true',
                       help='Run unit test with synthetic data')

    args = parser.parse_args()

    if args.unit_test:
        success = unit_test()
    elif args.benchmark:
        success = test_peace_in_kashmir()
    elif args.docx and args.pdf:
        success = test_custom_files(args.docx, args.pdf)
    else:
        print("Usage:")
        print("  python test_fast_matcher.py --benchmark")
        print("  python test_fast_matcher.py --docx <path> --pdf <path>")
        print("  python test_fast_matcher.py --unit-test")
        return 1

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
