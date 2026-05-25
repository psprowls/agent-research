from __future__ import annotations

"""Tests for wiki_io.ingest_work_item — ported from lattice-wiki-core.

Requirements: CMD-03 (ingest_work_item port from lattice-wiki-core)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


def test_slugify_basic() -> None:
    from wiki_io.ingest_work_item import _slugify

    assert _slugify("Fix the bug!") == "fix-the-bug"


def test_slugify_untitled_on_empty() -> None:
    from wiki_io.ingest_work_item import _slugify

    assert _slugify("") == "untitled"


def test_slugify_preserves_alphanum() -> None:
    from wiki_io.ingest_work_item import _slugify

    assert _slugify("add-oauth2-login") == "add-oauth2-login"


def test_slugify_handles_unicode() -> None:
    from wiki_io.ingest_work_item import _slugify

    result = _slugify("Résoudre le bug")
    assert result == result.lower()


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------

VALID_FM_YAML = """title: Fix auth bug
category: work
kind: bug
status: open
summary: Resolve the login failure for SSO users
opened: 2026-05-14
affects:
  - backend
  - frontend"""


def test_parse_frontmatter_scalar_fields() -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter

    fm = _parse_frontmatter(VALID_FM_YAML)
    assert fm["title"] == "Fix auth bug"
    assert fm["category"] == "work"
    assert fm["status"] == "open"
    assert fm["opened"] == "2026-05-14"


def test_parse_frontmatter_list_field() -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter

    fm = _parse_frontmatter(VALID_FM_YAML)
    assert isinstance(fm["affects"], list)
    assert "backend" in fm["affects"]
    assert "frontend" in fm["affects"]


def test_parse_frontmatter_empty_list() -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter

    fm = _parse_frontmatter("affects: []")
    assert fm["affects"] == []


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------


def test_validate_returns_empty_for_valid_fm() -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, _validate

    fm = _parse_frontmatter(VALID_FM_YAML)
    issues = _validate(fm)
    assert issues == []


def test_validate_catches_missing_required_fields() -> None:
    from wiki_io.ingest_work_item import _validate

    # Empty dict → all required fields missing
    issues = _validate({})
    required = {"title", "category", "kind", "status", "summary", "opened", "affects"}
    missing_fields = {i.split("missing required field: ")[1] for i in issues if "missing required field" in i}
    assert required == missing_fields


def test_validate_catches_wrong_category() -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, _validate

    fm = _parse_frontmatter(VALID_FM_YAML)
    fm["category"] = "package"
    issues = _validate(fm)
    assert any("category" in i for i in issues)


# ---------------------------------------------------------------------------
# _emit_yaml
# ---------------------------------------------------------------------------


def test_emit_yaml_roundtrip() -> None:
    from wiki_io.ingest_work_item import _emit_yaml, _parse_frontmatter

    fm = _parse_frontmatter(VALID_FM_YAML)
    emitted = _emit_yaml(fm)
    assert emitted.startswith("---")
    assert emitted.endswith("---")
    # Round-trip: parse the emitted YAML again
    fm2 = _parse_frontmatter(emitted.strip("---\n"))
    assert fm2["title"] == fm["title"]
    assert fm2["affects"] == fm["affects"]


def test_emit_yaml_contains_all_fields() -> None:
    from wiki_io.ingest_work_item import _emit_yaml, _parse_frontmatter

    fm = _parse_frontmatter(VALID_FM_YAML)
    emitted = _emit_yaml(fm)
    for field in ("title", "category", "kind", "status", "summary", "opened", "affects"):
        assert field in emitted


# ---------------------------------------------------------------------------
# file_work_item
# ---------------------------------------------------------------------------


def _make_wiki(tmp_path: Path) -> Path:
    """Create a minimal wiki directory with log.md."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "index.md").write_text("", encoding="utf-8")
    return wiki


