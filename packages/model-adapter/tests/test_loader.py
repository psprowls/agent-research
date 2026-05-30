"""Unit tests for model_adapter.loader.

Covers models.toml parsing and the BedrockAccessDenied error-wrapping path.
No real Bedrock calls — all network paths are mocked via a stub `_original_invoke`.
"""

from __future__ import annotations

import botocore.exceptions
import pytest

HAIKU_ARN = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
# Phase 16 D-13 / MODEL-FU-01: synthesizer default after the Sweep-01 swap
# (sonnet-4-6 -> qwen3-32b for 11x cheaper at parity). Sourced from
# packages/model-adapter/src/model_adapter/models.toml [roles.synthesizer].
QWEN_SYNTHESIZER_ARN = "qwen.qwen3-32b-v1:0"


def test_make_llm_preflight_returns_chatbedrockconverse_with_haiku_arn():
    """The preflight role is the dedicated BED-01 ping handle; it currently
    points at the haiku-4.5 ARN as a cheap, fast smoke-test model."""
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    llm = make_llm("preflight")
    assert isinstance(llm, ChatBedrockConverse)
    # ChatBedrockConverse (langchain-aws 1.4.6) stores the constructor `model`
    # argument as `model_id`. Tests must accept either to remain robust.
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == HAIKU_ARN


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

    llm = make_llm("preflight")
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

    llm = make_llm("preflight")
    monkeypatch.setattr(llm, "_original_invoke", raise_validation)

    with pytest.raises(botocore.exceptions.ClientError) as exc_info:
        llm.invoke("ping")
    assert exc_info.value.response["Error"]["Code"] == "ValidationException"


def test_invoke_returns_underlying_result_on_success(monkeypatch):
    """When the underlying invoke succeeds, the wrapped invoke returns the same value."""
    from model_adapter.loader import make_llm

    sentinel = object()
    llm = make_llm("preflight")
    monkeypatch.setattr(llm, "_original_invoke", lambda *a, **kw: sentinel)

    assert llm.invoke("ping") is sentinel


ALL_ROLES = ["preflight", "librarian", "scanner", "linter", "ingestor", "synthesizer", "judge_a", "judge_b"]

# Phase 48 D-19 / PROPOSE-06: dedicated role for `graph propose-domains` so
# per-LLM-call cost is trackable under a distinct trace tag and the model can
# be tuned independently of `scanner`. Initial config mirrors scanner; v1.9
# eval will refine.
DOMAIN_PROPOSER_ROLE = "domain-proposer"
NOVA_LITE_ARN = "us.amazon.nova-lite-v1:0"


def test_domain_proposer_role():
    """Phase 48 D-19 + D-21: `[roles.domain-proposer]` is present with the
    expected config, `make_llm` instantiates successfully, and `model_override`
    swaps the model_id while preserving the rest of the role config.
    """
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import load_role_config, make_llm

    # D-19: raw role config matches the spec.
    cfg = load_role_config(DOMAIN_PROPOSER_ROLE)
    assert cfg["model_id"] == HAIKU_ARN
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 1024
    assert cfg["max_concurrency"] == 5

    # D-19: `make_llm("domain-proposer")` returns a working LLM handle.
    llm = make_llm(DOMAIN_PROPOSER_ROLE)
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == HAIKU_ARN

    # D-21: `model_override` swaps the model_id while keeping the role's
    # other config intact.
    llm_override = make_llm(DOMAIN_PROPOSER_ROLE, model_override=NOVA_LITE_ARN)
    assert isinstance(llm_override, ChatBedrockConverse)
    actual_override = (
        getattr(llm_override, "model_id", None) or getattr(llm_override, "model", None)
    )
    assert actual_override == NOVA_LITE_ARN


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
    # Phase 16 D-13 / MODEL-FU-01: lock the bundled synthesizer default to
    # the post-Sweep-01 Qwen choice. Drift trips this test loudly.
    assert cfg["model_id"] == "qwen.qwen3-32b-v1:0"
    assert cfg["model_id"] == QWEN_SYNTHESIZER_ARN  # constant + literal pinned together
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


