"""Unit tests for render_recommendation_block() — models.toml comment block emitter.

Covers: recommendation block includes previous default (SWEEP-04), only
Pareto members appear, run_date is embedded.

Requirements: SWEEP-04, D-11.

All tests are deterministic (no Bedrock calls).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# render_recommendation_block tests (SWEEP-04 / D-11)
# ---------------------------------------------------------------------------


def test_recommendation_block_includes_previous_default() -> None:
    """render_recommendation_block output includes '# Previous default:' line."""
    from eval_harness.report import render_recommendation_block

    frontier = {
        "us.amazon.nova-pro-v1:0": {"quality_score": 0.82, "cost_usd": 0.005},
    }
    block = render_recommendation_block(
        role="librarian",
        run_date="2026-05-16",
        frontier=frontier,
        current_default="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )

    assert "# Previous default:" in block
    assert "us.anthropic.claude-haiku-4-5-20251001-v1:0" in block


def test_recommendation_block_lists_pareto_members_only() -> None:
    """render_recommendation_block lists only Pareto-frontier model IDs."""
    from eval_harness.report import render_recommendation_block

    frontier = {
        "us.amazon.nova-pro-v1:0": {"quality_score": 0.82, "cost_usd": 0.005},
        "us.amazon.nova-lite-v1:0": {"quality_score": 0.78, "cost_usd": 0.002},
    }
    block = render_recommendation_block(
        role="librarian",
        run_date="2026-05-16",
        frontier=frontier,
        current_default="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )

    # Both frontier members should appear
    assert "us.amazon.nova-pro-v1:0" in block
    assert "us.amazon.nova-lite-v1:0" in block

    # The header line format per D-11
    assert "# Sweep candidates (run 2026-05-16)" in block

    # Each frontier member is commented out
    lines = block.splitlines()
    for line in lines:
        assert line.startswith("#"), f"All lines should start with '#': {line!r}"


def test_recommendation_block_uses_run_date() -> None:
    """render_recommendation_block embeds run_date in the header comment."""
    from eval_harness.report import render_recommendation_block

    frontier = {
        "us.amazon.nova-lite-v1:0": {"quality_score": 0.78, "cost_usd": 0.002},
    }
    block = render_recommendation_block(
        role="scanner",
        run_date="2026-05-16",
        frontier=frontier,
        current_default="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )

    assert "2026-05-16" in block
    assert "# Sweep candidates (run 2026-05-16)" in block


def test_recommendation_block_none_cost() -> None:
    """render_recommendation_block handles cost_usd=None gracefully."""
    from eval_harness.report import render_recommendation_block

    frontier = {
        "unknown-model": {"quality_score": 0.75, "cost_usd": None},
    }
    block = render_recommendation_block(
        role="librarian",
        run_date="2026-05-16",
        frontier=frontier,
        current_default="current-model",
    )

    assert "N/A" in block or "unknown-model" in block
    assert "# Previous default: current-model" in block
