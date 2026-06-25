"""Generic constructor tests — make_bedrock_llm / make_gateway_llm."""

from __future__ import annotations

import pytest
from model_adapter import GatewayAccessDenied, make_bedrock_llm, make_gateway_llm
from model_adapter.loader import _GuardedChatBedrockConverse, _GuardedChatOpenAI


def test_make_bedrock_llm_binds_model_id_and_region() -> None:
    llm = make_bedrock_llm("anthropic.fake-model", region="us-west-2", max_tokens=64)
    assert isinstance(llm, _GuardedChatBedrockConverse)
    assert llm._model_id_for_errors == "anthropic.fake-model"
    assert llm.region_name == "us-west-2"
    assert llm.max_tokens == 64


def test_make_bedrock_llm_defaults() -> None:
    llm = make_bedrock_llm("m")
    assert llm.region_name == "us-east-1"


def test_make_gateway_llm_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    with pytest.raises(GatewayAccessDenied):
        make_gateway_llm("some/model")


def test_make_gateway_llm_builds_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    llm = make_gateway_llm("some/model", max_tokens=128)
    assert isinstance(llm, _GuardedChatOpenAI)
    assert llm._base_url_for_errors  # set from default gateway URL
    assert llm.model_name == "some/model"
    assert llm.max_tokens == 128
