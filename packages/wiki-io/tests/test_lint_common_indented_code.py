"""Phase 46 Plan 01: indented_code_spans helper for the link rewriter."""
from wiki_io.lint.common import indented_code_spans


def test_indented_code_spans_empty_input():
    assert indented_code_spans("") == []


def test_indented_code_spans_no_blocks():
    text = "Just some prose.\n\nWith blank lines.\n"
    assert indented_code_spans(text) == []


def test_indented_code_spans_single_4space_block():
    text = "Prose.\n\n    code line 1\n    code line 2\n\nMore prose.\n"
    spans = indented_code_spans(text)
    assert len(spans) == 1
    s, e = spans[0]
    # Span covers exactly the two code lines.
    assert text[s:e] == "    code line 1\n    code line 2\n"


def test_indented_code_spans_single_tab_block():
    text = "Prose.\n\n\tcode\n\nMore.\n"
    spans = indented_code_spans(text)
    assert len(spans) == 1
    s, e = spans[0]
    assert text[s:e] == "\tcode\n"


def test_indented_code_spans_requires_preceding_blank_line():
    # No blank line before "    code" → NOT an indented code block (it's a continuation
    # of the prose paragraph per CommonMark §4.4).
    text = "Prose.\n    code\n"
    spans = indented_code_spans(text)
    assert spans == []


def test_indented_code_spans_block_at_document_start():
    # Document starts with an indented line → IS an indented code block.
    text = "    code line\nfollowing prose\n"
    spans = indented_code_spans(text)
    assert len(spans) == 1
    s, e = spans[0]
    assert text[s:e] == "    code line\n"


def test_indented_code_spans_multiple_blocks():
    text = (
        "Prose A.\n\n"
        "    block 1 line 1\n"
        "    block 1 line 2\n\n"
        "Prose B.\n\n"
        "    block 2\n"
    )
    spans = indented_code_spans(text)
    assert len(spans) == 2
    # Both spans cover their respective indented runs.
    assert text[spans[0][0]:spans[0][1]] == "    block 1 line 1\n    block 1 line 2\n"
    assert text[spans[1][0]:spans[1][1]] == "    block 2\n"


def test_indented_code_spans_sorted_non_overlapping():
    text = (
        "Prose.\n\n"
        "    A\n\n"
        "Mid.\n\n"
        "    B\n"
    )
    spans = indented_code_spans(text)
    assert spans == sorted(spans)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2  # non-overlapping
