"""Offline capture test for run_full_matrix Gate 1 wiring (quick-260529-q8r).

NOT gated on GRAPH_WIKI_RUN_EVAL and makes no Bedrock calls: it drives
``run_full_matrix`` with ``dry_run=True`` (the inner sweep loop ``continue``s on
dry_run, but ``score_two_gate`` is STILL called once per candidate). A capturing
wrapper records the kwargs so we can assert that a divergence-eligible role
("librarian") receives a real ``DivergenceMetric`` instance and an existing-dir
``Path`` baselines_dir — proving the two formerly-hardcoded ``None``s are gone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import eval_harness.sweep as sweep_mod
from eval_harness.divergence.metric import DivergenceMetric
from eval_harness.two_gate import TwoGateOutcome
from eval_harness.two_gate import score_two_gate as original  # noqa: F401


@pytest.mark.asyncio
async def test_run_full_matrix_wires_divergence_metric_and_baselines(
    fixture_workspace_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    def score_two_gate_wrapper(**kwargs) -> TwoGateOutcome:
        captured.append(dict(kwargs))
        # Do NOT call the real scorer — avoids running divergence checks.
        return TwoGateOutcome(
            qualified=False,
            gate1_passed=None,
            gate2_passed=None,
            divergence_failures=None,
            panel_mean=None,
            threshold_used=0.95,
            notes="stub",
        )

    monkeypatch.setattr(sweep_mod, "score_two_gate", score_two_gate_wrapper)

    # Build minimal tmp inputs matching _load_and_validate_cases schema
    # (requires "query" str + "expected_answer" str).
    query_cases_path = tmp_path / "query_cases.json"
    query_cases_path.write_text(
        json.dumps(
            [
                {
                    "query": "what is the project",
                    "expected_answer": "a python monorepo",
                    "case_id": "q-01",
                }
            ]
        ),
        encoding="utf-8",
    )

    code_reader_cases_path = tmp_path / "code_reader_cases.json"
    code_reader_cases_path.write_text(
        json.dumps(
            [
                {
                    "query": "read the module",
                    "expected_answer": "a description of the module",
                    "case_id": "cr-01",
                }
            ]
        ),
        encoding="utf-8",
    )

    ingestor_source_path = tmp_path / "ingestor_source.md"
    ingestor_source_path.write_text("# Source\n\nSome markdown.\n", encoding="utf-8")

    await sweep_mod.run_full_matrix(
        role_candidates={"librarian": ["model-x"]},
        workspace_path=fixture_workspace_path,
        query_cases_path=query_cases_path,
        code_reader_cases_path=code_reader_cases_path,
        ingestor_source_path=ingestor_source_path,
        repeats=1,
        output_dir=tmp_path / "out",
        dry_run=True,
        skip_bed01=True,
        auto_confirm=True,
    )

    assert captured, "score_two_gate was never called"

    librarian_calls = [c for c in captured if c["role"] == "librarian"]
    assert librarian_calls, "no score_two_gate call captured for librarian"
    call = librarian_calls[0]

    assert isinstance(call["divergence_metric_or_none"], DivergenceMetric), (
        "librarian must receive a real DivergenceMetric, not None"
    )
    assert isinstance(call["baselines_dir"], Path), (
        "librarian must receive a Path baselines_dir, not None"
    )
    assert call["baselines_dir"].is_dir(), (
        f"baselines_dir {call['baselines_dir']} must be an existing directory"
    )


# ---------------------------------------------------------------------------
# Fix F (quick-260529-sot): SweepResult.judge_scores writeback helpers
# ---------------------------------------------------------------------------


def _mk_result(query: str, answer: str = "an answer", status: str = "ok") -> sweep_mod.SweepResult:
    """Minimal SweepResult fixture for writeback-helper tests."""
    return sweep_mod.SweepResult(
        model_id="model-x",
        safe_model_id="model-x",
        query=query,
        answer=answer,
        citations=[],
        pages_drilled=0,
        tokens_in=None,
        tokens_out=None,
        cost_usd=None,
        wall_seconds=0.0,
        structural={},
        status=status,
    )


def test_judgeable_writeback_sets_panel_mean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With GRAPH_WIKI_RUN_JUDGES set and panel_score patched to {"mean": 0.8, ...},
    a librarian ok SweepResult ends with judge_scores["mean"] == 0.8, and the
    helper returns that mean."""
    monkeypatch.setenv("GRAPH_WIKI_RUN_JUDGES", "1")

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps([{"query": "q1", "expected_answer": "exp", "case_id": "c1"}]),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "eval_harness.judge.panel_score",
        lambda query, actual, expected: {"mean": 0.8, "judge_a": 0.8, "judge_b": 0.8},
    )

    r = _mk_result("q1")
    mean = sweep_mod._score_and_writeback_judgeable("librarian", [r], cases_path)

    assert r.judge_scores is not None
    assert r.judge_scores["mean"] == 0.8
    assert mean == 0.8


def test_judgeable_writeback_judges_off_leaves_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With GRAPH_WIKI_RUN_JUDGES unset, judge_scores stays None and helper returns None."""
    monkeypatch.delenv("GRAPH_WIKI_RUN_JUDGES", raising=False)

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps([{"query": "q1", "expected_answer": "exp", "case_id": "c1"}]),
        encoding="utf-8",
    )

    r = _mk_result("q1")
    mean = sweep_mod._score_and_writeback_judgeable("librarian", [r], cases_path)

    assert r.judge_scores is None
    assert mean is None


def test_structural_writeback_sets_divergence_pass_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """With run_programmatic patched to {"R1":{runs:1,fail:0},"R2":{runs:1,fail:1}},
    a scanner ok SweepResult ends with judge_scores["mean"] == 0.5 (pass-rate)."""
    metric = DivergenceMetric.__new__(DivergenceMetric)  # no __init__ — only run_programmatic used
    monkeypatch.setattr(
        metric,
        "run_programmatic",
        lambda outputs: {"R1": {"runs": 1, "failures": 0}, "R2": {"runs": 1, "failures": 1}},
    )

    r = _mk_result("scan q")
    sweep_mod._writeback_structural_quality(metric, [r])

    assert r.judge_scores is not None
    assert r.judge_scores["mean"] == 0.5
