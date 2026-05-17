"""Unit tests for model_adapter.loader.

Covers models.toml parsing and the BedrockAccessDenied error-wrapping path.
No real Bedrock calls — all network paths are mocked via a stub `_original_invoke`.
"""

from __future__ import annotations

import botocore.exceptions
import pytest

HAIKU_ARN = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET_ARN = "us.anthropic.claude-sonnet-4-6"


def test_make_llm_haiku_returns_chatbedrockconverse_with_haiku_arn():
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    llm = make_llm("haiku")
    assert isinstance(llm, ChatBedrockConverse)
    # ChatBedrockConverse (langchain-aws 1.4.6) stores the constructor `model`
    # argument as `model_id`. Tests must accept either to remain robust.
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == HAIKU_ARN


def test_make_llm_sonnet_returns_chatbedrockconverse_with_sonnet_arn():
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    llm = make_llm("sonnet")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == SONNET_ARN


def test_make_llm_unknown_role_raises_keyerror():
    from model_adapter.loader import make_llm

    with pytest.raises(KeyError):
        make_llm("does-not-exist")


def _build_client_error(code: str) -> botocore.exceptions.ClientError:
    return botocore.exceptions.ClientError(
        {"Error": {"Code": code, "Message": "denied"}},
        "InvokeModel",
    )


def test_invoke_wraps_access_denied_with_arn_and_iam_action(monkeypatch):
    """An AccessDeniedException from boto3 becomes a BedrockAccessDenied whose
    message names the attempted ARN AND the bedrock:InvokeModel action AND the
    foundation-model ARN pattern.
    """
    from model_adapter.exceptions import BedrockAccessDenied
    from model_adapter.loader import make_llm

    def raise_access_denied(*a, **kw):
        raise _build_client_error("AccessDeniedException")

    llm = make_llm("haiku")
    monkeypatch.setattr(llm, "_original_invoke", raise_access_denied)

    with pytest.raises(BedrockAccessDenied) as exc_info:
        llm.invoke("ping")

    msg = str(exc_info.value)
    assert HAIKU_ARN in msg
    assert "bedrock:InvokeModel" in msg
    assert "arn:aws:bedrock:*::foundation-model/*" in msg


def test_invoke_passes_through_non_access_denied_client_error(monkeypatch):
    """A ClientError whose Code is NOT AccessDeniedException must re-raise unchanged."""
    from model_adapter.loader import make_llm

    def raise_validation(*a, **kw):
        raise _build_client_error("ValidationException")

    llm = make_llm("haiku")
    monkeypatch.setattr(llm, "_original_invoke", raise_validation)

    with pytest.raises(botocore.exceptions.ClientError) as exc_info:
        llm.invoke("ping")
    assert exc_info.value.response["Error"]["Code"] == "ValidationException"


def test_invoke_returns_underlying_result_on_success(monkeypatch):
    """When the underlying invoke succeeds, the wrapped invoke returns the same value."""
    from model_adapter.loader import make_llm

    sentinel = object()
    llm = make_llm("haiku")
    monkeypatch.setattr(llm, "_original_invoke", lambda *a, **kw: sentinel)

    assert llm.invoke("ping") is sentinel


ALL_ROLES = ["haiku", "sonnet", "librarian", "scanner", "linter", "ingestor", "synthesizer", "judge_a", "judge_b"]


@pytest.mark.parametrize("role", ALL_ROLES)
def test_load_role_config_returns_dict_for_all_seven_roles(role):
    from model_adapter.loader import load_role_config

    cfg = load_role_config(role)
    assert isinstance(cfg, dict)
    assert "model_id" in cfg
    assert "region" in cfg
    assert "max_tokens" in cfg
    assert "max_concurrency" in cfg


def test_load_role_config_librarian_values():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("librarian")
    assert cfg["model_id"] == HAIKU_ARN
    assert cfg["max_tokens"] == 2048
    assert cfg["max_concurrency"] == 5


def test_load_role_config_synthesizer_limits():
    from model_adapter.loader import load_role_config

    cfg = load_role_config("synthesizer")
    assert cfg["max_tokens"] == 4096
    assert cfg["max_concurrency"] == 3


def test_load_role_config_unknown_role_raises_keyerror():
    from model_adapter.loader import load_role_config

    with pytest.raises(KeyError):
        load_role_config("nonexistent")


def test_make_llm_librarian_sets_max_tokens():
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    llm = make_llm("librarian")
    assert isinstance(llm, ChatBedrockConverse)
    assert getattr(llm, "max_tokens", None) == 2048


def test_make_llm_haiku_still_works_after_extension():
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    llm = make_llm("haiku")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == HAIKU_ARN