# ---------------------------------------------------------------------------
# Phase 20 / WMC-02: workspace-override resolution path tests.
#
# The four tests below pin the resolution order in `make_llm`:
#   1. Workspace defines the role     → workspace wins.
#   2. Workspace silent on the role   → packaged models.toml wins (per-role).
#   3. workspace_io.resolve() raises  → caught; packaged models.toml wins.
#   4. Helper returns None (any path) → packaged models.toml wins.
#
# Tests 1, 2, 3 opt into the real `_workspace_role_override` helper via the
# `real_workspace_role_override` fixture (the autouse fixture stubs the helper
# to return None by default). Test 4 relies on the autouse stub directly.
# ---------------------------------------------------------------------------

# Non-default ARN used in workspace-override tests so workspace-wins vs.
# packaged-fallback paths produce distinguishable results.
WORKSPACE_OVERRIDE_ARN = "qwen.qwen3-32b-v1:0"


def _write_synthetic_workspace(tmp_path, roles):
    """Build a minimal workspace dir with `.graph-wiki.yaml` carrying the given roles."""
    from workspace_io.manifest import write as manifest_write

    workspace = tmp_path / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    manifest_write(
        workspace / ".graph-wiki.yaml",
        {
            "version": 2,
            "initialized_at": "2026-05-19",
            "plugins": [
                {
                    "name": "graph-wiki-agent",
                    "installed_version": "0.7.0",
                    "applied_version": "0.7.0",
                    "roles": roles,
                }
            ],
        },
    )
    return workspace


def test_make_llm_uses_workspace_role_when_present(
    tmp_path, monkeypatch, real_workspace_role_override
):
    """Workspace-defined role config wins over packaged defaults."""
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    workspace = _write_synthetic_workspace(
        tmp_path,
        [
            {
                "name": "librarian",
                "model_id": WORKSPACE_OVERRIDE_ARN,
                "region": "us-east-1",
                "max_tokens": 1024,
                "max_concurrency": 2,
            },
        ],
    )
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("librarian")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == WORKSPACE_OVERRIDE_ARN


def test_make_llm_falls_back_to_packaged_when_role_absent_in_workspace(
    tmp_path, monkeypatch, real_workspace_role_override
):
    """Per-role fallback: workspace silent on a role → packaged models.toml wins."""
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    workspace = _write_synthetic_workspace(
        tmp_path,
        [
            {
                "name": "librarian",
                "model_id": WORKSPACE_OVERRIDE_ARN,
                "region": "us-east-1",
                "max_tokens": 1024,
                "max_concurrency": 2,
            },
        ],
    )
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("scanner")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    # Scanner default per models.toml [roles.scanner]
    assert actual == HAIKU_ARN


def test_make_llm_falls_back_to_packaged_when_resolve_raises(
    monkeypatch, real_workspace_role_override
):
    """Production path: `workspace_io.resolve()` raises RuntimeError →
    `_workspace_role_override` catches it → `make_llm` falls back to packaged
    `models.toml`. Drives the real try/except, not a stub (BLOCKER fix from
    plan-check).
    """
    from model_adapter.loader import make_llm

    def _raise(*args, **kwargs):
        raise RuntimeError("synthetic: no manifest reachable")

    # Patch BOTH the source module attribute and the re-export so the
    # function-scoped `from workspace_io import ... resolve` inside the
    # helper picks up the patched callable. `workspace_io` re-exports
    # `resolve` from `workspace_io.config` via `__init__.py`.
    import workspace_io
    import workspace_io.config as _wsio_config

    monkeypatch.setattr(_wsio_config, "resolve", _raise)
    monkeypatch.setattr(workspace_io, "resolve", _raise)

    llm = make_llm("preflight")
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    # Preflight default per models.toml [roles.preflight]
    assert actual == HAIKU_ARN


def test_make_llm_falls_back_when_helper_returns_none(monkeypatch):
    """Branch coverage: when `_workspace_role_override` returns None (for any
    reason — no workspace, role absent, ImportError), `make_llm` reads packaged
    defaults. NOTE: this test stubs the helper and does NOT exercise the
    `workspace_io.resolve()` raise path — see
    `test_make_llm_falls_back_to_packaged_when_resolve_raises` for that
    coverage.
    """
    from model_adapter.loader import make_llm

    # The autouse fixture has already stubbed `_workspace_role_override` to
    # `lambda role: None` — so this test simply confirms the default branch
    # behavior of `make_llm` under that stub.
    llm = make_llm("preflight")
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == HAIKU_ARN

