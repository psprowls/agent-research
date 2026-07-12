"""Tests for work_io.lifecycle_lint.load_items — the shared work-item loader.

Moved from graph_wiki_core.commands.work._load_items so both lint surfaces
(gw lint and the plugin's lint_wiki.py scan()) load items identically.
"""

from __future__ import annotations

from work_io.lifecycle_lint import load_items

PAGE = """---
title: Some item
status: open
kind: bug
---

## Summary
body
"""


def _write(path, text=PAGE):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_missing_dir_returns_empty(tmp_path):
    assert load_items(tmp_path / "work") == []


def test_flat_live_dir_slug_from_stem(tmp_path):
    work = tmp_path / "work"
    _write(work / "2026-01-01-fix-thing.md")
    items = load_items(work)
    assert [it["slug"] for it in items] == ["2026-01-01-fix-thing"]
    assert items[0]["fm"]["status"] == "open"
    assert items[0]["plan"] is not None


def test_archive_nested_slug_from_parent_dir(tmp_path):
    archive = tmp_path / "work" / "_archive"
    _write(archive / "2026-01-02-nested-item" / "00-open-work.md")
    items = load_items(archive)
    assert [it["slug"] for it in items] == ["2026-01-02-nested-item"]


def test_archive_legacy_flat_slug_from_stem(tmp_path):
    archive = tmp_path / "work" / "_archive"
    _write(archive / "2026-01-03-legacy-item.md")
    items = load_items(archive)
    assert [it["slug"] for it in items] == ["2026-01-03-legacy-item"]


def test_archive_both_shapes_coexist(tmp_path):
    archive = tmp_path / "work" / "_archive"
    _write(archive / "2026-01-02-nested-item" / "00-open-work.md")
    _write(archive / "2026-01-03-legacy-item.md")
    slugs = {it["slug"] for it in load_items(archive)}
    assert slugs == {"2026-01-02-nested-item", "2026-01-03-legacy-item"}


def test_unparseable_page_skipped(tmp_path):
    work = tmp_path / "work"
    _write(work / "good.md")
    _write(work / "bad.md", "no frontmatter here\n")
    assert [it["slug"] for it in load_items(work)] == ["good"]


def test_flat_live_dir_skips_generated_index(tmp_path):
    work = tmp_path / "work"
    _write(work / "2026-01-01-fix-thing.md")
    _write(work / "index.md", "---\ntitle: Work Index\ncategory: index\n---\n")
    items = load_items(work)
    assert [it["slug"] for it in items] == ["2026-01-01-fix-thing"]
