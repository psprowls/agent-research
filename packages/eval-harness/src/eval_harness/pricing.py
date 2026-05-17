"""Hardcoded model pricing for Bedrock models. Update manually when AWS changes prices.

Prices are USD per million tokens, current as of 2026-05-14.
Ported from lattice-evals/pricing.py and extended with Bedrock model IDs.
"""

from __future__ import annotations


class UnknownModelError(KeyError):
    pass


# USD per 1M tokens; verified against AWS pricing page and Anthropic pricing on 2026-05-14.
# Bedrock non-Claude models (Nova, Qwen) do not support prompt caching — no cache keys.
PRICES: dict[str, dict[str, float]] = {
    # Claude models via direct Anthropic API (from lattice-evals port, cache keys included)
    "claude-opus-4-7": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "claude-haiku-4-5": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.10,
        "cache_write": 1.25,
    },
    # Claude models via AWS Bedrock cross-region inference profiles
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "input": 1.0,
        "output": 5.0,
    },
    "us.anthropic.claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
    },
    # Amazon Nova models via Bedrock (no prompt caching)
    "us.amazon.nova-pro-v1:0": {
        "input": 0.80,
        "output": 3.20,
    },
    "us.amazon.nova-lite-v1:0": {
        "input": 0.30,
        "output": 1.20,
    },
    "us.amazon.nova-micro-v1:0": {
        "input": 0.035,
        "output": 0.14,
    },
    # Qwen3 via Bedrock (no prompt caching)
    "qwen.qwen3-32b-v1:0": {
        "input": 0.40,
        "output": 1.60,
    },
}


def cost_for_usage(model: str, usage: dict[str, int]) -> float:
    """Return USD cost for token usage on `model`.

    `usage` keys: input, output, cache_read, cache_write (all int token counts).
    Missing keys default to 0.

    Raises:
        UnknownModelError: if model is not in PRICES.
    """
    if model not in PRICES:
        raise UnknownModelError(f"unknown model {model!r}; update eval_harness/pricing.py")
    p = PRICES[model]
    return sum(usage.get(k, 0) * p[k] / 1_000_000 for k in p)
