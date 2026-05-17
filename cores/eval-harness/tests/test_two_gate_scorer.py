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

import pytest
from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS
from eval_harness.divergence.check import AgentOutputProxy

pytestmark = pytest.mark.skip(reason="Pending Plan 07-05")


# ---------------------------------------------------------------------------
# Gate 1: divergence programmatic check
# ---------------------------------------------------------------------------


def test_two_gate_librarian_pass(fixture_vault_path: Path) -> None:
    """Both gates pass for a well-formed librarian answer; result is 'pass'."""
    assert False, "TODO Plan 07-05"


def test_two_gate_librarian_divergence_fail(fixture_vault_path: Path) -> None:
    """Gate 1 fails when hard-rule failures exceed baseline; result is 'divergence_fail'."""
    assert False, "TODO Plan 07-05"


def test_two_gate_librarian_quality_fail(fixture_vault_path: Path) -> None:
    """Gate 1 passes but Gate 2 (judge score) fails threshold; result is 'quality_fail'."""
    assert False, "TODO Plan 07-05"


# ---------------------------------------------------------------------------
# Synthesizer: end-to-end only (no Gate 1)
# ---------------------------------------------------------------------------


def test_synthesizer_uses_end_to_end_only(fixture_vault_path: Path) -> None:
    """Synthesizer role skips Gate 1 (no divergence check) and uses Gate 2 only."""
    assert False, "TODO Plan 07-05"
