"""Unit tests for render_role_doc() and pareto_frontier() in eval_harness.report.

Covers: per-role markdown doc rendering (SWEEP-03), Pareto frontier filter,
recommendation block emission (SWEEP-04).

Requirements: SWEEP-03, D-12.

All tests are deterministic (no Bedrock calls). Module-level pytest.skip
guards are in place until Plan 07-06 lands render_role_doc and pareto_frontier.
"""

from __future__ import annotations

import pytest
from eval_harness.sweep import SweepResult

pytestmark = pytest.mark.skip(reason="Pending Plan 07-06")


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
    assert False, "TODO Plan 07-06"


def test_pareto_frontier_filters_dominated_points() -> None:
    """pareto_frontier() removes dominated points (higher cost, lower quality)."""
    assert False, "TODO Plan 07-06"
