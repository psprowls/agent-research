"""Tests for the 7 ported lint mechanical modules.

Verifies: importability, GROUP constants, and that check() returns a list
when invoked against fixture vaults. Finding-count parity with lattice-wiki-core
is a plan-05-06 concern — this file only asserts structural correctness.

Requirements: CMD-05
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vault_io.lint import (
    container,
    dependency,
    domain,
    file_map,
    package_sync,
    source_sync,
    workflow_hints,
)

FIXTURES = Path(__file__).parent / "fixtures"
EDGE_CASE_VAULT = FIXTURES / "edge-case-vault"
ROUND_TRIP_VAULT = FIXTURES / "round-trip-vault"

EXPECTED_GROUPS = {
    "container",
    "dependency_layer",
    "domain",
    "file_map",
    "package_sync",
    "source_sync",
    "workflow_hints",
}

ALL_MODULES = [container, dependency, domain, file_map, package_sync, source_sync, workflow_hints]


def _load_pages(wiki: Path) -> dict:
    """Build a minimal pages dict from a vault fixture directory.

    Each page entry: {"fm": dict, "text": str}
    """
    from vault_io.lint.common import parse_frontmatter

    pages: dict = {}
    for md in sorted(wiki.rglob("*.md")):
        rel = md.relative_to(wiki)
        key = str(rel).replace("\\", "/")
        if key.endswith(".md"):
            key = key[:-3]
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        pages[key] = {"fm": fm, "text": text}
    return pages


# ---------------------------------------------------------------------------
# Structural tests
# ---------------------------------------------------------------------------


def test_all_modules_importable() -> None:
    """All 7 lint modules can be imported without error."""
    for mod in ALL_MODULES:
        assert mod is not None
        assert hasattr(mod, "check"), f"{mod.__name__} missing check()"
        assert hasattr(mod, "GROUP"), f"{mod.__name__} missing GROUP"


def test_GROUP_constants_unique_and_expected() -> None:
    """All 7 GROUP constants are the expected strings and are all distinct."""
    actual_groups = {mod.GROUP for mod in ALL_MODULES}
    assert actual_groups == EXPECTED_GROUPS, (
        f"GROUP mismatch.\nExpected: {EXPECTED_GROUPS}\nGot: {actual_groups}"
    )


# ---------------------------------------------------------------------------
# Per-module smoke tests: check() returns a list against fixture vault
# ---------------------------------------------------------------------------


def test_container_check_returns_list() -> None:
    """container.check(repo, wiki) returns a list."""
    # Use edge-case-vault as both repo and wiki — fixture has CLAUDE.md
    result = container.check(EDGE_CASE_VAULT, EDGE_CASE_VAULT)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_dependency_check_returns_list() -> None:
    """dependency.check(pages) returns a list."""
    pages = _load_pages(EDGE_CASE_VAULT)
    result = dependency.check(pages)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_domain_check_returns_list() -> None:
    """domain.check(pages) returns a list."""
    pages = _load_pages(EDGE_CASE_VAULT)
    result = domain.check(pages)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_file_map_check_returns_list() -> None:
    """file_map.check(repo, pages) returns a list."""
    pages = _load_pages(EDGE_CASE_VAULT)
    result = file_map.check(EDGE_CASE_VAULT, pages)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_package_sync_check_returns_list() -> None:
    """package_sync.check(repo, wiki) returns a list."""
    result = package_sync.check(EDGE_CASE_VAULT, EDGE_CASE_VAULT)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_source_sync_check_returns_list() -> None:
    """source_sync.check(repo, wiki) returns a list."""
    result = source_sync.check(EDGE_CASE_VAULT, EDGE_CASE_VAULT)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_workflow_hints_check_returns_list() -> None:
    """workflow_hints.check(pages, vault) returns a list."""
    pages = _load_pages(EDGE_CASE_VAULT)
    result = workflow_hints.check(pages, EDGE_CASE_VAULT)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


# ---------------------------------------------------------------------------
# Bonus: round-trip vault smoke (richer pages — catches signature drift)
# ---------------------------------------------------------------------------


def test_dependency_check_against_round_trip_vault() -> None:
    """dependency.check(pages) returns a list against the richer round-trip vault."""
    pages = _load_pages(ROUND_TRIP_VAULT)
    result = dependency.check(pages)
    assert isinstance(result, list)


def test_domain_check_against_round_trip_vault() -> None:
    """domain.check(pages) returns a list against the richer round-trip vault."""
    pages = _load_pages(ROUND_TRIP_VAULT)
    result = domain.check(pages)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# parse_section_entries() tests — new table-based parser
# ---------------------------------------------------------------------------


class TestParseSectionEntries:
    """Tests for parse_section_entries() — table-format parser with graceful fallback."""

    def _parse(self, body: str, pkg_name: str = "mypkg") -> list[tuple[str, bool]]:
        from vault_io.lint.common import parse_section_entries

        return parse_section_entries(body, pkg_name)

    def test_new_format_one_h3_two_rows(self) -> None:
        """New-format body with one H3 section and 2 rows returns expected tuples."""
        body = """\
