"""Unit tests for run_role_sweep() and the dispatch map.

Covers: single-role-swap protocol (SWEEP-01), dispatch map,
sweep_candidates TOML read, and ROLE_COMMAND_MAP routing.

Requirements: SWEEP-01, D-06.

All tests use AsyncMock/patch to avoid Bedrock calls. Module-level
pytest.skip guards are in place until Plan 07-05 lands the production code.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from graph_wiki_agent.commands.ingest import IngestResult
from graph_wiki_agent.commands.lint import LintResult
from graph_wiki_agent.commands.query import QueryResult
from graph_wiki_agent.commands.scan import ScanResult
from eval_harness.sweep import ROLE_COMMAND_MAP, SweepResult, run_role_sweep


# ---------------------------------------------------------------------------
# Helper: minimal result factories for mocking
# ---------------------------------------------------------------------------


def _make_query_result(answer: str = "test answer [[wiki-page]]") -> QueryResult:
    return QueryResult(
        answer=answer,
        citations=["wiki-page"],
        pages_drilled=2,
        search_scores={"page.md": {"bm25": 0.5, "embed": 0.4, "rrf": 0.9}},
    )


def _make_scan_result() -> ScanResult:
    return ScanResult(
        added=["pkg-a"],
        updated=[],
        deleted=[],
        renamed=[],
        errors=[],
        state_gate={"allowed": True},
    )


def _make_lint_result() -> LintResult:
    return LintResult(
        wiki="test-wiki",
        total_pages=2,
        orphans=[],
        errors=[],
    )


def _make_ingest_result() -> IngestResult:
    return IngestResult(
        status="ok",
        page_path="packages/test.md",
        slug="test",
        title="Test",
        page_type="package",
        source_path="src/test.py",
        cross_refs_updated=0,
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


def test_role_command_map_covers_all_roles() -> None:
    """ROLE_COMMAND_MAP has an entry for each of the 6 agent roles."""
    expected_roles = {"librarian", "synthesizer", "code_reader", "scanner", "linter", "ingestor"}
    assert expected_roles == set(ROLE_COMMAND_MAP.keys())


def test_role_command_map_query_roles() -> None:
    """librarian, synthesizer, and code_reader all map to _sweep_query_role."""
    for role in ("librarian", "synthesizer", "code_reader"):
        assert ROLE_COMMAND_MAP[role] == "_sweep_query_role", (
            f"{role} should map to _sweep_query_role"
        )


def test_role_command_map_non_query_roles() -> None:
    """scanner/linter/ingestor each map to their own command function."""
    assert ROLE_COMMAND_MAP["scanner"] == "_sweep_scan_role"
    assert ROLE_COMMAND_MAP["linter"] == "_sweep_lint_role"
    assert ROLE_COMMAND_MAP["ingestor"] == "_sweep_ingest_role"


async def test_role_sweep_calls_dispatch_map(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_role_sweep uses ROLE_COMMAND_MAP to route each role to the correct command."""
    cases_path = _make_cases_file(tmp_path)

    # Test scanner routes to run_scan
    mock_scan = AsyncMock(return_value=_make_scan_result())
    with patch("eval_harness.sweep.run_scan", new=mock_scan):
        results = await run_role_sweep(
            "scanner",
            "us.amazon.nova-lite-v1:0",
            cases_path,
            fixture_vault_path,
            repeats=1,
        )

    assert mock_scan.called, "run_scan should have been called for scanner role"
    assert len(results) == 1
    assert results[0].model_id == "us.amazon.nova-lite-v1:0"


