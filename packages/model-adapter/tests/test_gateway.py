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
    make_llm so the guard can be tested in isolation."""
    from model_adapter.loader import _GuardedChatOpenAI

    llm = _GuardedChatOpenAI(model=GATEWAY_MODEL, api_key="dummy", base_url=GATEWAY_URL)
    # make_llm binds these per-instance; set them here for the standalone guard.
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


# ---------------------------------------------------------------------------
# Task 3: backend-aware make_llm + _make_gateway_llm.
#
# The tests below pin the backend branch in make_llm:
#   - no `backend` key       → Bedrock guard (regression).
#   - `backend = "vercel"`   → gateway guard built from env-only credentials.
# ---------------------------------------------------------------------------


def _set_gateway_env(monkeypatch, key="test-key", base_url=None):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", key)
    if base_url is not None:
        monkeypatch.setenv("AI_GATEWAY_BASE_URL", base_url)
    else:
        monkeypatch.delenv("AI_GATEWAY_BASE_URL", raising=False)


def _write_vercel_workspace(tmp_path, role_name, model_id):
    from workspace_io.manifest import write as manifest_write

    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    manifest_write(
        workspace / ".graph-wiki.yaml",
        {
            "version": 2,
            "initialized_at": "2026-06-24",
            "plugins": [
                {
                    "name": "graph-wiki-agent",
                    "installed_version": "0.7.0",
                    "applied_version": "0.7.0",
                    "roles": [
                        {
                            "name": role_name,
                            "backend": "vercel",
                            "model_id": model_id,
                            "max_tokens": 2048,
                            "max_concurrency": 5,
                        }
                    ],
                }
            ],
        },
    )
    return workspace


def test_default_backend_builds_bedrock_guard():
    """Regression: a role with no backend key is unchanged (Bedrock)."""
    from model_adapter.loader import _GuardedChatBedrockConverse, make_llm

    llm = make_llm("preflight")
    assert isinstance(llm, _GuardedChatBedrockConverse)


def test_vercel_backend_builds_gateway_guard_with_config(tmp_path, monkeypatch, real_workspace_role_override):
    from model_adapter.loader import _GuardedChatOpenAI, make_llm

    _set_gateway_env(monkeypatch)
    workspace = _write_vercel_workspace(tmp_path, "librarian", GATEWAY_MODEL)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("librarian")
    assert isinstance(llm, _GuardedChatOpenAI)
    actual_model = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    assert actual_model == GATEWAY_MODEL
    assert getattr(llm, "max_tokens", None) == 2048
    assert str(getattr(llm, "openai_api_base", "")) == "https://ai-gateway.vercel.sh/v1"


def test_vercel_base_url_override(tmp_path, monkeypatch, real_workspace_role_override):
    from model_adapter.loader import make_llm

    custom = "https://gw.example.test/v1"
    _set_gateway_env(monkeypatch, base_url=custom)
    workspace = _write_vercel_workspace(tmp_path, "librarian", GATEWAY_MODEL)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("librarian")
    assert str(getattr(llm, "openai_api_base", "")) == custom


def test_vercel_missing_key_raises(tmp_path, monkeypatch, real_workspace_role_override):
    from model_adapter import GatewayAccessDenied
    from model_adapter.loader import make_llm

    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    workspace = _write_vercel_workspace(tmp_path, "librarian", GATEWAY_MODEL)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    with pytest.raises(GatewayAccessDenied) as exc_info:
        make_llm("librarian")
    assert "AI_GATEWAY_API_KEY" in str(exc_info.value)


def test_vercel_model_override(tmp_path, monkeypatch, real_workspace_role_override):
    from model_adapter.loader import make_llm

    _set_gateway_env(monkeypatch)
    workspace = _write_vercel_workspace(tmp_path, "librarian", GATEWAY_MODEL)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("librarian", model_override="anthropic/claude-sonnet-4")
    actual_model = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    assert actual_model == "anthropic/claude-sonnet-4"
