"""Hardcoded Claude model pricing for cost tracking. Update manually when Anthropic changes prices.

Prices are USD per million tokens, current as of 2026-06-07.
"""

from __future__ import annotations


class UnknownModelError(KeyError):
    pass


PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.10,
        "cache_write": 1.25,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "claude-opus-4-7": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "claude-opus-4-8": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
}


def cost_for_usage(model: str, usage: dict[str, int]) -> float:
    """Return USD cost for token usage on model.

    usage keys: input, output, cache_read, cache_write (int token counts).
    Missing keys default to 0. Raises UnknownModelError if model not in PRICES.
    """
    if model not in PRICES:
        raise UnknownModelError(f"unknown model {model!r}; update pricing.py")
    p = PRICES[model]
    return sum(usage.get(k, 0) * p[k] / 1_000_000 for k in p)
