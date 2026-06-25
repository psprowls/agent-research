"""Generic Bedrock / Vercel AI Gateway chat-model client.

Strategy choice (per Phase 1 RESEARCH A1):
    `ChatBedrockConverse` is a Pydantic v2 BaseModel with `extra='forbid'` and
    `__slots__`, so direct attribute reassignment (`llm.invoke = fn`) is
    rejected with ValueError. We therefore use the subclass-override strategy:
    a `_GuardedChatBedrockConverse(ChatBedrockConverse)` subclass overrides
    `invoke` to apply the try/except wrapper. The underlying parent invoke is
    exposed as `_original_invoke` so unit tests can stub it via `monkeypatch`.
"""

from __future__ import annotations

from typing import Any

import botocore.exceptions
import openai
from langchain_aws import ChatBedrockConverse
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from model_adapter.exceptions import BedrockAccessDenied, GatewayAccessDenied

_DEFAULT_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"


def _format_access_denied_message(model_id: str, original: Exception) -> str:
    return (
        "Bedrock access denied.\n"
        f"  Model ARN attempted: {model_id}\n"
        f"  IAM action required: bedrock:InvokeModel\n"
        "  Add an IAM policy with: "
        '{"Effect":"Allow","Action":"bedrock:InvokeModel",'
        '"Resource":"arn:aws:bedrock:*::foundation-model/*"}\n'
        f"  Original error: {original}"
    )


def _format_gateway_access_denied_message(base_url: str, original: Exception | None) -> str:
    return (
        "Vercel AI Gateway access denied.\n"
        f"  Gateway base URL: {base_url}\n"
        "  Set a valid bearer key in the AI_GATEWAY_API_KEY environment variable.\n"
        f"  Original error: {original}"
    )


def _normalize_content(response: Any) -> Any:
    """Collapse list-shaped message content to a plain `str`.

    Bedrock's Converse API returns `response.content` as a list of content
    blocks (text + reasoning) when the model emits multi-block output (e.g.
    gpt-oss-120b, minimax-m2.5 "thinking" models). Downstream consumers
    (synthesizer, ingestor) call `.strip()` / regex on `.content` and break
    on a list. The trigger is content SHAPE, not model id — so we detect via
    `isinstance(content, list)`, never a model-name check.

    Behavior:
      - Non-list `content` (bare object, str-content message) → return unchanged.
      - List content: bare `str` items and `{'type': 'text', ...}` dicts are
        joined into `response.content`; every other block (reasoning, etc.) is
        preserved on `response.additional_kwargs['reasoning']`.

    Decision LOCKED: reasoning blocks are preserved, never dropped.
    """
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return response

    text_parts: list[str] = []
    reasoning_blocks: list[Any] = []
    for block in content:
        if isinstance(block, str):
            text_parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        else:
            reasoning_blocks.append(block)

    response.content = "".join(text_parts)
    if reasoning_blocks:
        if response.additional_kwargs is None:
            response.additional_kwargs = {}
        response.additional_kwargs["reasoning"] = reasoning_blocks
    return response


