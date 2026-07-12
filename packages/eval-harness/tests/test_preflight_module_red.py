"""RED-phase tests for eval_harness.preflight module (Plan 07-04 Task 1).

These tests confirm the module does NOT yet exist and the API is missing.
They will fail until preflight.py is created.
"""

from __future__ import annotations


def test_hard_cap_is_25() -> None:
    """HARD_CAP_USD must equal 25.0."""
    from eval_harness.preflight import HARD_CAP_USD

    assert HARD_CAP_USD == 25.0
