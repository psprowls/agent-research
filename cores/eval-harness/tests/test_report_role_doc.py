"""Unit tests for render_role_doc() and pareto_frontier() in eval_harness.report.

Covers: per-role markdown doc rendering (SWEEP-03), Pareto frontier filter,
recommendation block emission (SWEEP-04).

Requirements: SWEEP-03, D-12.

All tests are deterministic (no Bedrock calls).
"""

from __future__ import annotations

import pytest
from eval_harness.sweep import SweepResult


# ---------------------------------------------------------------------------
# Helper: minimal SweepResult for unit testing
# ---------------------------------------------------------------------------


def _make_sweep_result(
    model_id: str,
    cost_usd: float | None = None,
    judge_scores: dict | None = None,
    structural: dict | None = None,
    status: str = "ok",
) -> SweepResult:
    """Create a minimal SweepResult for report unit testing."""
    return SweepResult(
        model_id=model_id,
        safe_model_id=model_id.replace(":", "_"),
        query="test query",
        answer="test answer [[SomePage]]",
        citations=["SomePage"],
        pages_drilled=2,
        tokens_in=100,
        tokens_out=50,
        cost_usd=cost_usd,
        wall_seconds=1.0,
        structural=structural or {"has_citation": True},
        status=status,
        judge_scores=judge_scores,
        seed=None,
    )


# ---------------------------------------------------------------------------
# render_role_doc tests (SWEEP-03 / D-12)
# ---------------------------------------------------------------------------


def test_render_role_doc_contains_required_sections() -> None:
    """render_role_doc output contains 'Pareto frontier', 'Previous default',
    role name, and raw scores table headings."""
    from eval_harness.report import render_role_doc

    candidates = [
        "us.anthropic.claude-sonnet-4-6",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "us.amazon.nova-pro-v1:0",
        "qwen.qwen3-32b-v1:0",
    ]
    results = [
        _make_sweep_result(
            "us.anthropic.claude-sonnet-4-6",
            cost_usd=0.02,
            judge_scores={"mean": 0.85},
        ),
        _make_sweep_result(
            "us.amazon.nova-pro-v1:0",
            cost_usd=0.01,
            judge_scores={"mean": 0.80},
        ),
    ]

    doc = render_role_doc(
        role="librarian",
        tier="quality",
        candidates=candidates,
        sweep_results=results,
        divergence_results=None,
        run_date="2026-05-16",
        commit_sha="abc1234",
        total_cost_usd=0.42,
        two_gate_outcomes=None,
    )

    assert "Pareto frontier" in doc
    assert "Previous default" in doc
    assert "librarian" in doc
    assert "quality" in doc
    assert "Raw Scores" in doc
    assert "Run Metadata" in doc
    assert "Recommendation" in doc
    assert "2026-05-16" in doc
    assert "abc1234" in doc


def test_pareto_frontier_filters_dominated_points() -> None:
    """pareto_frontier() removes dominated points (higher cost, lower quality)."""
    from eval_harness.report import pareto_frontier

    # A dominates B: A has higher quality AND lower cost
    # C has None cost → never dominated
    table = {
        "model-A": {"quality_score": 0.90, "cost_usd": 0.01},
        "model-B": {"quality_score": 0.80, "cost_usd": 0.02},  # dominated by A
        "model-C": {"quality_score": 0.70, "cost_usd": None},  # never dominated
    }

    frontier = pareto_frontier(table)

    assert "model-A" in frontier, "model-A is on the Pareto frontier"
    assert "model-B" not in frontier, "model-B is dominated by model-A"
    assert "model-C" in frontier, "cost_usd=None entries are never dominated"


def test_pareto_frontier_no_dominated_when_quality_tradeoff() -> None:
    """When models trade off quality vs cost, none is dominated."""
    from eval_harness.report import pareto_frontier

    table = {
        "cheap": {"quality_score": 0.70, "cost_usd": 0.01},
        "expensive": {"quality_score": 0.90, "cost_usd": 0.05},
    }

    frontier = pareto_frontier(table)

    # Neither dominates the other (one has better quality, other has lower cost)
    assert "cheap" in frontier
    assert "expensive" in frontier
