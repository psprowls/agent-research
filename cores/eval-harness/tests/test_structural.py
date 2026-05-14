from __future__ import annotations

"""Unit tests for eval_harness.structural.

All tests are deterministic and require no Bedrock access.
Uses fixture_vault_path from conftest.py (round-trip-vault fixture).
"""

from pathlib import Path

import pytest

from code_wiki_agent.commands.query import QueryResult
from eval_harness.structural import check_structural

# The 7 keys that check_structural must always return.
EXPECTED_KEYS = {
    "has_citation",
    "citations_resolve",
    "unresolved_citations",
    "pages_drilled_positive",
    "has_code_path",
    "frontmatter_valid",
    "json_schema_valid",
}


def test_fixture_vault_has_pages(fixture_vault_path: Path) -> None:
    """Fixture vault must contain more than 3 markdown pages."""
    pages = list(fixture_vault_path.rglob("*.md"))
    assert len(pages) > 3


def test_known_good(fixture_vault_path: Path) -> None:
    """A well-formed QueryResult with a valid citation resolves cleanly."""
    result = QueryResult(
        answer="See [[packages/lattice-wiki-core]].",
        citations=["packages/lattice-wiki-core"],
        pages_drilled=3,
        search_scores={},
    )
    report = check_structural(result, fixture_vault_path)
    assert report["citations_resolve"] is True
    assert report["has_citation"] is True
    assert report["pages_drilled_positive"] is True


def test_no_citation(fixture_vault_path: Path) -> None:
    """QueryResult with no citations has has_citation=False."""
    result = QueryResult(
        answer="no links",
        citations=[],
        pages_drilled=1,
        search_scores={},
    )
    report = check_structural(result, fixture_vault_path)
    assert report["has_citation"] is False


def test_unresolved_citation(fixture_vault_path: Path) -> None:
    """A citation pointing to a nonexistent page has citations_resolve=False."""
    result = QueryResult(
        answer="[[nonexistent/page]]",
        citations=["nonexistent/page"],
        pages_drilled=1,
        search_scores={},
    )
    report = check_structural(result, fixture_vault_path)
    assert report["citations_resolve"] is False
    assert "nonexistent/page" in report["unresolved_citations"]


def test_all_keys_present(fixture_vault_path: Path) -> None:
    """check_structural always returns a dict with all 7 required keys."""
    result = QueryResult(
        answer="Some answer with src/main.py reference.",
        citations=[],
        pages_drilled=2,
        search_scores={},
    )
    report = check_structural(result, fixture_vault_path)
    assert set(report.keys()) >= EXPECTED_KEYS


def test_has_code_path_detected(fixture_vault_path: Path) -> None:
    """has_code_path is True when answer contains a .py path reference."""
    result = QueryResult(
        answer="See cores/eval-harness/src/eval_harness/pricing.py for details.",
        citations=[],
        pages_drilled=1,
        search_scores={},
    )
    report = check_structural(result, fixture_vault_path)
    assert report["has_code_path"] is True


def test_no_code_path(fixture_vault_path: Path) -> None:
    """has_code_path is False when answer has no path-like strings."""
    result = QueryResult(
        answer="The system works by processing requests in order.",
        citations=[],
        pages_drilled=1,
        search_scores={},
    )
    report = check_structural(result, fixture_vault_path)
    assert report["has_code_path"] is False


def test_json_schema_valid(fixture_vault_path: Path) -> None:
    """json_schema_valid is True for a properly typed QueryResult."""
    result = QueryResult(
        answer="Valid answer",
        citations=["packages/lattice-wiki-core"],
        pages_drilled=2,
        search_scores={"page": 0.9},
    )
    report = check_structural(result, fixture_vault_path)
    assert report["json_schema_valid"] is True


def test_invalid_result_type(fixture_vault_path: Path) -> None:
    """check_structural raises TypeError when result is not a QueryResult (T-4-01)."""
    with pytest.raises(TypeError):
        check_structural({"answer": "bad"}, fixture_vault_path)  # type: ignore[arg-type]
