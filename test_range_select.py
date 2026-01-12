#!/usr/bin/env python3
"""Test range selection logic"""

def test_range_selection():
    """Simulate marking paragraphs in a range"""
    # Mock paragraphs
    paragraphs = [
        {'id': i, 'text': f'Paragraph {i}', 'potential_delete': False}
        for i in range(1, 21)  # 20 paragraphs
    ]

    # Simulate range selection: Mark 5-10
    start_id, end_id = 5, 10
    count = 0
    for p in paragraphs:
        if start_id <= p['id'] <= end_id:
            p['potential_delete'] = True
            p['delete_reason'] = 'range_select'
            count += 1

    # Verify
    assert count == 6, f"Expected 6, got {count}"
    assert paragraphs[4]['potential_delete'] == True, "Para 5 should be marked"
    assert paragraphs[9]['potential_delete'] == True, "Para 10 should be marked"
    assert paragraphs[3]['potential_delete'] == False, "Para 4 should NOT be marked"
    assert paragraphs[10]['potential_delete'] == False, "Para 11 should NOT be marked"

    print("✅ Range selection logic test PASSED")

if __name__ == "__main__":
    test_range_selection()
