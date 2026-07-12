"""Phase 45 D-06: tests for the new `narrator` role in models.toml."""

from __future__ import annotations

import pytest

KIMI_MODEL_ID = "moonshotai.kimi-k2.5"


def test_load_role_config_narrator_returns_dict():
    from graph_wiki_core.roles import load_role_config

    cfg = load_role_config("narrator")
    assert isinstance(cfg, dict)
    assert cfg["model_id"] == KIMI_MODEL_ID
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 600
    assert cfg["max_concurrency"] == 10


def test_make_llm_narrator_does_not_raise_keyerror():
    """`make_llm("narrator")` must instantiate without KeyError.

    Pure object construction — no Bedrock network calls.
    """
    from graph_wiki_core.roles import make_llm
    from langchain_aws import ChatBedrockConverse

    try:
        llm = make_llm("narrator")
    except KeyError as exc:  # pragma: no cover — guard for regression visibility
        pytest.fail(f"make_llm('narrator') raised KeyError: {exc!r}")

    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == KIMI_MODEL_ID
