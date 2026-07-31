"""Unit tests for the structured frontmatter setter (wiki_io.entity_writer)
and the M4 content-hash primitives (wiki_io.content_hash)."""

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
            "content_hash": "9f2c",
            "custom_list": ["a", "b"],
        },
    )
    meta = _fm.load(page).metadata
    assert meta["content_hash"] == "9f2c"
    assert meta["custom_list"] == ["a", "b"]


def test_update_frontmatter_deletes_key(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\ncontent_hash: old\n")
    update_frontmatter(page, {"content_hash": "new"}, delete=["content_hash"])
    meta = _fm.load(page).metadata
    assert "content_hash" not in meta


def test_update_frontmatter_preserves_body_and_other_keys(tmp_path):
    page = _write(tmp_path, "uri: pkg:a\nkind: package\nsummary: keep me\n")
    update_frontmatter(page, {"content_hash": "x"})
    post = _fm.load(page)
    assert post.metadata["summary"] == "keep me"
    assert post.metadata["uri"] == "pkg:a"
    assert "## Purpose" in post.content


def test_update_frontmatter_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        update_frontmatter(tmp_path / "nope.md", {"x": "y"})


# ---------------------------------------------------------------------------
# M4 content-hash primitives (wiki_io.content_hash)
# ---------------------------------------------------------------------------

from wiki_io.content_hash import page_body_hash, section_hash  # noqa: E402


def test_section_hash_is_stable_and_edit_sensitive():
    chunk = "## Purpose\nProcesses items synchronously.\n"
    assert section_hash(chunk) == section_hash(chunk + "\n\n")  # trailing ws ignored
    assert section_hash(chunk) != section_hash("## Purpose\nProcesses items async.\n")


def test_page_body_hash_is_stable_and_edit_sensitive():
    body = "# T\n\n## Definition\nA thing.\n"
    assert page_body_hash(body) == page_body_hash(body + "\n\n")  # trailing ws ignored
    assert page_body_hash(body) != page_body_hash("# T\n\n## Definition\nA different thing.\n")


def test_page_body_hash_matches_section_hash_over_whole_body():
    body = "# T\n\n## Definition\nA thing.\n"
    assert page_body_hash(body) == section_hash(body)