class _GuardedChatBedrockConverse(ChatBedrockConverse):
    """ChatBedrockConverse subclass that translates AccessDeniedException and
    normalizes list-shaped content.

    `invoke()`/`ainvoke()` defer to the parent implementation via
    `_original_invoke`/`_original_ainvoke` so unit tests can monkeypatch the
    inner call without touching the network. Both paths translate
    AccessDeniedException → BedrockAccessDenied and pass successful responses
    through `_normalize_content`.
    """

    # Default ARN for error messages; overridden per-instance by `make_bedrock_llm`
    # via `object.__setattr__` (Pydantic v2 forbids normal field assignment).
    _model_id_for_errors: str = ""

    def _wrap_client_error(self, e: botocore.exceptions.ClientError) -> BedrockAccessDenied | None:
        """Translate an AccessDeniedException ClientError into a
        BedrockAccessDenied, or return None for any other error code (caller
        re-raises the original)."""
        if e.response.get("Error", {}).get("Code") == "AccessDeniedException":
            return BedrockAccessDenied(_format_access_denied_message(self._model_id_for_errors, e))
        return None

    def _original_invoke(self, *args: Any, **kwargs: Any) -> Any:
        return ChatBedrockConverse.invoke(self, *args, **kwargs)

    async def _original_ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await ChatBedrockConverse.ainvoke(self, *args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            response = self._original_invoke(*args, **kwargs)
        except botocore.exceptions.ClientError as e:
            wrapped = self._wrap_client_error(e)
            if wrapped is not None:
                raise wrapped from e
            raise
        return _normalize_content(response)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            response = await self._original_ainvoke(*args, **kwargs)
        except botocore.exceptions.ClientError as e:
            wrapped = self._wrap_client_error(e)
            if wrapped is not None:
                raise wrapped from e
            raise
        return _normalize_content(response)


class _GuardedChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass for the Vercel AI Gateway that translates gateway
    auth failures into GatewayAccessDenied and normalizes list-shaped content.

    Symmetric with `_GuardedChatBedrockConverse`: `invoke()`/`ainvoke()` defer
    to the parent via `_original_invoke`/`_original_ainvoke` (the monkeypatch
    seam), translate `openai.AuthenticationError` → GatewayAccessDenied, and
    pass successful responses through the shared `_normalize_content`. All other
    errors propagate raw (the gateway path is opt-in; debuggers see real errors).
    """

    # Bound per-instance by `make_gateway_llm` via `object.__setattr__` (Pydantic v2
    # forbids normal field assignment).
    _base_url_for_errors: str = ""

    def _original_invoke(self, *args: Any, **kwargs: Any) -> Any:
        return ChatOpenAI.invoke(self, *args, **kwargs)

    async def _original_ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await ChatOpenAI.ainvoke(self, *args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            response = self._original_invoke(*args, **kwargs)
        except openai.AuthenticationError as e:
            raise GatewayAccessDenied(_format_gateway_access_denied_message(self._base_url_for_errors, e)) from e
        return _normalize_content(response)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            response = await self._original_ainvoke(*args, **kwargs)
        except openai.AuthenticationError as e:
            raise GatewayAccessDenied(_format_gateway_access_denied_message(self._base_url_for_errors, e)) from e
        return _normalize_content(response)


def make_bedrock_llm(model_id: str, *, region: str = "us-east-1", max_tokens: int | None = None) -> BaseChatModel:
    """Build a guarded Bedrock Converse chat model from explicit config.

    The returned model translates AccessDeniedException -> BedrockAccessDenied
    and normalizes list-shaped content. No role concept -- callers that resolve
    a logical role to config live in graph_wiki_core.roles.
    """
    kwargs: dict[str, Any] = dict(model=model_id, region_name=region)
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    llm = _GuardedChatBedrockConverse(**kwargs)
    # Bind the ARN to the instance so error messages name the exact model.
    # object.__setattr__ bypasses Pydantic v2's extra='forbid' validator.
    object.__setattr__(llm, "_model_id_for_errors", model_id)
    return llm


def make_gateway_llm(model_id: str, *, max_tokens: int | None = None) -> BaseChatModel:
    """Build a guarded Vercel AI Gateway chat model from explicit config.

    Credentials come from the environment ONLY:
      AI_GATEWAY_API_KEY  (required; raises GatewayAccessDenied if unset)
      AI_GATEWAY_BASE_URL (optional; defaults to the Vercel gateway endpoint)
    """
    import os

    base_url = os.environ.get("AI_GATEWAY_BASE_URL", _DEFAULT_GATEWAY_BASE_URL)
    api_key = os.environ.get("AI_GATEWAY_API_KEY")
    if not api_key:
        raise GatewayAccessDenied(_format_gateway_access_denied_message(base_url, None))

    kwargs: dict[str, Any] = dict(model=model_id, api_key=api_key, base_url=base_url)
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    llm = _GuardedChatOpenAI(**kwargs)
    object.__setattr__(llm, "_base_url_for_errors", base_url)
    return llm
