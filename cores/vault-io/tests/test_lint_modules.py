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
