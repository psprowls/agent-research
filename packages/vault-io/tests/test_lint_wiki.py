"""Tests for vault_io.lint_wiki.

Verifies importability and structural correctness of scan().
Finding-count parity with the upstream lint_wiki module is out of
Phase 14 scope (VP-02 rubric) — this file only asserts structural correctness.
"""

from __future__ import annotations

from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"


def test_lint_wiki_importable() -> None:
    """vault_io.lint_wiki exports main and scan as callables."""
    from vault_io.lint_wiki import main, scan  # noqa: F401

    assert callable(main)
    assert callable(scan)


def test_lint_wiki_scan_runs_on_fixture_vault(tmp_path: Path) -> None:
    """scan(wiki, stale_days, log_gap_days) returns a structurally well-formed dict.

    A minimal wiki directory is constructed under tmp_path so that scan() has
    a valid wiki.exists() and a clean workspace to walk. The test asserts the
    top-level keys expected on the return value — no finding-count assertions.
    """
    from vault_io.lint_wiki import scan

    # Create a minimal workspace/wiki layout.
    # scan() treats wiki.parent as the workspace and rglobs *.md under it.
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()

    # Seed one page with full frontmatter so scan() has something to process.
    (wiki / "index.md").write_text(
        "---\ntitle: Index\ncategory: meta\nsummary: root index\n---\n\nWelcome.\n",
        encoding="utf-8",
    )
    page = wiki / "concepts"
    page.mkdir()
    (page / "example.md").write_text(
        "---\ntitle: Example\ncategory: concept\nsummary: an example page\ntokens: 100\n---\n\nBody.\n",
        encoding="utf-8",
    )

    result = scan(wiki, stale_days=90, log_gap_days=14)

    # Structural assertions — top-level keys must be present.
    expected_keys = {
        "wiki",
        "total_pages",
        "orphans",
        "broken_links",
        "stale",
        "missing_frontmatter",
        "missing_tokens",
        "duplicate_titles",
        "log_gap",
        "code_drift",
        "container_drift",
        "source_sync_drift",
        "file_map_drift",
        "package_sync_drift",
        "domain_placement",
        "dependency_layer",
        "workflow_hints",
    }
    assert expected_keys.issubset(result.keys()), (
        f"scan() result missing keys: {expected_keys - result.keys()}"
    )

    # Basic type assertions.
    assert isinstance(result["wiki"], str)
    assert isinstance(result["total_pages"], int)
    assert isinstance(result["orphans"], list)
    assert isinstance(result["broken_links"], list)
    assert isinstance(result["stale"], list)
    assert isinstance(result["missing_frontmatter"], list)
    assert isinstance(result["missing_tokens"], list)
    assert isinstance(result["duplicate_titles"], dict)


def _legit_page() -> str:
    """Frontmatter for a fully valid wiki page (no lint findings)."""
    return (
        "---\n"
        "title: Foo\n"
        "category: concept\n"
        "summary: a legit page\n"
        "tokens: 100\n"
        "updated: 2099-01-01\n"
        "---\n\n"
        "Body.\n"
    )


def test_schema_files_excluded_from_page_enumeration(tmp_path: Path) -> None:
    """CLAUDE.md and AGENTS.md at the wiki root are schema files, not pages —
    lint must not flag them for missing_frontmatter or missing_tokens, and they
    must not contribute to total_pages."""
    from vault_io.lint_wiki import scan

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()

    # Schema files (no frontmatter, plain content).
    (wiki / "CLAUDE.md").write_text("# Project schema\n\nsome notes\n", encoding="utf-8")
    (wiki / "AGENTS.md").write_text("# Agents schema\n\n", encoding="utf-8")

    # One legit page.
    (wiki / "foo.md").write_text(_legit_page(), encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)

    # Neither schema file should appear in lint findings.
    assert "wiki/CLAUDE" not in result["missing_frontmatter"]
    assert "wiki/AGENTS" not in result["missing_frontmatter"]
    assert "wiki/CLAUDE" not in result["missing_tokens"]
    assert "wiki/AGENTS" not in result["missing_tokens"]
    # And not in orphans either.
    assert "wiki/CLAUDE" not in result["orphans"]
    assert "wiki/AGENTS" not in result["orphans"]


def test_schema_files_excluded_at_any_depth(tmp_path: Path) -> None:
    """Forward-compatible: CLAUDE.md and AGENTS.md nested under packages/ etc.
    are also excluded."""
    from vault_io.lint_wiki import scan

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()
    pkg_dir = wiki / "packages" / "foo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "CLAUDE.md").write_text("nested schema\n", encoding="utf-8")
    (pkg_dir / "AGENTS.md").write_text("nested schema\n", encoding="utf-8")
    (wiki / "foo.md").write_text(_legit_page(), encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)

    for finding_list in ("missing_frontmatter", "missing_tokens", "orphans"):
        for key in result[finding_list]:
            assert "CLAUDE" not in key, f"{finding_list} unexpectedly contains schema file: {key}"
            assert "AGENTS" not in key, f"{finding_list} unexpectedly contains schema file: {key}"


def test_total_pages_excludes_schema_files(tmp_path: Path) -> None:
    """total_pages reflects content pages only, not schema files."""
    from vault_io.lint_wiki import scan

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()

    (wiki / "CLAUDE.md").write_text("schema\n", encoding="utf-8")
    (wiki / "AGENTS.md").write_text("schema\n", encoding="utf-8")
    (wiki / "foo.md").write_text(_legit_page(), encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)

    # Only 'foo.md' is a real page.
    assert result["total_pages"] == 1
