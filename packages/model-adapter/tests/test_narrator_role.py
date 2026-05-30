"""Phase 45 D-06: tests for the new `narrator` role in models.toml."""

from __future__ import annotations

import pytest

HAIKU_ARN = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


def test_narrator_role_in_models_toml():
    """Phase 45 D-06: [roles.narrator] is present with the four expected keys."""
    from model_adapter.loader import _load_models_config

    config = _load_models_config()
    assert "narrator" in config["roles"], (
        "Phase 45 D-06 requires a [roles.narrator] section in models.toml"
    )
    narrator = config["roles"]["narrator"]
    assert narrator["model_id"] == HAIKU_ARN, (
        "narrator initial model_id must match scanner (v1.8 D-06; v1.9 refines)"
    )
    assert narrator["region"] == "us-east-1"
    assert narrator["max_tokens"] == 600, (
        "narrator emits prose only — max_tokens lower than scanner"
    )
    assert narrator["max_concurrency"] == 10


def test_load_role_config_narrator_returns_dict():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("narrator")
    assert isinstance(cfg, dict)
    assert cfg["model_id"] == HAIKU_ARN
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 600
    assert cfg["max_concurrency"] == 10


def test_make_llm_narrator_does_not_raise_keyerror():
    """`make_llm("narrator")` must instantiate without KeyError.

    Pure object construction — no Bedrock network calls.
    """
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    try:
        llm = make_llm("narrator")
    except KeyError as exc:  # pragma: no cover — guard for regression visibility
        pytest.fail(f"make_llm('narrator') raised KeyError: {exc!r}")

    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == HAIKU_ARN