def test_file_work_item_creates_page(tmp_path: Path) -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, file_work_item

    wiki = _make_wiki(tmp_path)
    fm = _parse_frontmatter(VALID_FM_YAML)
    body = "## Details\n\nSome body text.\n"

    with (
        patch("wiki_io.ingest_work_item.update_index") as mock_ui,
        patch("wiki_io.ingest_work_item.append_log") as mock_al,
    ):
        result = file_work_item(wiki, fm, body)

    assert result["status"] == "ok"
    page_path = Path(result["page_path"])
    assert page_path.exists()
    content = page_path.read_text(encoding="utf-8")
    assert "Fix auth bug" in content
    assert "Some body text" in content


def test_file_work_item_calls_update_index_and_append_log(tmp_path: Path) -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, file_work_item

    wiki = _make_wiki(tmp_path)
    fm = _parse_frontmatter(VALID_FM_YAML)
    body = "Body text.\n"

    with (
        patch("wiki_io.ingest_work_item.update_index") as mock_ui,
        patch("wiki_io.ingest_work_item.append_log") as mock_al,
    ):
        result = file_work_item(wiki, fm, body)

    # update_index must be called with (wiki,)
    mock_ui.assert_called_once_with(wiki)
    # append_log must be called with (wiki, "create", title, detail=...)
    mock_al.assert_called_once()
    call_args = mock_al.call_args
    assert call_args.args[0] == wiki
    assert call_args.args[1] == "create"
    assert call_args.args[2] == fm["title"]
    assert "work/" in call_args.kwargs.get("detail", "")


def test_file_work_item_slug_from_title(tmp_path: Path) -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, file_work_item

    wiki = _make_wiki(tmp_path)
    fm = _parse_frontmatter(VALID_FM_YAML)
    body = "Body.\n"

    with (
        patch("wiki_io.ingest_work_item.update_index"),
        patch("wiki_io.ingest_work_item.append_log"),
    ):
        result = file_work_item(wiki, fm, body)

    assert result["slug"] == "fix-auth-bug"


def test_file_work_item_respects_explicit_slug(tmp_path: Path) -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, file_work_item

    wiki = _make_wiki(tmp_path)
    fm = _parse_frontmatter(VALID_FM_YAML)
    body = "Body.\n"

    with (
        patch("wiki_io.ingest_work_item.update_index"),
        patch("wiki_io.ingest_work_item.append_log"),
    ):
        result = file_work_item(wiki, fm, body, slug="custom-slug")

    assert result["slug"] == "custom-slug"
    assert "custom-slug" in result["page_path"]


def test_file_work_item_refuses_overwrite_without_force(tmp_path: Path) -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, file_work_item

    wiki = _make_wiki(tmp_path)
    fm = _parse_frontmatter(VALID_FM_YAML)
    body = "Body.\n"

    with (
        patch("wiki_io.ingest_work_item.update_index"),
        patch("wiki_io.ingest_work_item.append_log"),
    ):
        # First write succeeds
        file_work_item(wiki, fm, body, slug="my-slug")
        # Second write should raise
        with pytest.raises((FileExistsError, SystemExit, ValueError, RuntimeError)):
            file_work_item(wiki, fm, body, slug="my-slug", force=False)


def test_file_work_item_force_overwrites(tmp_path: Path) -> None:
    from wiki_io.ingest_work_item import _parse_frontmatter, file_work_item

    wiki = _make_wiki(tmp_path)
    fm = _parse_frontmatter(VALID_FM_YAML)
    body = "Body.\n"

    with (
        patch("wiki_io.ingest_work_item.update_index"),
        patch("wiki_io.ingest_work_item.append_log"),
    ):
        file_work_item(wiki, fm, body, slug="my-slug")
        result = file_work_item(wiki, fm, body, slug="my-slug", force=True)

    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# No subprocess / lattice_wiki_core references
# ---------------------------------------------------------------------------


def test_no_subprocess_or_lattice_imports() -> None:
    import importlib.util

    spec = importlib.util.find_spec("wiki_io.ingest_work_item")
    assert spec is not None
    src_path = Path(spec.origin)
    text = src_path.read_text(encoding="utf-8")
    assert "import subprocess" not in text
    assert "_run_helper" not in text
    assert "lattice_wiki_core" not in text
