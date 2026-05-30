"""Two-gate scoring protocol for the cost-frontier sweep (D-07, D-08).

Implements the qualification logic that determines whether a candidate model
passes enough quality bars to be considered for a role-default swap.

All 6 in-scope roles (librarian, ingestor, linter, scanner, code_reader, synthesizer)
run both gates (D-06 Phase 16 — D-08 superseded):
  Gate 1 — divergence programmatic regression: current divergence failures must
            not exceed baseline failures on any hard-severity rule.
  Gate 2 — end-to-end quality: panel_score mean must be >= default_panel_mean * threshold.

Security:
  T-07-10: AssertionError from check_regression is caught and surfaced as
           gate1_passed=False — the error text is logged at DEBUG, not re-raised.
           This prevents a crafted assertion message from aborting a sweep cell.

Exports:
  ROLES_WITH_DIVERGENCE  — frozenset of role names that run Gate 1
  TwoGateOutcome         — frozen dataclass capturing both gate results
  score_two_gate         — entry point for the outer sweep driver
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from eval_harness.divergence.metric import check_regression, load_baseline

logger = logging.getLogger(__name__)

# All 6 in-scope roles run Gate 1 (D-06 Phase 16: code_reader + synthesizer
# divergence rubrics authored in 16-01 supersede the prior D-08 skip).
ROLES_WITH_DIVERGENCE: frozenset[str] = frozenset(
    {"librarian", "ingestor", "linter", "scanner", "code_reader", "synthesizer"}
)


@dataclass(frozen=True)
class TwoGateOutcome:
    """Immutable result of the two-gate scoring pass for one (role, candidate) cell.

    Attributes:
        qualified:           True when the candidate cleared all applicable gates.
        gate1_passed:        True/False = divergence regression passed/failed.
                             None for roles without divergence rubrics (D-08).
        gate2_passed:        True/False = quality score threshold passed/failed.
                             None when panel_mean or default_panel_mean is None.
        divergence_failures: Per-rule failure counts from run_programmatic().
                             None for D-08 roles.
        panel_mean:          Candidate's judge panel mean score (None if unavailable).
        threshold_used:      The threshold fraction used for Gate 2 (e.g. 0.95).
        notes:               Human-readable explanation of the outcome.
    """

    qualified: bool
    gate1_passed: bool | None
    gate2_passed: bool | None
    divergence_failures: dict[str, int] | None
    panel_mean: float | None
    threshold_used: float
    notes: str


def score_two_gate(
    role: str,
    divergence_metric_or_none,
    agent_outputs_by_case: list[tuple[str, object]],
    baselines_dir,
    panel_mean: float | None,
    default_panel_mean: float | None,
    threshold: float,
) -> TwoGateOutcome:
    """Compute the two-gate qualification outcome for a (role, candidate) cell.

    Args:
        role:                   Agent role name (e.g. "librarian", "synthesizer").
        divergence_metric_or_none:
                                DivergenceMetric instance for roles in
                                ROLES_WITH_DIVERGENCE; None for D-08 roles.
        agent_outputs_by_case:  List of (case_id, AgentOutputProxy) pairs.
        baselines_dir:          Path to the directory containing
                                ``divergence-{role}.json`` baseline files.
        panel_mean:             Candidate model's mean judge panel score, or
                                None when scoring was not run / failed.
        default_panel_mean:     Current-default model's mean judge panel score,
                                or None when unavailable.
        threshold:              Gate 2 pass threshold as a fraction of the
                                default score (e.g. 0.95 for "within 5%").

    Returns:
        TwoGateOutcome with qualified, gate1_passed, gate2_passed,
        divergence_failures, panel_mean, threshold_used, and notes.
    """
    gate1_passed: bool | None = None
    divergence_failures: dict[str, int] | None = None

    # ------------------------------------------------------------------
    # Gate 1: divergence programmatic regression check (D-07 roles only)
    # ------------------------------------------------------------------
    if role in ROLES_WITH_DIVERGENCE:
        if not agent_outputs_by_case:
            # No ok outputs to evaluate — Gate 1 has no signal. Leave gate1=None
            # and divergence_failures=None so the candidate cannot falsely qualify.
            gate1_passed = None
            divergence_failures = None
            logger.debug("[%s] Gate 1: no outputs — not evaluated", role)
        elif divergence_metric_or_none is None:
            # Caller omitted the metric for a D-07 role — treat as failure
            gate1_passed = False
            divergence_failures = {}
            logger.debug("[%s] Gate 1: divergence_metric not provided — gate1=FAIL", role)
        else:
            try:
                prog_results = divergence_metric_or_none.run_programmatic(
                    agent_outputs_by_case
                )
                divergence_failures = {
                    rule_id: data["failures"]
                    for rule_id, data in prog_results.items()
                }
                baseline = load_baseline(role, baselines_dir)
                check_regression(role, prog_results, baseline)
                gate1_passed = True
                logger.debug("[%s] Gate 1: divergence regression check PASS", role)
            except AssertionError as exc:
                gate1_passed = False
                logger.debug(
                    "[%s] Gate 1: divergence regression check FAIL — %s", role, exc
                )
    else:
        # D-08: no Gate 1 for synthesizer / code_reader
        logger.debug("[%s] Gate 1: skipped (D-08 role — no divergence rubric)", role)

    # ------------------------------------------------------------------
    # Gate 2: end-to-end quality threshold
    # ------------------------------------------------------------------
    gate2_passed: bool | None = None

    if panel_mean is None or default_panel_mean is None:
        gate2_passed = None
        logger.debug(
            "[%s] Gate 2: skipped — panel_mean=%s default_panel_mean=%s",
            role,
            panel_mean,
            default_panel_mean,
        )
    else:
        required = default_panel_mean * threshold
        gate2_passed = panel_mean >= required
        logger.debug(
            "[%s] Gate 2: panel_mean=%.4f >= %.4f (default=%.4f × threshold=%.2f) → %s",
            role,
            panel_mean,
            required,
            default_panel_mean,
            threshold,
            "PASS" if gate2_passed else "FAIL",
        )

    # ------------------------------------------------------------------
    # Qualification: both applicable gates must pass (or be N/A)
    # ------------------------------------------------------------------
    # A gate in {True, None} does not disqualify the candidate.
    # A gate value of False disqualifies.
    # Special case: if both gates are None there is no quality signal at all.
    gate1_ok = gate1_passed in {True, None}
    gate2_ok = gate2_passed in {True, None}

    if gate1_passed is None and gate2_passed is None:
        qualified = False
        notes = "no quality signal — both gates returned None; cannot qualify"
    elif gate1_ok and gate2_ok:
        qualified = True
        parts: list[str] = []
        if gate1_passed is True:
            parts.append("Gate 1 (divergence) PASS")
        if gate2_passed is True:
            parts.append("Gate 2 (quality) PASS")
        if gate1_passed is None:
            parts.append("Gate 1 N/A (D-08 role)")
        if gate2_passed is None:
            parts.append("Gate 2 N/A (panel_mean unavailable)")
        notes = "; ".join(parts)
    else:
        qualified = False
        parts = []
        if gate1_passed is False:
            parts.append("Gate 1 (divergence) FAIL")
        if gate2_passed is False:
            parts.append(
                f"Gate 2 (quality) FAIL — panel_mean {panel_mean:.4f} < "
                f"required {(default_panel_mean or 0.0) * threshold:.4f}"
            )
        notes = "; ".join(parts)

    logger.info(
        "[%s] two-gate outcome: qualified=%s gate1=%s gate2=%s — %s",
        role,
        qualified,
        gate1_passed,
        gate2_passed,
        notes,
    )

    return TwoGateOutcome(
        qualified=qualified,
        gate1_passed=gate1_passed,
        gate2_passed=gate2_passed,
        divergence_failures=divergence_failures,
        panel_mean=panel_mean,
        threshold_used=threshold,
        notes=notes,
    )
