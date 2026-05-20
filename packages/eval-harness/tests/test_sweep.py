"""Unit tests for eval_harness.sweep: SweepResult dataclass and run_sweep().

Integration test (test_run_query_accepts_tmpdir_vault) requires GRAPH_WIKI_RUN_EVAL=1
and is marked "integration" — skipped in the normal unit suite.

All other tests use AsyncMock to avoid Bedrock calls and are fully deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from graph_wiki_agent.commands.query import QueryResult
from eval_harness.sweep import SweepResult, run_sweep

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
                "tags": ["test"],
            }
        ]
    cases_path = tmp_path / "query_cases.json"
    cases_path.write_text(json.dumps(cases))
    return cases_path


# ---------------------------------------------------------------------------
# Integration smoke test (skipped in unit suite)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_run_query_accepts_tmpdir_vault(
    fixture_vault_path: Path,
) -> None:
    """Assumption A1 validation: run_query() accepts a tmpdir vault_path.

    This test calls run_query() directly with vault_path set to a fresh
    EvalWorktree copy of fixture_vault_path. If resolve_wiki_and_repo or
    any internal function rejects the tmpdir path, the failure is surfaced
    here before the sweep loop trusts it (RESEARCH.md Pitfall 6).

    Requires: GRAPH_WIKI_RUN_EVAL=1 (integration marker), real Bedrock credentials.
    """
    from graph_wiki_agent.commands.query import run_query
    from eval_harness.isolation import EvalWorktree

    async with EvalWorktree(fixture_vault_path) as wt:
        result = await run_query(
            "What does lattice-wiki-core do?",
            vault_path=wt.path,
            top_k=3,
        )
    assert isinstance(result, QueryResult)


# ---------------------------------------------------------------------------
# Unit tests (mocked run_query — no Bedrock calls)
# ---------------------------------------------------------------------------


async def test_sweep_collects_results(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_sweep with 2 model_ids and 1 case returns a list of 2 SweepResult."""
    cases_path = _make_cases_file(tmp_path)
    model_ids = ["us.amazon.nova-lite-v1:0", "us.amazon.nova-micro-v1:0"]

    mock_result = _make_query_result()
    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=mock_result)):
        results = await run_sweep(cases_path, fixture_vault_path, model_ids)

    assert len(results) == 2
    assert all(isinstance(r, SweepResult) for r in results)


async def test_sweep_partial_failure(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_sweep with 2 model_ids where one raises returns 1 ok + 1 error result."""
    cases_path = _make_cases_file(tmp_path)
    model_ids = ["us.amazon.nova-lite-v1:0", "us.amazon.nova-micro-v1:0"]

    mock_result = _make_query_result()

    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated Bedrock error")
        return mock_result

    with patch("eval_harness.sweep.run_query", new=AsyncMock(side_effect=_side_effect)):
        results = await run_sweep(cases_path, fixture_vault_path, model_ids)

    assert len(results) == 2
    statuses = {r.status for r in results}
    assert "ok" in statuses
    assert "error" in statuses


async def test_sweep_includes_structural(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Each SweepResult.structural contains the 'has_citation' key."""
    cases_path = _make_cases_file(tmp_path)
    model_ids = ["us.amazon.nova-lite-v1:0"]

    mock_result = _make_query_result()
    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=mock_result)):
        results = await run_sweep(cases_path, fixture_vault_path, model_ids)

    assert len(results) == 1
    assert "has_citation" in results[0].structural


async def test_sweep_sanitizes_model_id(tmp_path: Path, fixture_vault_path: Path) -> None:
    """SweepResult for 'us.amazon.nova-pro-v1:0' has safe_model_id with colon replaced."""
    cases_path = _make_cases_file(tmp_path)
    model_ids = ["us.amazon.nova-pro-v1:0"]

    mock_result = _make_query_result()
    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=mock_result)):
        results = await run_sweep(cases_path, fixture_vault_path, model_ids)

    assert len(results) == 1
    assert results[0].safe_model_id == "us.amazon.nova-pro-v1_0"


async def test_sweep_loads_cases(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_sweep reads cases from cases_path JSON and validates schema (T-4-01)."""
    # Valid case plus invalid cases missing required fields — invalid should be skipped
    cases = [
        {"case_id": "valid-01", "query": "What?", "expected_answer": "something"},
        {"case_id": "invalid-01", "query": "Missing answer field"},  # no expected_answer
        {"case_id": "invalid-02", "expected_answer": "no query field"},  # no query
    ]
    cases_path = _make_cases_file(tmp_path, cases)
    model_ids = ["us.amazon.nova-lite-v1:0"]

    mock_result = _make_query_result()
    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=mock_result)):
        results = await run_sweep(cases_path, fixture_vault_path, model_ids)

    # Only the valid case should produce a SweepResult (2 invalid cases skipped)
    assert len(results) == 1
    assert results[0].query == "What?"


async def test_sweep_records_wall_seconds(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Each SweepResult.wall_seconds is greater than 0.0."""
    cases_path = _make_cases_file(tmp_path)
    model_ids = ["us.amazon.nova-lite-v1:0"]

    mock_result = _make_query_result()
    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=mock_result)):
        results = await run_sweep(cases_path, fixture_vault_path, model_ids)

    assert len(results) == 1
    assert results[0].wall_seconds > 0.0


async def test_sweep_result_has_seed(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Each SweepResult has a seed field; seed is None for non-deterministic runs."""
    cases_path = _make_cases_file(tmp_path)
    model_ids = ["us.amazon.nova-lite-v1:0"]

    mock_result = _make_query_result()
    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=mock_result)):
        results = await run_sweep(cases_path, fixture_vault_path, model_ids)

    assert len(results) == 1
    result = results[0]
    # Field must exist and must be None (librarian is non-deterministic)
    assert hasattr(result, "seed")
    assert result.seed is None
