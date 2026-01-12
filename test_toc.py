#!/usr/bin/env python3
"""
TOC Detection Test Suite
Tests the is_toc_entry() function for Table of Contents detection.
"""
import re


def is_toc_entry(text: str) -> bool:
    """Detect TOC/Index entries. Returns False on any error (fail-safe)."""
    try:
        text = text.strip()

        # Early exits (fast)
        if len(text) > 80 or len(text) < 5:
            return False
        if not text[-1].isdigit():
            return False

        # Must have leader pattern (dots or spaces)
        has_dots = bool(re.search(r'\.{3,}\s*\d+$', text))
        has_spaces = bool(re.search(r'\s{5,}\d+$', text))

        if not (has_dots or has_spaces):
            return False

        # Reject normal sentences (contains sentence-ending punctuation mid-text)
        if re.search(r'\.\s+[A-Z]', text[:-10]):
            return False

        return True

    except Exception:
        return False  # Fail-safe: don't flag on error


# Test suite - MUST pass ALL tests
tests = [
    # Valid TOC entries
    ("Chapter One ............. 12", True),
    ("Introduction          5", True),
    ("مقدمہ ............. ۱۲", True),  # Urdu: Introduction ... 12
    ("Part 1 ..... 45", True),
    ("Index........78", True),
    ("Conclusion...............234", True),
    ("Appendix A      100", True),

    # Invalid - normal sentences
    ("I was born in 1968", False),
    ("Dr. Smith said... 2024", False),
    ("The year 2024 was great", False),
    ("This happened in 1999. Then something else.", False),

    # Edge cases
    ("", False),
    (None, False),  # Error case - should not crash
    ("x" * 100, False),  # Too long
    ("Short 1", False),  # Too short (< 5 chars before number)
    ("No digit at end ...", False),
    ("Just a number 42", False),  # No leader pattern

    # False positives to avoid
    ("Copyright © 2024", False),  # Pattern_match should catch this
    ("Page 42", False),  # Page number detection should catch this
    ("Chapter 1", False),  # No leader pattern
    ("See page 123", False),  # No leader pattern
]

print("=" * 60)
print("TOC Detection Test Suite")
print("=" * 60)

passed = 0
failed = 0

for text, expected in tests:
    try:
        result = is_toc_entry(text) if text is not None else is_toc_entry(None)
    except Exception as e:
        result = f"ERROR: {e}"

    if result == expected:
        status = "✓ PASS"
        passed += 1
    else:
        status = "✗ FAIL"
        failed += 1

    text_display = repr(text[:30] + "..." if text and len(text) > 30 else text)
    print(f"{status} is_toc_entry({text_display}) = {result}, expected {expected}")

print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    print("❌ TESTS FAILED - DO NOT DEPLOY")
    exit(1)
else:
    print("✅ ALL TESTS PASSED - SAFE TO DEPLOY")
    exit(0)
