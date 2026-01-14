#!/usr/bin/env python3
"""
Test script to verify PDF page matching bug fixes.
Tests Bug #1, #2, and #3 fixes.
"""

import sys
sys.path.insert(0, '/root/annotation_tool')

from services.pdf_handler import find_paragraph_in_pdf, match_all_paragraphs_to_pages

def test_bug1_false_exact_match():
    """Test Bug #1 fix: No false exact matches with repeated phrases"""
    print("\n" + "="*60)
    print("TEST 1: Bug #1 - False Exact Match (Repeated Phrases)")
    print("="*60)

    # Mock PDF pages with repeated phrase
    pdf_pages = [
        {
            "page_number": 1,
            "text": "Table of Contents\n1. In the name of God, the Most Gracious, the Most Merciful - Introduction\n2. Peace in Islam"
        },
        {
            "page_number": 15,
            "text": "Some other content here about history and background of the topic being discussed in this chapter..."
        },
        {
            "page_number": 42,
            "text": "In the name of God, the Most Gracious, the Most Merciful. This chapter discusses the concept of peace in Islam. The Quran teaches us that peace is the foundation of all good actions and that we should strive for it in all aspects of our lives."
        }
    ]

    # Paragraph that should match page 42 (full paragraph, not TOC)
    para_text = "In the name of God, the Most Gracious, the Most Merciful. This chapter discusses the concept of peace in Islam. The Quran teaches us that peace is the foundation of all good actions and that we should strive for it in all aspects of our lives."

    result = find_paragraph_in_pdf(para_text, pdf_pages)

    print(f"Paragraph (first 80 chars): {para_text[:80]}...")
    print(f"\nResult: {result}")
    print(f"\nExpected page: 42")
    print(f"Actual page: {result['page_number']}")
    print(f"Match type: {result['match_type']}")
    print(f"Confidence: {result['confidence']}")

    if result['page_number'] == 42:
        print("\n✅ PASS: Correctly matched page 42 (not TOC on page 1)")
        return True
    else:
        print(f"\n❌ FAIL: Matched page {result['page_number']} instead of 42")
        return False


def test_bug2_window_boundary():
    """Test Bug #2 fix: Sliding window catches text at boundary positions"""
    print("\n" + "="*60)
    print("TEST 2: Bug #2 - Window Boundary Miss")
    print("="*60)

    # Mock PDF page with paragraph starting at position 75
    preceding_text = "A" * 75  # Exactly 75 chars of preceding text
    para_text = "The Kashmir issue is a complex matter that requires careful consideration. It involves historical, political, and social dimensions that must be understood in their proper context and with full awareness of all stakeholders."

    pdf_pages = [
        {
            "page_number": 5,
            "text": preceding_text + para_text
        }
    ]

    result = find_paragraph_in_pdf(para_text, pdf_pages)

    print(f"Paragraph starts at position: 75")
    print(f"Paragraph text: {para_text[:80]}...")
    print(f"\nResult: {result}")

    if result and result['page_number'] == 5:
        print(f"\n✅ PASS: Found paragraph at boundary position (page {result['page_number']})")
        print(f"   Match type: {result['match_type']}, Confidence: {result['confidence']}")
        return True
    else:
        print(f"\n❌ FAIL: Did not find paragraph at boundary position")
        print(f"   Expected: page 5, Got: {result}")
        return False


def test_bug3_cascading_fallback():
    """Test Bug #3 fix: Intelligent fallback prevents cascading errors"""
    print("\n" + "="*60)
    print("TEST 3: Bug #3 - Cascading Fallback Error")
    print("="*60)

    # Mock paragraphs: short ones followed by unmatched longer ones
    paragraphs = [
        {"text": "Short"},  # Too short, will be skipped
        {"text": "Another"},  # Too short, will be skipped
        {"text": "Third"},  # Too short, will be skipped
        {"text": "Fourth"},  # Too short, will be skipped
        {"text": "This is a longer unmatched paragraph number five that doesn't match any PDF page"},
        {"text": "This is another unmatched paragraph number six that also doesn't match"},
        {"text": "Unmatched paragraph seven continues the sequence without any matches"},
        {"text": "Unmatched paragraph eight is still not matching anything in the PDF"},
        {"text": "Finally paragraph nine should trigger page increment after 4+ unmatched"},
    ]

    pdf_pages = [
        {"page_number": 1, "text": "Page 1 content"},
        {"page_number": 2, "text": "Page 2 content"},
        {"page_number": 3, "text": "Page 3 content"},
        {"page_number": 4, "text": "Page 4 content"},
        {"page_number": 5, "text": "Page 5 content"},
    ]

    result = match_all_paragraphs_to_pages(paragraphs, pdf_pages)

    print("Paragraph assignments:")
    for i, para in enumerate(result):
        page_info = para.get('page_info', {})
        print(f"  Para {i+1}: page {page_info.get('page_number')}, "
              f"{page_info.get('match_type')}, conf={page_info.get('confidence')}")

    # Check if page incremented after consecutive unmatched
    page_numbers = [p['page_info']['page_number'] for p in result]
    unique_pages = len(set(page_numbers))

    print(f"\nUnique pages assigned: {unique_pages}")
    print(f"Page progression: {page_numbers}")

    if unique_pages > 1:
        print(f"\n✅ PASS: Page numbers incremented (not all stuck on page 1)")
        print(f"   This prevents cascading errors from one wrong match")
        return True
    else:
        print(f"\n❌ FAIL: All paragraphs stuck on same page (cascading error)")
        return False


def main():
    print("\n" + "#"*60)
    print("# PDF Page Matching Bug Fixes - Test Suite")
    print("#"*60)

    results = []

    # Run all tests
    results.append(("Bug #1 Fix", test_bug1_false_exact_match()))
    results.append(("Bug #2 Fix", test_bug2_window_boundary()))
    results.append(("Bug #3 Fix", test_bug3_cascading_fallback()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All bug fixes verified!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
