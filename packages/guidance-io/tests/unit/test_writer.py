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
