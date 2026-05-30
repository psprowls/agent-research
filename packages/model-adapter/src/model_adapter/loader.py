"""Bedrock model loader.

Reads role-keyed model configuration with workspace-aware override layer.

Resolution order for `make_llm(role)`:
  1. Workspace manifest (`<workspace>/.graph-wiki.yaml` `plugins[].roles[]` for
     plugin "graph-wiki-agent") if a role entry with `name == role` is present.
  2. Packaged `model_adapter/models.toml` `[roles.<role>]` (per-role fallback).

Strategy choice (per Phase 1 RESEARCH A1):
    `ChatBedrockConverse` is a Pydantic v2 BaseModel with `extra='forbid'` and
    `__slots__`, so direct attribute reassignment (`llm.invoke = fn`) is
    rejected with ValueError. We therefore use the subclass-override strategy:
    a `_GuardedChatBedrockConverse(ChatBedrockConverse)` subclass overrides
    `invoke` to apply the try/except wrapper. The underlying parent invoke is
    exposed as `_original_invoke` so unit tests can stub it via `monkeypatch`.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from typing import Any

import botocore.exceptions
from langchain_aws import ChatBedrockConverse

from model_adapter.exceptions import BedrockAccessDenied


def _load_models_config() -> dict:
    # models.toml is bundled inside the model_adapter package
    # (src/model_adapter/models.toml) so it is accessible under any
    # install mode (editable, wheel, or zip).
    with resources.files("model_adapter").joinpath("models.toml").open("rb") as f:
        return tomllib.load(f)


def _workspace_role_override(role: str) -> dict | None:
    """Return the workspace-defined role dict for `role`, or None.

    Resolution order:
      1. Locate the workspace via `workspace_io.resolve()` — raises
         RuntimeError when no `.graph-wiki.yaml` is reachable.
      2. Read the role list via `workspace_io.read_roles(
         "graph-wiki-agent", workspace/".graph-wiki.yaml")`.
      3. Return the first role dict whose `name` matches.
      4. Return None on any failure (no workspace, plugin absent, role
         absent, ImportError in restricted test contexts).
    """
    try:
        from workspace_io import read_roles, resolve
    except ImportError:
        return None
    try:
        cfg = resolve()
    except RuntimeError:
        return None
    manifest_path = cfg.workspace / ".graph-wiki.yaml"
    for entry in read_roles("graph-wiki-agent", manifest_path):
        if entry.get("name") == role:
            return entry
    return None


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

    # Default ARN for error messages; overridden per-instance by `make_llm`
    # via `object.__setattr__` (Pydantic v2 forbids normal field assignment).
    _model_id_for_errors: str = ""

    def _wrap_client_error(self, e: botocore.exceptions.ClientError) -> BedrockAccessDenied | None:
        """Translate an AccessDeniedException ClientError into a
        BedrockAccessDenied, or return None for any other error code (caller
        re-raises the original)."""
        if e.response.get("Error", {}).get("Code") == "AccessDeniedException":
            return BedrockAccessDenied(
                _format_access_denied_message(self._model_id_for_errors, e)
            )
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


def make_llm(role: str, *, model_override: str | None = None) -> ChatBedrockConverse:
    """Return a ChatBedrockConverse configured for the given role.

    Resolution order:
      1. Workspace manifest (`<workspace>/.graph-wiki.yaml`
         `plugins[].roles[]` for plugin "graph-wiki-agent") if a role
         entry with `name == role` is present.
      2. Packaged `model_adapter/models.toml` `[roles.<role>]`.

    Args:
        role: Role name (e.g. ``"librarian"``, ``"domain-proposer"``).
        model_override: Optional Bedrock model id (ARN or short form) that
            replaces the resolved role's ``model_id``. Other role config
            (region, max_tokens, etc.) is preserved. Phase 48 D-21 wires
            the ``--model`` CLI flag through this parameter.

    Raises:
        KeyError: when `role` is not present in either source.
    """
    workspace_cfg = _workspace_role_override(role)
    if workspace_cfg is not None:
        role_cfg = workspace_cfg
    else:
        config = _load_models_config()
        role_cfg = config["roles"][role]  # KeyError if absent

    model_id = model_override if model_override is not None else role_cfg["model_id"]
    region = role_cfg.get("region", "us-east-1")

    kwargs: dict[str, Any] = dict(model=model_id, region_name=region)
    max_tokens = role_cfg.get("max_tokens")
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    llm = _GuardedChatBedrockConverse(**kwargs)
    # Bind the ARN to the instance so error messages name the exact model.
    # `object.__setattr__` bypasses Pydantic v2's `extra='forbid'` validator
    # that would otherwise reject the assignment.
    object.__setattr__(llm, "_model_id_for_errors", model_id)
    return llm


def load_role_config(role: str) -> dict:
    """Return the raw config dict for a role from models.toml.

    Note: this accessor reads packaged defaults only. Workspace overrides
    via `<workspace>/.graph-wiki.yaml` apply to `make_llm()` only, not to
    this raw role-config accessor (eval-harness consumers depend on the
    packaged shape including `sweep_candidates`).

    Raises:
        KeyError: when `role` is not present in `models.toml`.

    Returns a dict with all keys present for the role in models.toml:
        model_id, region, max_tokens, max_concurrency
    """
    config = _load_models_config()
    return config["roles"][role]  # KeyError if role absent — intentional
