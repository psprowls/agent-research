"""Unit tests for the Vercel AI Gateway path in model_adapter.loader.

No real gateway calls — all network paths are mocked via a stub
`_original_invoke`, mirroring tests/test_loader.py for the Bedrock path.
"""

from __future__ import annotations

import pytest


def test_gateway_access_denied_is_exported_exception():
    from model_adapter import GatewayAccessDenied

    assert issubclass(GatewayAccessDenied, Exception)


GATEWAY_MODEL = "openai/gpt-4o"
GATEWAY_URL = "https://ai-gateway.vercel.sh/v1"


def _make_guard():
    """Construct a _GuardedChatOpenAI directly with a dummy key/url, bypassing
    make_gateway_llm so the guard can be tested in isolation."""
    from model_adapter.loader import _GuardedChatOpenAI

    llm = _GuardedChatOpenAI(model=GATEWAY_MODEL, api_key="dummy", base_url=GATEWAY_URL)
    # make_gateway_llm binds these per-instance; set them here for the standalone guard.
    object.__setattr__(llm, "_base_url_for_errors", GATEWAY_URL)
    return llm


def _auth_error():
    """Build an openai.AuthenticationError. The openai 2.x signature requires a
    real httpx.Response (response=None blows up inside the SDK constructor)."""
    import httpx
    import openai

    resp = httpx.Response(401, request=httpx.Request("POST", GATEWAY_URL))
    return openai.AuthenticationError(message="invalid key", response=resp, body=None)


def test_guarded_chat_openai_subclasses_chatopenai():
    from langchain_openai import ChatOpenAI
    from model_adapter.loader import _GuardedChatOpenAI

    assert issubclass(_GuardedChatOpenAI, ChatOpenAI)


def test_invoke_wraps_authentication_error_naming_key_and_url(monkeypatch):
    from model_adapter import GatewayAccessDenied

    llm = _make_guard()

    def raise_auth(*a, **kw):
        raise _auth_error()

    monkeypatch.setattr(llm, "_original_invoke", raise_auth)

    with pytest.raises(GatewayAccessDenied) as exc_info:
        llm.invoke("ping")
    msg = str(exc_info.value)
    assert "AI_GATEWAY_API_KEY" in msg
    assert GATEWAY_URL in msg


def test_invoke_passes_through_non_auth_error(monkeypatch):
    llm = _make_guard()

    def raise_value(*a, **kw):
        raise ValueError("some other failure")

    monkeypatch.setattr(llm, "_original_invoke", raise_value)

    with pytest.raises(ValueError):
        llm.invoke("ping")


def test_invoke_normalizes_list_content_on_gateway_path(monkeypatch):
    from langchain_core.messages import AIMessage

    reasoning_block = {"type": "reasoning_content", "reasoning_content": {"text": "t"}}
    llm = _make_guard()
    monkeypatch.setattr(
        llm,
        "_original_invoke",
        lambda *a, **kw: AIMessage(
            content=[reasoning_block, {"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}]
        ),
    )

    result = llm.invoke("ping")
    assert result.content == "Hello world"
    assert result.additional_kwargs["reasoning"] == [reasoning_block]


async def test_ainvoke_wraps_authentication_error(monkeypatch):
    from model_adapter import GatewayAccessDenied

    llm = _make_guard()

    async def raise_auth(*a, **kw):
        raise _auth_error()

    monkeypatch.setattr(llm, "_original_ainvoke", raise_auth)

    with pytest.raises(GatewayAccessDenied):
        await llm.ainvoke("ping")
