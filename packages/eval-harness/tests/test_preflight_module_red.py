"""RED-phase tests for eval_harness.preflight module (Plan 07-04 Task 1).

These tests confirm the module does NOT yet exist and the API is missing.
They will fail until preflight.py is created.
"""

from __future__ import annotations

import pytest


def test_preflight_module_importable() -> None:
    """preflight module must be importable with its four public names."""
    from eval_harness.preflight import (  # noqa: F401
        HARD_CAP_USD,
        estimate_sweep_cost,
        preflight_bed01,
        preflight_check,
    )


def test_hard_cap_is_25() -> None:
    """HARD_CAP_USD must equal 25.0."""
    from eval_harness.preflight import HARD_CAP_USD

    assert HARD_CAP_USD == 25.0


def test_estimate_sweep_cost_returns_float() -> None:
    """estimate_sweep_cost returns a non-negative float."""
    from eval_harness.preflight import estimate_sweep_cost

    result = estimate_sweep_cost(
        {"librarian": ["us.anthropic.claude-haiku-4-5-20251001-v1:0"]},
        n_cases=1,
        repeats=1,
    )
    assert isinstance(result, float)
    assert result >= 0.0


def test_preflight_check_exists_and_callable() -> None:
    """preflight_check is callable."""
    from eval_harness.preflight import preflight_check

    assert callable(preflight_check)


def test_preflight_bed01_exists_and_callable() -> None:
    """preflight_bed01 is callable."""
    from eval_harness.preflight import preflight_bed01

    assert callable(preflight_bed01)
