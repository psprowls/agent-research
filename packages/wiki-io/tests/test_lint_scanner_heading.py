"""Deterministic-heading lint: flag entity pages missing an expected
deterministic section for their kind (renamed/dropped heading)."""

from __future__ import annotations

from wiki_io.lint.scanner_heading import check

# A well-formed package page carries both deterministic sections.
_OK_PACKAGE = {
    "fm": {"kind": "package"},
    "text": (
        "---\nuri: pkg:org/repo/foo\nkind: package\n---\n# foo\n\n"
        "## Narrative\nprose\n\n## Referenced in wiki\n- x\n\n"
        "## File map - foo\n| a | b | c |\n"
    ),
}

# A package page whose ## Referenced in wiki was renamed -> the heading is missing.
_RENAMED_REFERENCED_IN_WIKI = {
    "fm": {"kind": "package"},
    "text": (
        "---\nuri: pkg:org/repo/bar\nkind: package\n---\n# bar\n\n"
        "## Narrative\nprose\n\n## Referenced in wiki (old)\n- x\n\n"
        "## File map - bar\n| a | b | c |\n"
    ),
}

# A dependency page (no File map expected) that is well-formed.
_OK_DEPENDENCY = {
    "fm": {"kind": "dependency"},
    "text": (
        "---\nuri: dependency:pypi/boto3\nkind: dependency\n---\n# boto3\n\n"
        "## Narrative\nprose\n\n## Referenced in wiki\n- x\n"
    ),
}

# A non-entity page (no entity `kind`) must be ignored entirely.
_NON_ENTITY = {"fm": {"category": "concept"}, "text": "# c\n\n## Whatever\n"}

_AGENT_PLUGIN_TABLES = (
    "## Commands",
    "## Agents",
    "## Skills",
    "## Scripts",
    "## Hooks",
    "## MCP servers",
)


def _agent_plugin_text(*, drop: str | None = None) -> str:
    lines = ["---\nkind: agent_plugin\n---\n# plug\n\n## Referenced in wiki\n- x\n"]
    for heading in _AGENT_PLUGIN_TABLES:
        if heading == drop:
            continue
        lines.append(f"\n{heading}\n| a | b |\n")
    return "".join(lines)


def test_well_formed_pages_produce_no_findings() -> None:
    pages = {"wiki/entities/foo": _OK_PACKAGE, "wiki/entities/boto3": _OK_DEPENDENCY}
    assert check(pages) == []


def test_renamed_narrative_is_no_longer_flagged() -> None:
    """`## Narrative` is prose now, not deterministic — a rename/drop isn't a lint finding."""
    page = {
        "fm": {"kind": "package"},
        "text": (
            "---\nkind: package\n---\n# foo\n\n## Narrative (old)\nprose\n\n"
            "## Referenced in wiki\n- x\n\n## File map - foo\n| a | b | c |\n"
        ),
    }
    assert check({"wiki/entities/foo": page}) == []


def test_renamed_referenced_in_wiki_is_flagged() -> None:
    issues = check({"wiki/entities/bar": _RENAMED_REFERENCED_IN_WIKI})
    assert len(issues) == 1
    assert "wiki/entities/bar" in issues[0]
    assert "## Referenced in wiki" in issues[0]


def test_missing_file_map_on_package_is_flagged() -> None:
    page = {
        "fm": {"kind": "package"},
        "text": ("---\nkind: package\n---\n# foo\n\n## Narrative\np\n\n## Referenced in wiki\n- x\n"),
    }
    issues = check({"wiki/entities/foo": page})
    assert any("## File map" in i for i in issues)


def test_non_entity_pages_are_ignored() -> None:
    assert check({"concepts/c": _NON_ENTITY}) == []


def test_well_formed_app_page_produces_no_findings() -> None:
    """An `app` page (a file-map kind) with both deterministic sections is clean."""
    page = {
        "fm": {"kind": "app"},
        "text": (
            "---\nkind: app\n---\n# svc\n\n## Narrative\nprose\n\n"
            "## Referenced in wiki\n- x\n\n## File map - svc\n| a | b | c |\n"
        ),
    }
    assert check({"wiki/entities/svc": page}) == []


def test_missing_narrative_on_app_is_not_flagged() -> None:
    """Narrative dropping out of the expected set applies to every kind, not just package."""
    page = {
        "fm": {"kind": "app"},
        "text": ("---\nkind: app\n---\n# svc\n\n## Referenced in wiki\n- x\n\n## File map - svc\n| a | b | c |\n"),
    }
    assert check({"wiki/entities/svc": page}) == []


def test_well_formed_agent_plugin_page_produces_no_findings() -> None:
    page = {"fm": {"kind": "agent_plugin"}, "text": _agent_plugin_text()}
    assert check({"wiki/entities/plug": page}) == []


def test_missing_agent_plugin_data_table_is_flagged() -> None:
    page = {"fm": {"kind": "agent_plugin"}, "text": _agent_plugin_text(drop="## Skills")}
    issues = check({"wiki/entities/plug": page})
    assert any("## Skills" in i for i in issues)
