"""Unit tests for work_io.filing — ported from the former wiki-io ingest module.

Covers slugify / parse_fields / validate / write_work_item. The
update_index/append_log side-effect assertions intentionally do NOT live here
— those effects moved to graph-wiki-core (see test_commands_ingest.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_basic() -> None:
    from work_io.filing import slugify

    assert slugify("Fix the bug!") == "fix-the-bug"


def test_slugify_untitled_on_empty() -> None:
    from work_io.filing import slugify

    assert slugify("") == "untitled"


def test_slugify_preserves_alphanum() -> None:
    from work_io.filing import slugify

    assert slugify("add-oauth2-login") == "add-oauth2-login"


def test_slugify_lowercases() -> None:
    from work_io.filing import slugify

    result = slugify("Resolve The Bug")
    assert result == result.lower()


def test_slugify_handles_unicode() -> None:
    from work_io.filing import slugify

    result = slugify("Résoudre le bug")
    assert result == result.lower()


# ---------------------------------------------------------------------------
# compose_slug
# ---------------------------------------------------------------------------


def test_compose_slug_basic() -> None:
    from work_io.filing import compose_slug

    slug, warnings = compose_slug("feature", "shorten work item slugs")
    assert slug == "feature-shorten-work-item-slugs"
    assert warnings == []


def test_compose_slug_epic_child_prefix() -> None:
    from work_io.filing import compose_slug

    slug, warnings = compose_slug("bug", "fix flaky retry", epic_child=True)
    assert slug == "epic-bug-fix-flaky-retry"
    assert warnings == []


def test_compose_slug_warns_on_five_or_six_words() -> None:
    from work_io.filing import compose_slug

    slug, warnings = compose_slug("feature", "one two three four five")
    assert slug == "feature-one-two-three-four-five"
    assert len(warnings) == 1
    assert "5 words" in warnings[0]

    slug6, warnings6 = compose_slug("feature", "one two three four five six")
    assert slug6 == "feature-one-two-three-four-five-six"
    assert len(warnings6) == 1
    assert "6 words" in warnings6[0]


def test_compose_slug_truncates_seven_plus_words() -> None:
    from work_io.filing import compose_slug

    slug, warnings = compose_slug("feature", "one two three four five six seven eight")
    assert slug == "feature-one-two-three-four-five-six"
    assert len(warnings) == 1
    assert "truncated" in warnings[0]


def test_compose_slug_empty_words_degrades_to_untitled() -> None:
    from work_io.filing import compose_slug

    slug, warnings = compose_slug("feature", "   ")
    assert slug == "feature-untitled"
    assert warnings == []


def test_compose_slug_non_alphanumeric_words() -> None:
    from work_io.filing import compose_slug

    slug, warnings = compose_slug("bug", "OAuth2 login!! failing @ prod")
    assert slug == "bug-oauth2-login-failing-prod"
    assert warnings == []


# ---------------------------------------------------------------------------
# parse_fields
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


def test_parse_fields_scalar_fields() -> None:
    from work_io.filing import parse_fields

    fm = parse_fields(VALID_FM_YAML)
    assert fm["title"] == "Fix auth bug"
    assert fm["category"] == "work"
    assert fm["status"] == "open"
    # safe_load coerces an ISO date scalar to a datetime.date; compare as str.
    assert str(fm["opened"]) == "2026-05-14"


def test_parse_fields_list_field() -> None:
    from work_io.filing import parse_fields

    fm = parse_fields(VALID_FM_YAML)
    assert isinstance(fm["affects"], list)
    assert "backend" in fm["affects"]
    assert "frontend" in fm["affects"]


def test_parse_fields_empty_list() -> None:
    from work_io.filing import parse_fields

    fm = parse_fields("affects: []")
    assert fm["affects"] == []


def test_parse_fields_handles_at_handle_flow_list() -> None:
    """Regression: the old hand-rolled line parser stored the literal string
    '["@psprowls"]' for this value (it only special-cased '[]'). Full YAML
    yields a real one-element list. '@' is a reserved YAML indicator, so the
    value must be quoted in the source — parse_fields must honor that."""
    from work_io.filing import parse_fields

    fm = parse_fields('deciders: ["@psprowls"]')
    assert fm["deciders"] == ["@psprowls"]


def test_parse_fields_rejects_non_mapping() -> None:
    from work_io.filing import parse_fields

    with pytest.raises(ValueError):
        parse_fields("just a bare string")


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_returns_empty_for_valid_fm() -> None:
    from work_io.filing import parse_fields, validate

    fm = parse_fields(VALID_FM_YAML)
    assert validate(fm) == []


def test_validate_catches_missing_required_fields() -> None:
    from work_io.filing import validate

    issues = validate({})
    required = {"title", "category", "kind", "status", "summary", "opened", "affects"}
    missing = {i.split("missing required field: ")[1] for i in issues if "missing required field" in i}
    assert required == missing


def test_validate_catches_wrong_category() -> None:
    from work_io.filing import parse_fields, validate

    fm = parse_fields(VALID_FM_YAML)
    fm["category"] = "package"
    assert any("category" in i for i in validate(fm))


# ---------------------------------------------------------------------------
# emit round-trip (now via work_io.frontmatter)
# ---------------------------------------------------------------------------


def test_emit_roundtrips_through_frontmatter() -> None:
    from work_io import frontmatter
    from work_io.filing import parse_fields

    fm = parse_fields(VALID_FM_YAML)
    emitted = frontmatter.emit(fm)
    assert emitted.startswith("---")
    assert emitted.rstrip().endswith("---")
    fm2, _body = frontmatter.parse(emitted + "\n\nbody\n")
    assert fm2["title"] == fm["title"]
    assert fm2["affects"] == fm["affects"]


# ---------------------------------------------------------------------------
# write_work_item
# ---------------------------------------------------------------------------


def _make_wiki(tmp_path: Path) -> Path:
    """Return <tmp>/workspace/wiki so work_dir(wiki.parent) -> .../wiki/work."""
    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    return wiki


def test_write_work_item_creates_page(tmp_path: Path) -> None:
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    result = write_work_item(wiki, fm, "## Details\n\nSome body text.\n")

    assert result["status"] == "ok"
    page_path = Path(result["page_path"])
    assert page_path.exists()
    assert page_path == wiki / "work" / "2026-05-14-bug-fix-auth-bug.md"
    content = page_path.read_text(encoding="utf-8")
    assert "Fix auth bug" in content
    assert "Some body text" in content


def test_write_work_item_slug_from_title(tmp_path: Path) -> None:
    """VALID_FM_YAML carries kind: bug, so the default slug gets the kind prefix."""
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    result = write_work_item(wiki, fm, "Body.\n")
    assert result["slug"] == "2026-05-14-bug-fix-auth-bug"


def test_write_work_item_default_slug_epic_child_prefix(tmp_path: Path) -> None:
    """epic_child is caller-supplied, not inferred from fm['parent']."""
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    fm["kind"] = "feature"
    fm["parent"] = "2026-01-01-epic-something"
    result = write_work_item(wiki, fm, "Body.\n", epic_child=True)
    assert result["slug"] == "2026-05-14-epic-feature-fix-auth-bug"


def test_write_work_item_parent_without_epic_child_keeps_plain_prefix(tmp_path: Path) -> None:
    """A feature parent (or any non-epic parent) must NOT be inferred as epic_child."""
    from work_io.filing import write_work_item

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    fm = {
        "title": "Fix flaky retry logic",
        "kind": "bug",
        "opened": "2026-07-24",
        "parent": "2026-07-01-feature-parent",
    }
    result = write_work_item(wiki, fm, "body\n", epic_child=False)
    assert "epic-bug" not in result["slug"]
    assert "-bug-" in result["slug"]


def test_write_work_item_explicit_epic_child_prefix(tmp_path: Path) -> None:
    from work_io.filing import write_work_item

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    fm = {"title": "Fix flaky retry logic", "kind": "bug", "opened": "2026-07-24", "parent": "2026-07-01-epic-x"}
    result = write_work_item(wiki, fm, "body\n", epic_child=True)
    assert "epic-bug-" in result["slug"]


def test_write_work_item_default_slug_truncates_title_to_four_words(tmp_path: Path) -> None:
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    fm["title"] = "Shorten work item slugs to date kind and four words"
    fm["kind"] = "feature"
    result = write_work_item(wiki, fm, "Body.\n")
    assert result["slug"] == "2026-05-14-feature-shorten-work-item-slugs"


def test_write_work_item_default_slug_falls_back_to_legacy_when_kind_missing(tmp_path: Path) -> None:
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    del fm["kind"]
    result = write_work_item(wiki, fm, "Body.\n")
    assert result["slug"] == "2026-05-14-fix-auth-bug"


def test_write_work_item_respects_explicit_slug(tmp_path: Path) -> None:
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    result = write_work_item(wiki, fm, "Body.\n", slug="custom-slug")
    assert result["slug"] == "2026-05-14-custom-slug"
    assert "custom-slug" in result["page_path"]


def test_write_work_item_refuses_overwrite_without_force(tmp_path: Path) -> None:
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    write_work_item(wiki, fm, "Body.\n", slug="my-slug")
    with pytest.raises(FileExistsError):
        write_work_item(wiki, fm, "Body.\n", slug="my-slug", force=False)


def test_write_work_item_force_overwrites(tmp_path: Path) -> None:
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    write_work_item(wiki, fm, "Body.\n", slug="my-slug")
    result = write_work_item(wiki, fm, "Body.\n", slug="my-slug", force=True)
    assert result["status"] == "ok"


def test_write_work_item_appends_trailing_newline(tmp_path: Path) -> None:
    from work_io.filing import parse_fields, write_work_item

    wiki = _make_wiki(tmp_path)
    fm = parse_fields(VALID_FM_YAML)
    result = write_work_item(wiki, fm, "Body without trailing newline", slug="nl")
    content = Path(result["page_path"]).read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert content.endswith("Body without trailing newline\n")


def test_filing_module_has_no_wiki_io_import() -> None:
    """work-io must not gain a wiki-io dependency."""
    import importlib.util

    spec = importlib.util.find_spec("work_io.filing")
    assert spec is not None and spec.origin is not None
    text = Path(spec.origin).read_text(encoding="utf-8")
    assert "wiki_io" not in text
    assert "_emit_yaml" not in text
