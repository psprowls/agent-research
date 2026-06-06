"""Living Wiki M2d §3.4 / D4: flag entity pages missing an expected
scanner-owned section for their kind (renamed/dropped heading)."""

from __future__ import annotations

from wiki_io.lint.scanner_heading import check

# A well-formed package page carries all three scanner sections.
_OK_PACKAGE = {
    "fm": {"kind": "package"},
    "text": (
        "---\nuri: pkg:org/repo/foo\nkind: package\n---\n# foo\n\n"
        "## Narrative\nprose\n\n## Referenced in wiki\n- x\n\n"
        "## File map - foo\n| a | b | c |\n"
    ),
}

# A package page whose ## Narrative was renamed -> the heading is missing.
_RENAMED_NARRATIVE = {
    "fm": {"kind": "package"},
    "text": (
        "---\nuri: pkg:org/repo/bar\nkind: package\n---\n# bar\n\n"
        "## Narrative (old)\nprose\n\n## Referenced in wiki\n- x\n\n"
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


def test_well_formed_pages_produce_no_findings() -> None:
    pages = {"wiki/entities/foo": _OK_PACKAGE, "wiki/entities/boto3": _OK_DEPENDENCY}
    assert check(pages) == []


def test_renamed_narrative_is_flagged() -> None:
    pages = {"wiki/entities/bar": _RENAMED_NARRATIVE}
    issues = check(pages)
    assert len(issues) == 1
    assert "wiki/entities/bar" in issues[0]
    assert "## Narrative" in issues[0]


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
    """An `app` page (a file-map kind) with all three scanner sections is clean."""
    page = {
        "fm": {"kind": "app"},
        "text": (
            "---\nkind: app\n---\n# svc\n\n## Narrative\nprose\n\n"
            "## Referenced in wiki\n- x\n\n## File map - svc\n| a | b | c |\n"
        ),
    }
    assert check({"wiki/entities/svc": page}) == []


def test_missing_narrative_on_app_is_flagged() -> None:
    """An `app` page missing `## Narrative` is flagged."""
    page = {
        "fm": {"kind": "app"},
        "text": ("---\nkind: app\n---\n# svc\n\n## Referenced in wiki\n- x\n\n## File map - svc\n| a | b | c |\n"),
    }
    issues = check({"wiki/entities/svc": page})
    assert any("## Narrative" in i for i in issues)
