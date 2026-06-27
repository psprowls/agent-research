"""guidance_io.writer.write_page mechanical scaffolding tests."""

from __future__ import annotations

from pathlib import Path

from guidance_io.frontmatter import parse
from guidance_io.writer import WriteResult, write_page

_PAGE = """---
title: Pin The Model Role
category: guidance
summary: Use make_llm(role).
topic: model-adapter
applies_when: calling Bedrock
impact: high
updated: 1999-01-01
tokens: 30
---

## Guidance
Use make_llm.

## Applies to
All model calls.
"""


def test_write_page_writes_and_stamps(tmp_path: Path) -> None:
    res = write_page(
        tmp_path, topic_raw="Model Adapter", slug_raw="Pin The Model Role", page_text=_PAGE, stamp="2026-06-15"
    )
    assert isinstance(res, WriteResult)
    assert res.skip_reason is None
    assert res.written_rel == "wiki/guidance/model-adapter/pin-the-model-role.md"
    written = (tmp_path / res.written_rel).read_text(encoding="utf-8")
    fm, _ = parse(written)
    assert fm["updated"] == "2026-06-15"


def test_write_page_skips_invalid(tmp_path: Path) -> None:
    bad = "---\ntitle: X\ncategory: concept\n---\n\nbody\n"
    res = write_page(tmp_path, topic_raw="model-adapter", slug_raw="bad", page_text=bad, stamp="2026-06-15")
    assert res.written_rel is None
    assert res.skip_reason and "category" in res.skip_reason
    assert not (tmp_path / "wiki" / "guidance" / "model-adapter" / "bad.md").exists()


def test_write_page_skips_unparseable(tmp_path: Path) -> None:
    res = write_page(
        tmp_path, topic_raw="model-adapter", slug_raw="x", page_text="not frontmatter\n", stamp="2026-06-15"
    )
    assert res.written_rel is None
    assert res.skip_reason


def test_write_page_strips_trailing_whitespace(tmp_path: Path) -> None:
    # Synthesizer output with trailing whitespace/newlines must not leak into the
    # written file — matches the pre-refactor page_text.strip() behavior.
    res = write_page(
        tmp_path, topic_raw="model-adapter", slug_raw="trailer", page_text=_PAGE + "\n\n   \n", stamp="2026-06-15"
    )
    assert res.skip_reason is None
    written = (tmp_path / res.written_rel).read_text(encoding="utf-8")
    assert written == written.rstrip()  # no trailing whitespace in the file


def test_write_page_language_suffix_and_stamp(tmp_path: Path) -> None:
    res = write_page(
        tmp_path,
        topic_raw="code-review",
        slug_raw="language-specific-checks",
        page_text=_PAGE,
        stamp="2026-06-26",
        language="python",
    )
    assert res.written_rel == "wiki/guidance/code-review/language-specific-checks-python.md"
    fm, _ = parse((tmp_path / res.written_rel).read_text(encoding="utf-8"))
    assert fm["language"] == "python"


def test_write_page_agnostic_no_suffix(tmp_path: Path) -> None:
    res = write_page(
        tmp_path,
        topic_raw="code-review",
        slug_raw="language-specific-checks",
        page_text=_PAGE,
        stamp="2026-06-26",
    )
    assert res.written_rel == "wiki/guidance/code-review/language-specific-checks.md"
    fm, _ = parse((tmp_path / res.written_rel).read_text(encoding="utf-8"))
    assert "language" not in fm


def test_write_page_normalizes_language(tmp_path: Path) -> None:
    res = write_page(
        tmp_path,
        topic_raw="code-review",
        slug_raw="checks",
        page_text=_PAGE,
        stamp="2026-06-26",
        language="  Python  ",
    )
    assert res.written_rel == "wiki/guidance/code-review/checks-python.md"
    fm, _ = parse((tmp_path / res.written_rel).read_text(encoding="utf-8"))
    assert fm["language"] == "python"
