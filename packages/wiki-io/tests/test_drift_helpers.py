"""Living Wiki M2e: unit tests for the structured frontmatter setter and the
pure drift helpers (wiki_io.drift)."""

from __future__ import annotations

import frontmatter as _fm
import pytest
from wiki_io.entity_writer import update_frontmatter


def _write(tmp_path, fm: str, body: str = "# T\n\n## Purpose\nx\n"):
    p = tmp_path / "page.md"
    p.write_text(f"---\n{fm}---\n{body}", encoding="utf-8")
    return p


def test_update_frontmatter_sets_structured_value(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\n")
    update_frontmatter(
        page,
        {
            "drift_checked_commit": "abc123",
            "drift_review": [
                {"section": "Purpose", "detected_commit": "abc123",
                 "hash": "9f2c", "reason": "stale"}
            ],
        },
    )
    meta = _fm.load(page).metadata
    assert meta["drift_checked_commit"] == "abc123"
    assert meta["drift_review"] == [
        {"section": "Purpose", "detected_commit": "abc123",
         "hash": "9f2c", "reason": "stale"}
    ]


def test_update_frontmatter_deletes_key(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\ndrift_review:\n- {section: Purpose}\n")
    update_frontmatter(page, {"drift_checked_commit": "x"}, delete=["drift_review"])
    meta = _fm.load(page).metadata
    assert "drift_review" not in meta
    assert meta["drift_checked_commit"] == "x"


def test_update_frontmatter_preserves_body_and_other_keys(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\nsummary: keep me\n")
    update_frontmatter(page, {"drift_checked_commit": "x"})
    post = _fm.load(page)
    assert post.metadata["summary"] == "keep me"
    assert post.metadata["uri"] == "pkg:a"
    assert "## Purpose" in post.content


def test_update_frontmatter_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        update_frontmatter(tmp_path / "nope.md", {"x": "y"})
