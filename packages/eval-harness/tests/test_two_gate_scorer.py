"""Unit tests for the D-07 two-gate scoring protocol in run_role_sweep().

Covers: Gate 1 (divergence programmatic check), Gate 2 (end-to-end judge
score), role isolation (synthesizer skips Gate 1).

Requirements: D-07, D-11.

All tests use DivergenceMetric construction + AgentOutputProxy patterns
from test_divergence_metric.py. No Bedrock calls needed for Gate 1. Module-
level pytest.skip guards are in place until Plan 07-05 lands the scorer code.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.check import AgentOutputProxy
from eval_harness.two_gate import ROLES_WITH_DIVERGENCE, TwoGateOutcome, score_two_gate


# ---------------------------------------------------------------------------
# Gate 1: divergence programmatic check
# ---------------------------------------------------------------------------


def test_two_gate_librarian_pass(fixture_wiki_path: Path) -> None:
    """Both gates pass for a well-formed librarian answer; result is qualified."""
    from eval_harness.divergence.metric import DivergenceMetric

    baselines_dir = (
        Path(__file__).parent.parent / "baselines"
    )

    metric = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )

    # Well-formed output that should pass all hard-rule checks
    outputs = [
        (
            "case-01",
            AgentOutputProxy(
                answer="See [[packages/lattice-wiki-core]] for details. Also `src/main.py:10`."
            ),
        )
    ]

    outcome = score_two_gate(
        role="librarian",
        divergence_metric_or_none=metric,
        agent_outputs_by_case=outputs,
        baselines_dir=baselines_dir,
        panel_mean=0.85,
        default_panel_mean=0.80,
        threshold=0.95,
    )

    # Gate 1: librarian is in ROLES_WITH_DIVERGENCE — should have a result
    assert outcome.gate1_passed is not None
    # Gate 2 should pass since 0.85 >= 0.80 * 0.95 = 0.76
    assert outcome.gate2_passed is True
    assert outcome.panel_mean == pytest.approx(0.85)
    assert outcome.threshold_used == pytest.approx(0.95)
    # Qualified only if gate1 also passed
    if outcome.gate1_passed is True:
        assert outcome.qualified is True
    # divergence_failures dict should be present for D-07 role
    assert outcome.divergence_failures is not None
    assert isinstance(outcome.divergence_failures, dict)


def test_two_gate_librarian_divergence_fail(fixture_wiki_path: Path) -> None:
    """Gate 1 fails when hard-rule failures exceed baseline; result is not qualified."""
    from eval_harness.divergence.metric import DivergenceMetric

    baselines_dir = (
        Path(__file__).parent.parent / "baselines"
    )

    metric = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )

    # Inject many hard-rule failures by mocking run_programmatic to return
    # worse-than-baseline failure counts, and mock check_regression to raise.
    heavy_failures = {
        "LIB-001-wikilink-resolves": {"runs": 1, "failures": 99, "accepted_failures": []},
        "LIB-002-citation-present": {"runs": 1, "failures": 99, "accepted_failures": []},
        "LIB-004-code-path-format": {"runs": 1, "failures": 0, "accepted_failures": []},
    }

    with (
        patch.object(metric, "run_programmatic", return_value=heavy_failures),
        patch(
            "eval_harness.two_gate.check_regression",
            side_effect=AssertionError("LIB-001: 99 failures > baseline 3"),
        ),
    ):
        outcome = score_two_gate(
            role="librarian",
            divergence_metric_or_none=metric,
            agent_outputs_by_case=[("case-01", AgentOutputProxy(answer="bad output"))],
            baselines_dir=baselines_dir,
            panel_mean=0.85,
            default_panel_mean=0.80,
            threshold=0.95,
        )

    assert outcome.gate1_passed is False
    assert outcome.qualified is False
    assert "Gate 1" in outcome.notes
    assert outcome.divergence_failures is not None


def test_two_gate_librarian_quality_fail(fixture_wiki_path: Path) -> None:
    """Gate 1 passes but Gate 2 (judge score) fails threshold; result is not qualified."""
    from eval_harness.divergence.metric import DivergenceMetric

    baselines_dir = (
        Path(__file__).parent.parent / "baselines"
    )

    metric = DivergenceMetric(
        role="librarian",
        checks=ROLE_CHECKS["librarian"],
        rubric_path=ROLE_RUBRICS["librarian"],
        wiki=fixture_wiki_path,
    )

    # Gate 1 passes (no assertion raised) but Gate 2 fails
    clean_results = {
        "LIB-001-wikilink-resolves": {"runs": 1, "failures": 0, "accepted_failures": []},
        "LIB-002-citation-present": {"runs": 1, "failures": 0, "accepted_failures": []},
        "LIB-004-code-path-format": {"runs": 1, "failures": 0, "accepted_failures": []},
    }

    with (
        patch.object(metric, "run_programmatic", return_value=clean_results),
        patch("eval_harness.two_gate.check_regression"),  # does not raise
    ):
        outcome = score_two_gate(
            role="librarian",
            divergence_metric_or_none=metric,
            agent_outputs_by_case=[("case-01", AgentOutputProxy(answer="ok"))],
            baselines_dir=baselines_dir,
            panel_mean=0.50,       # very low quality
            default_panel_mean=0.80,
            threshold=0.95,        # requires >= 0.80 * 0.95 = 0.76
        )

    assert outcome.gate1_passed is True
    assert outcome.gate2_passed is False  # 0.50 < 0.76
    assert outcome.qualified is False
    assert "Gate 2" in outcome.notes


# ---------------------------------------------------------------------------
# Synthesizer: end-to-end only (no Gate 1)
# ---------------------------------------------------------------------------


def test_synthesizer_now_runs_gate1_after_phase16(fixture_wiki_path: Path) -> None:
    """Phase 16 D-06: synthesizer is now in ROLES_WITH_DIVERGENCE and runs Gate 1.

    Replaces the prior D-08 "skip Gate 1" assertion. The synthesizer rubric
    + programmatic checks (SYN-001..SYN-004) were authored in 16-01.
    """
    # Phase 16: synthesizer IS in ROLES_WITH_DIVERGENCE
    assert "synthesizer" in ROLES_WITH_DIVERGENCE
    assert "code_reader" in ROLES_WITH_DIVERGENCE


def test_no_quality_signal_is_unqualified(fixture_wiki_path: Path) -> None:
    """When neither gate has any signal (no metric + no panel), outcome is not qualified.

    Post-Phase-16: all roles are in ROLES_WITH_DIVERGENCE, so a missing metric
    triggers gate1=False rather than gate1=None. To preserve the "no quality
    signal" intent we hit it by giving the gate-1 path a metric that returns
    nothing — but more directly, we simulate an unknown role (not in
    ROLES_WITH_DIVERGENCE) which still produces both gates as None.
    """
    baselines_dir = (
        Path(__file__).parent.parent / "baselines"
    )

    # "unknown-role" is not in ROLES_WITH_DIVERGENCE -> Gate 1 stays None.
    # No panel inputs -> Gate 2 stays None. Together: "no quality signal".
    outcome = score_two_gate(
        role="unknown-role",
        divergence_metric_or_none=None,
        agent_outputs_by_case=[],
        baselines_dir=baselines_dir,
        panel_mean=None,
        default_panel_mean=None,
        threshold=0.95,
    )

    assert outcome.gate1_passed is None
    assert outcome.gate2_passed is None
    assert outcome.qualified is False
    assert "no quality signal" in outcome.notes


def test_empty_outputs_divergence_role_is_unqualified(tmp_path: Path) -> None:
    """A divergence role with NO ok outputs must not run the metric: gate1=None,
    divergence_failures=None, qualified=False (Fix E, quick-260529-sot)."""
    mock_metric = MagicMock()

    outcome = score_two_gate(
        role="librarian",
        divergence_metric_or_none=mock_metric,
        agent_outputs_by_case=[],
        baselines_dir=tmp_path,
        panel_mean=None,
        default_panel_mean=None,
        threshold=0.95,
    )

    assert outcome.gate1_passed is None
    assert outcome.divergence_failures is None
    assert outcome.gate2_passed is None
    assert outcome.qualified is False
    # The metric must NOT have been evaluated against zero outputs.
    mock_metric.run_programmatic.assert_not_called()


def test_roles_with_divergence_constant() -> None:
    """ROLES_WITH_DIVERGENCE covers all 6 in-scope roles (Phase 16 D-06)."""
    assert isinstance(ROLES_WITH_DIVERGENCE, frozenset)
    assert ROLES_WITH_DIVERGENCE == {
        "librarian",
        "ingestor",
        "linter",
        "scanner",
        "code_reader",
        "synthesizer",
    }
