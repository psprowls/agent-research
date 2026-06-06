"""Unit tests for set_frontmatter_value (Living Wiki M2a)."""

from __future__ import annotations

from pathlib import Path

import frontmatter
from wiki_io.entity_writer import LAST_UPDATED_COMMIT_KEY, set_frontmatter_value


def _write(p: Path, text: str) -> None:
    p.write_text(text, encoding="utf-8")


def test_appends_new_key_last_preserving_body(tmp_path: Path) -> None:
    page = tmp_path / "e.md"
    _write(page, "---\ntitle: A\nuri: pkg:a\n---\n# A\n\n## Narrative\nprose here\n")
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "abc123")
    post = frontmatter.load(page)
    assert post.metadata[LAST_UPDATED_COMMIT_KEY] == "abc123"
    assert post.metadata["title"] == "A"  # existing keys preserved
    assert "## Narrative\nprose here" in post.content  # body preserved
    assert list(post.metadata.keys())[-1] == LAST_UPDATED_COMMIT_KEY  # appended last


def test_updates_existing_key_in_place(tmp_path: Path) -> None:
    page = tmp_path / "e.md"
    _write(
        page,
        "---\nuri: pkg:a\nlast_updated_commit: old\ntitle: A\n---\n# A\n",
    )
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "new")
    post = frontmatter.load(page)
    assert post.metadata[LAST_UPDATED_COMMIT_KEY] == "new"
    keys = list(post.metadata.keys())
    assert keys.index("last_updated_commit") < keys.index("title")  # position kept


def test_resetting_same_value_is_byte_stable(tmp_path: Path) -> None:
    page = tmp_path / "e.md"
    _write(page, "---\nuri: pkg:a\n---\n# A\n\n## Purpose\nkept\n")
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "abc123")
    first = page.read_text(encoding="utf-8")
    set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, "abc123")
    assert page.read_text(encoding="utf-8") == first


def test_missing_file_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        set_frontmatter_value(tmp_path / "nonexistent.md", "x", "y")