async def test_single_role_swap_librarian(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Sweeping librarian role passes role_model_overrides={"librarian": candidate}
    to run_query; all other roles use defaults."""
    cases_path = _make_cases_file(tmp_path)
    captured_kwargs: dict = {}

    async def _mock_run_query(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return _make_query_result()

    with patch("eval_harness.sweep.run_query", new=AsyncMock(side_effect=_mock_run_query)):
        results = await run_role_sweep(
            "librarian",
            "us.amazon.nova-pro-v1:0",
            cases_path,
            fixture_vault_path,
            repeats=1,
        )

    assert len(results) == 1
    overrides = captured_kwargs.get("role_model_overrides", {})
    assert overrides.get("librarian") == "us.amazon.nova-pro-v1:0", (
        "librarian override must match the candidate model_id"
    )
    # Other roles must NOT be in overrides (single-role-swap D-06)
    assert "synthesizer" not in overrides
    assert "scanner" not in overrides


async def test_single_role_swap_scanner(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Sweeping scanner role calls run_scan with model_override=candidate."""
    cases_path = _make_cases_file(tmp_path)
    captured_kwargs: dict = {}

    async def _mock_run_scan(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return _make_scan_result()

    with patch("eval_harness.sweep.run_scan", new=AsyncMock(side_effect=_mock_run_scan)):
        results = await run_role_sweep(
            "scanner",
            "us.amazon.nova-micro-v1:0",
            cases_path,
            fixture_vault_path,
            repeats=1,
        )

    assert len(results) == 1
    assert captured_kwargs.get("model_override") == "us.amazon.nova-micro-v1:0", (
        "scanner override must be passed as model_override kwarg"
    )


async def test_sweep_candidates_read_from_models_toml(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_role_sweep can be called with candidates read from load_role_config."""
    from model_adapter.loader import load_role_config

    # Verify that load_role_config returns a sweep_candidates key for roles that have it.
    # If not present, the caller falls back to [] — test that the contract holds.
    cfg = load_role_config("librarian")
    candidates = cfg.get("sweep_candidates", [])
    # sweep_candidates may be empty if not yet configured — we just verify the key
    # is accessible without error and is a list.
    assert isinstance(candidates, list)

    # Now run a sweep using the first candidate (or a known safe fallback)
    model_id = candidates[0] if candidates else "us.amazon.nova-lite-v1:0"
    cases_path = _make_cases_file(tmp_path)

    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=_make_query_result())):
        results = await run_role_sweep(
            "librarian",
            model_id,
            cases_path,
            fixture_vault_path,
            repeats=1,
        )

    assert len(results) >= 1
    assert results[0].model_id == model_id


async def test_role_sweep_partial_failure(tmp_path: Path, fixture_vault_path: Path) -> None:
    """Partial-failure isolation: one cell exception produces error SweepResult, not abort."""
    cases = [
        {"case_id": "c-01", "query": "q1", "expected_answer": "a1", "tags": []},
        {"case_id": "c-02", "query": "q2", "expected_answer": "a2", "tags": []},
    ]
    cases_path = _make_cases_file(tmp_path, cases)
    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated Bedrock error")
        return _make_query_result()

    with patch("eval_harness.sweep.run_query", new=AsyncMock(side_effect=_side_effect)):
        results = await run_role_sweep(
            "librarian",
            "us.amazon.nova-lite-v1:0",
            cases_path,
            fixture_vault_path,
            repeats=1,
        )

    assert len(results) == 2
    statuses = {r.status for r in results}
    assert "ok" in statuses
    assert "error" in statuses


async def test_role_sweep_semaphore_throttle(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_role_sweep accepts an external semaphore for rate-limit throttling (Pitfall 4)."""
    import asyncio

    cases_path = _make_cases_file(tmp_path)
    external_sem = asyncio.Semaphore(2)

    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=_make_query_result())):
        results = await run_role_sweep(
            "librarian",
            "us.amazon.nova-lite-v1:0",
            cases_path,
            fixture_vault_path,
            repeats=1,
            semaphore=external_sem,
        )

    assert len(results) == 1


async def test_role_sweep_sanitizes_model_id(tmp_path: Path, fixture_vault_path: Path) -> None:
    """SweepResult.safe_model_id has colon replaced with underscore."""
    cases_path = _make_cases_file(tmp_path)

    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=_make_query_result())):
        results = await run_role_sweep(
            "librarian",
            "us.amazon.nova-pro-v1:0",
            cases_path,
            fixture_vault_path,
            repeats=1,
        )

    assert len(results) == 1
    assert results[0].safe_model_id == "us.amazon.nova-pro-v1_0"


async def test_role_sweep_repeats(tmp_path: Path, fixture_vault_path: Path) -> None:
    """run_role_sweep with repeats=3 returns 3 SweepResult entries for 1 case."""
    cases_path = _make_cases_file(tmp_path)

    with patch("eval_harness.sweep.run_query", new=AsyncMock(return_value=_make_query_result())):
        results = await run_role_sweep(
            "librarian",
            "us.amazon.nova-lite-v1:0",
            cases_path,
            fixture_vault_path,
            repeats=3,
        )

    assert len(results) == 3
