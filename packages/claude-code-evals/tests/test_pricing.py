import pytest
from claude_code_evals.pricing import UnknownModelError, cost_for_usage


def test_cost_for_usage_sonnet():
    cost = cost_for_usage("claude-sonnet-4-6", {"input": 1_000_000, "output": 0})
    assert cost == pytest.approx(3.0)


def test_cost_for_usage_with_cache():
    cost = cost_for_usage(
        "claude-sonnet-4-6",
        {
            "input": 0,
            "output": 0,
            "cache_read": 1_000_000,
            "cache_write": 1_000_000,
        },
    )
    assert cost == pytest.approx(0.30 + 3.75)


def test_unknown_model_raises():
    with pytest.raises(UnknownModelError):
        cost_for_usage("nonexistent-model", {"input": 1000})


def test_missing_keys_default_to_zero():
    cost = cost_for_usage("claude-haiku-4-5-20251001", {})
    assert cost == 0.0
