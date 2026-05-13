"""Bedrock model loader.

Reads role-keyed model configuration from `models.toml` and returns a
`ChatBedrockConverse` whose `invoke` wraps boto3 AccessDeniedException
into the actionable `BedrockAccessDenied` exception type.

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
    # models.toml is bundled inside the model_adapter package (src/model_adapter/models.toml)
    # so it is accessible under any install mode (editable, wheel, or zip).
    with resources.files("model_adapter").joinpath("models.toml").open("rb") as f:
        return tomllib.load(f)


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


class _GuardedChatBedrockConverse(ChatBedrockConverse):
    """ChatBedrockConverse subclass that translates AccessDeniedException.

    `invoke()` defers to the parent implementation via `_original_invoke` so
    unit tests can monkeypatch the inner call without touching the network.
    """

    # Default ARN for error messages; overridden per-instance by `make_llm`
    # via `object.__setattr__` (Pydantic v2 forbids normal field assignment).
    _model_id_for_errors: str = ""

    def _original_invoke(self, *args: Any, **kwargs: Any) -> Any:
        return ChatBedrockConverse.invoke(self, *args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._original_invoke(*args, **kwargs)
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "AccessDeniedException":
                raise BedrockAccessDenied(_format_access_denied_message(self._model_id_for_errors, e)) from e
            raise


def make_llm(role: str) -> ChatBedrockConverse:
    """Return a ChatBedrockConverse configured for the given role.

    Reads `models.toml`, instantiates a guarded subclass that wraps
    `AccessDeniedException` from boto3 into `BedrockAccessDenied` with a
    message naming the attempted model ARN and the `bedrock:InvokeModel`
    IAM action.

    Raises:
        KeyError: when `role` is not present in `models.toml`.
    """
    config = _load_models_config()
    role_cfg = config["roles"][role]
    model_id = role_cfg["model_id"]
    region = role_cfg.get("region", "us-east-1")

    llm = _GuardedChatBedrockConverse(model=model_id, region_name=region)
    # Bind the ARN to the instance so error messages name the exact model.
    # `object.__setattr__` bypasses Pydantic v2's `extra='forbid'` validator
    # that would otherwise reject the assignment.
    object.__setattr__(llm, "_model_id_for_errors", model_id)
    return llm
