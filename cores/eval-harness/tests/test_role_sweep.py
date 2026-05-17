"""Unit tests for run_role_sweep() and estimate_sweep_cost().

Covers: single-role-swap protocol (SWEEP-01), dispatch map,
sweep_candidates TOML read, and pre-flight cost estimator (D-13).

Requirements: SWEEP-01, D-13.

All tests use AsyncMock/patch to avoid Bedrock calls. Module-level
pytest.skip guards are in place until Plan 07-05 lands the production code.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from code_wiki_agent.commands.query import QueryResult

pytestmark = pytest.mark.skip(reason="Pending Plan 07-05")

# ---------------------------------------------------------------------------
# Helper: minimal QueryResult for mocking
# ---------------------------------------------------------------------------


def _make_query_result(answer: str = "test answer [[wiki-page]]") -> QueryResult:
    return QueryResult(
        answer=answer,
        citations=["wiki-page"],
        pages_drilled=2,
        search_scores={"page.md": {"bm25": 0.5, "embed": 0.4, "rrf": 0.9}},
    )


def _make_cases_file(tmp_path: Path, cases: list[dict] | None = None) -> Path:
    """Write a query_cases.json file to tmp_path and return its path."""
    if cases is None:
        cases = [
            {
                "case_id": "test-01",
                "query": "What does this do?",
                "expected_answer": "it does something",
                "tags": [],
            }
        ]
    cases_path = tmp_path / "query_cases.json"
    cases_path.write_text(json.dumps(cases))
    return cases_path


# ---------------------------------------------------------------------------
# Dispatch map tests (SWEEP-01)
# ---------------------------------------------------------------------------


async def test_role_sweep_calls_dispatch_map(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_role_sweep uses ROLE_COMMAND_MAP to route each role to the correct command."""
    assert False, "TODO Plan 07-05"


async def test_single_role_swap_librarian(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Sweeping librarian role passes role_model_overrides={"librarian": candidate}
    to run_query; all other roles use defaults."""
    assert False, "TODO Plan 07-05"


async def test_single_role_swap_scanner(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Sweeping scanner role calls run_scan with model_override=candidate."""
    assert False, "TODO Plan 07-05"


async def test_sweep_candidates_read_from_models_toml(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_role_sweep reads sweep_candidates from models.toml via load_role_config."""
    assert False, "TODO Plan 07-05"
