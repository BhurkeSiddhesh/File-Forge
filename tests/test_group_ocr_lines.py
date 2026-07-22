"""Regression tests for _group_ocr_lines' column-awareness and left-margin
overlap fixes.

Background: the OCR fallback path (used when RapidOCR has no layout
recovery, e.g. on ARM deployments) used to group OCR text fragments into
lines purely by vertical-center proximity, with no notion of columns or
left-margin/indentation. On a multi-column resume this merged text from
different columns into one line, and could merge a new bullet's left-margin
start into a still-open previous line just because their y-centers were
close - both contributing to bullets losing their opening words.
"""
from scripts.pdf_utils import _group_ocr_lines, _split_into_columns


def _entry(text, x0, x1, y0, y1):
    return {"text": text, "bbox": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


def test_group_ocr_lines_keeps_two_columns_separate():
    """Two fragments at the same y but in different columns (wide x gap)
    must stay on separate lines when page_width is known."""
    items = [
        _entry("Skills:", 10, 80, 100, 120),
        _entry("Experience:", 400, 500, 100, 120),
    ]

    # Without page_width (old behavior), everything is one column and these
    # get merged into a single nonsensical line.
    assert _group_ocr_lines(items) == ["Skills: Experience:"]

    # With page_width, the wide gap is recognized as a column boundary.
    result = _group_ocr_lines(items, page_width=600)
    assert result == ["Skills:", "Experience:"]


def test_group_ocr_lines_no_column_gap_stays_single_column():
    """Fragments with no significant x gap are treated as one column/line,
    same as before."""
    items = [
        _entry("Hello", 10, 60, 100, 120),
        _entry("world", 65, 110, 100, 120),
    ]
    assert _group_ocr_lines(items, page_width=600) == ["Hello world"]


def test_group_ocr_lines_left_margin_bullet_not_merged_into_previous_line():
    """A new bullet starting back at the left margin, whose y-center happens
    to fall within tolerance of an still-open previous line, must not be
    absorbed into it - overlapping x-ranges can't be the same visual row."""
    items = [
        _entry("First bullet continuation text on the right", 150, 400, 100, 118),
        _entry("New bullet starts here", 20, 140, 108, 126),
    ]
    result = _group_ocr_lines(items, page_width=600)
    assert result == [
        "First bullet continuation text on the right",
        "New bullet starts here",
    ]


def test_group_ocr_lines_same_row_left_to_right_words_still_join():
    """Ordinary same-row, non-overlapping, left-to-right words are still
    joined into a single line (baseline behavior preserved)."""
    items = [
        _entry("The", 10, 40, 100, 120),
        _entry("quick", 45, 90, 100, 120),
        _entry("fox", 95, 120, 100, 120),
    ]
    assert _group_ocr_lines(items, page_width=600) == ["The quick fox"]


def test_split_into_columns_falls_back_to_one_column_without_page_width():
    items = [_entry("a", 0, 10, 0, 10), _entry("b", 500, 510, 0, 10)]
    assert _split_into_columns(items, None) == [items]
    assert _split_into_columns(items, 0) == [items]
