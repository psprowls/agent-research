"""Phase 46 Plan 01: tests for wiki_io.link_rewriter.rewrite_text.

Covers CONTEXT D-02 edge cases: fenced/inline/indented code exclusion,
alias/anchor preservation, idempotency, table-cell escape, lazy continuation,
nested-fence known limitation, unresolvable / unknown target handling.
"""
import pytest

from wiki_io.link_rewriter import rewrite_text


TABLE_BASIC = {
    "packages/foo/index": "entities/pkg__org__foo",
    "packages/bar/index": "entities/pkg__org__bar",
    "domain/billing/index": "entities/domain__org__billing",
}


# --- Basic rewrites ---

def test_rewrite_text_basic_single():
    text = "See [[packages/foo/index]] for details.\n"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == "See [[entities/pkg__org__foo]] for details.\n"
    assert n == 1


def test_rewrite_text_basic_multiple():
    text = "See [[packages/foo/index]] and [[packages/bar/index]].\n"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == "See [[entities/pkg__org__foo]] and [[entities/pkg__org__bar]].\n"
    assert n == 2


def test_rewrite_text_returns_count_equals_rewrites():
    text = (
        "[[packages/foo/index]] [[packages/bar/index]] "
        "[[packages/unknown/index]] [[domain/billing/index]]\n"
    )
    out, n = rewrite_text(text, TABLE_BASIC)
    assert n == 3  # unknown one skipped


# --- Alias / anchor preservation ---

def test_rewrite_text_alias_preserved():
    text = "[[packages/foo/index|graph-io]]"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == "[[entities/pkg__org__foo|graph-io]]"
    assert n == 1


def test_rewrite_text_anchor_preserved():
    text = "[[packages/foo/index#api]]"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == "[[entities/pkg__org__foo#api]]"
    assert n == 1


def test_rewrite_text_alias_and_anchor_preserved():
    text = "[[packages/foo/index#api|graph-io API]]"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == "[[entities/pkg__org__foo#api|graph-io API]]"
    assert n == 1


def test_rewrite_text_escaped_table_cell_alias_preserved():
    # The escaped \| form is used inside markdown table cells.
    text = "| col1 | [[packages/foo/index\\|graph-io]] |"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == "| col1 | [[entities/pkg__org__foo\\|graph-io]] |"
    assert n == 1


# --- Code region skipping (MIGRATION-04) ---

def test_rewrite_text_skips_fenced_code():
    text = (
        "Prose with [[packages/foo/index]].\n\n"
        "```\n"
        "[[packages/foo/index]]\n"
        "```\n\n"
        "More prose with [[packages/bar/index]].\n"
    )
    out, n = rewrite_text(text, TABLE_BASIC)
    expected = (
        "Prose with [[entities/pkg__org__foo]].\n\n"
        "```\n"
        "[[packages/foo/index]]\n"
        "```\n\n"
        "More prose with [[entities/pkg__org__bar]].\n"
    )
    assert out == expected
    assert n == 2  # both prose rewrites; fenced one skipped


def test_rewrite_text_skips_inline_code():
    text = "Prose with `[[packages/foo/index]]` inline and [[packages/foo/index]] outside.\n"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert "`[[packages/foo/index]]`" in out  # inline byte-identical
    assert "[[entities/pkg__org__foo]] outside" in out  # outside rewritten
    assert n == 1


def test_rewrite_text_skips_indented_code():
    text = (
        "Prose.\n\n"
        "    [[packages/foo/index]]\n\n"
        "More prose with [[packages/foo/index]].\n"
    )
    out, n = rewrite_text(text, TABLE_BASIC)
    # Indented block bytes preserved
    assert "    [[packages/foo/index]]" in out
    # Prose rewrite applied
    assert "More prose with [[entities/pkg__org__foo]]." in out
    assert n == 1


def test_rewrite_text_lazy_continuation_rewrites():
    # No blank line between fence close and next text → paragraph continuation;
    # the wikilink IS rewritten.
    text = "```\nint x = 0;\n```\n[[packages/foo/index]]\n"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert "```\nint x = 0;\n```\n[[entities/pkg__org__foo]]" in out
    assert n == 1


# --- Unresolvable / unknown target handling ---

def test_rewrite_text_unresolvable_target_skipped():
    table = {**TABLE_BASIC, "packages/unresolved/index": None}
    text = "Has [[packages/unresolved/index]] and [[packages/foo/index]].\n"
    out, n = rewrite_text(text, table)
    assert "[[packages/unresolved/index]]" in out  # unresolved preserved
    assert "[[entities/pkg__org__foo]]" in out  # known one rewritten
    assert n == 1


def test_rewrite_text_unknown_target_skipped():
    text = "Has [[packages/never-heard-of/index]] alone.\n"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == text  # byte-identical
    assert n == 0


# --- Idempotency ---

def test_rewrite_text_idempotent():
    text = "See [[packages/foo/index]] and [[packages/bar/index]].\n"
    out1, n1 = rewrite_text(text, TABLE_BASIC)
    out2, n2 = rewrite_text(out1, TABLE_BASIC)
    assert out2 == out1  # second pass is a no-op
    assert n2 == 0
    assert n1 == 2


# --- Nested fences (CONTEXT D-02 known limitation) ---

@pytest.mark.xfail(
    reason=(
        "Nested fences are a v1.8 known limitation per CONTEXT D-02 — regex "
        "FENCED_CODE_RE is non-greedy and may misdetect inner fences. "
        "Documented; not solved."
    ),
    strict=False,
)
def test_rewrite_text_nested_fence_known_limitation():
    text = (
        "````\n"
        "Inside outer fence.\n"
        "```\n"
        "[[packages/foo/index]]\n"
        "```\n"
        "Still inside outer.\n"
        "````\n"
    )
    out, _ = rewrite_text(text, TABLE_BASIC)
    # If the regex correctly treats the entire outer-fenced region as code,
    # the wikilink is preserved. If it incorrectly closes the outer fence at
    # the inner ``` it may rewrite — that's the known limitation. We assert
    # the desired (correct) behavior; xfail accommodates the actual v1.8 behavior.
    assert out == text


# --- Empty / trivial inputs ---

def test_rewrite_text_empty_input():
    out, n = rewrite_text("", TABLE_BASIC)
    assert out == ""
    assert n == 0


def test_rewrite_text_no_wikilinks():
    text = "Just prose with no wikilinks at all.\n"
    out, n = rewrite_text(text, TABLE_BASIC)
    assert out == text
    assert n == 0


def test_rewrite_text_empty_table():
    text = "Has [[packages/foo/index]] but table is empty.\n"
    out, n = rewrite_text(text, {})
    assert out == text
    assert n == 0
