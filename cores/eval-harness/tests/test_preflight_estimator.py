"""Unit tests for estimate_sweep_cost() pre-flight cost estimator.

Covers: 24-cell sweep under $25 hard cap (D-13), empty candidate handling,
graceful skip of unknown model IDs.

Requirements: D-13.

All tests are deterministic (no Bedrock calls). Module-level pytest.skip
guards are in place until Plan 07-04 lands estimate_sweep_cost in sweep.py.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Pending Plan 07-04")


# ---------------------------------------------------------------------------
# estimate_sweep_cost tests (D-13)
# ---------------------------------------------------------------------------


def test_estimate_24_cell_sweep_within_cap() -> None:
    """estimate_sweep_cost for a 6-role × 4-candidate matrix is below $25.00 cap."""
    assert False, "TODO Plan 07-04"


def test_estimator_returns_zero_for_empty_candidates() -> None:
    """estimate_sweep_cost returns 0.0 when all roles have empty candidate lists."""
    assert False, "TODO Plan 07-04"


def test_estimator_skips_unknown_model_ids() -> None:
    """estimate_sweep_cost silently skips unknown model IDs (UnknownModelError swallowed)."""
    assert False, "TODO Plan 07-04"