### mypkg/src/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `index.ts` | file | — TODO |
| `utils.ts` | file | — TODO |
"""
        result = self._parse(body)
        # H3 header produces dir entry for "src"
        assert ("src", True) in result
        assert ("src/index.ts", False) in result
        assert ("src/utils.ts", False) in result

    def test_root_section_produces_tuples_without_prefix(self) -> None:
        """Root section ### mypkg/ produces tuples without any sub-dir prefix."""
        body = """\
### mypkg/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `package.json` | file | — TODO |
"""
        result = self._parse(body)
        assert ("package.json", False) in result
        # No dir entry for root itself (empty current_path)
        dirs = [p for p, is_d in result if is_d]
        assert dirs == []

    def test_nested_path_row_inside_depth1_section(self) -> None:
        """A nested-path row middleware/auth.ts inside ### mypkg/src/ yields src/middleware/auth.ts."""
        body = """\
### mypkg/src/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `middleware/auth.ts` | file | — TODO |
"""
        result = self._parse(body)
        assert ("src/middleware/auth.ts", False) in result

    def test_dir_row_inside_depth1_section(self) -> None:
        """A dir row inside depth-1 section yields a directory entry; H3 also yields dir entry."""
        body = """\
### mypkg/src/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `clients/` | dir | — TODO |
"""
        result = self._parse(body)
        # H3 itself produces ("src", True)
        assert ("src", True) in result
        # dir row produces ("src/clients", True) — trailing slash stripped
        assert ("src/clients", True) in result

    def test_old_format_returns_empty_list_gracefully(self) -> None:
        """Old heading+bullet format returns empty list without raising."""
        body = """\
### mypkg/src/
One-paragraph description.

- `index.ts` — TODO
- `utils.ts` — TODO

### mypkg/tests/
Tests.

- `spec.ts` — TODO
"""
        result = self._parse(body)
        # Should not crash; returns directory entries from H3 headers only (no file rows)
        assert isinstance(result, list)
        # File rows are absent (no tables found)
        files = [(p, d) for p, d in result if not d]
        assert files == []

    def test_malformed_table_missing_separator_no_crash(self) -> None:
        """Missing separator row — no row-level entries, no crash."""
        body = """\
### mypkg/src/
TODO.

| Path | Kind | Description |
| `index.ts` | file | — TODO |
"""
        result = self._parse(body)
        # Should not crash
        assert isinstance(result, list)
        # Dir entry from H3 header still produced
        assert ("src", True) in result

    def test_brace_expansion_in_path_tokens(self) -> None:
        """Brace-expanded path token yields two file entries."""
        body = """\
### mypkg/src/
TODO.

| Path | Kind | Description |
|---|---|---|
| `{a,b}.ts` | file | — TODO |
"""
        result = self._parse(body)
        assert ("src/a.ts", False) in result
        assert ("src/b.ts", False) in result

    def test_pipe_in_description_does_not_break_parser(self) -> None:
        """Escaped pipe in Description cell does not break table parsing."""
        body = """\
### mypkg/src/
TODO.

| Path | Kind | Description |
|---|---|---|
| `index.ts` | file | — TODO \\| with pipe |
"""
        result = self._parse(body)
        assert ("src/index.ts", False) in result
