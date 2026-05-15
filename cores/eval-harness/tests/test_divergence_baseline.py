from __future__ import annotations

"""Unit tests for divergence baseline load/write/regression-check (EVAL-13).

All tests are pure unit — no Bedrock calls, no subprocess. Tests cover:
- load_baseline(): returns empty dict when file is missing
- write_baseline(): writes JSON with all required schema keys
- check_regression(): raises AssertionError when hard-severity failures increase
- check_regression(): does not raise for soft-severity increases
- --accept-divergence-baseline flag: rewrites baseline file

Tests skip at module level when the divergence.metric module has not landed yet
(before 06-09); they are stub-stubbed so `pytest --collect-only` shows the
expected test IDs even before the implementation exists.
"""

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import guard — skip entire module if divergence.metric not yet implemented
# ---------------------------------------------------------------------------

_DIVERGENCE_AVAILABLE = True
try:
    from eval_harness.divergence.metric import (
        check_regression,
        load_baseline,
        write_baseline,
    )
except ImportError:
    _DIVERGENCE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _DIVERGENCE_AVAILABLE,
    reason="divergence.metric module not yet implemented (lands in 06-09)",
)


# ---------------------------------------------------------------------------
# load_baseline() tests
# ---------------------------------------------------------------------------


def test_load_baseline_returns_empty_when_missing(tmp_path: Path) -> None:
    """load_baseline returns {} when the baseline file does not exist (Pitfall 5)."""
    pytest.skip("filled in by 06-09")


# ---------------------------------------------------------------------------
# write_baseline() tests
# ---------------------------------------------------------------------------


def test_write_baseline_schema(tmp_path: Path) -> None:
    """write_baseline writes JSON with all required schema keys: role, recorded_at, agent_commit, checks."""
    pytest.skip("filled in by 06-09")


# ---------------------------------------------------------------------------
# check_regression() tests
# ---------------------------------------------------------------------------


def test_check_regression_raises_on_hard_increase(tmp_path: Path) -> None:
    """check_regression raises AssertionError when hard-severity failures increase vs baseline.

    The error message must mention 'accept-divergence-baseline' so the caller
    knows how to re-accept the baseline.
    """
    pytest.skip("filled in by 06-09")


def test_check_regression_does_not_raise_for_soft(tmp_path: Path) -> None:
    """check_regression does not raise for soft-severity failure increases."""
    pytest.skip("filled in by 06-09")


def test_accept_baseline_flag_rewrites_file(tmp_path: Path) -> None:
    """When accept_baseline=True, write_baseline overwrites the existing file."""
    pytest.skip("filled in by 06-09")
