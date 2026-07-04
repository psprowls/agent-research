"""Role resolution tests: make_llm / load_role_config / workspace overrides / backend selection.

Moved from model-adapter as part of Task 5 decoupling. These tests exercise the
role concept (models.toml parsing, workspace override layer, backend selection)
which now lives entirely in graph_wiki_core.roles.
"""

from __future__ import annotations

import pytest

KIMI_MODEL_ID = "moonshotai.kimi-k2.5"
# 2026-05-30: preflight moved from Haiku to qwen3-32b (Haiku quota exhausted).
PREFLIGHT_ARN = "qwen.qwen3-32b-v1:0"
# Non-default ARN used in workspace-override tests so workspace-wins vs.
# packaged-fallback paths produce distinguishable results.
WORKSPACE_OVERRIDE_ARN = "qwen.qwen3-32b-v1:0"
NOVA_LITE_ARN = "us.amazon.nova-lite-v1:0"
GATEWAY_MODEL = "openai/gpt-4o"
GATEWAY_URL = "https://ai-gateway.vercel.sh/v1"


# ---------------------------------------------------------------------------
# models.toml parsing
# ---------------------------------------------------------------------------

ALL_ROLES = [
    "preflight",
    "librarian",
    "scanner",
    "linter",
    "ingestor",
    "package_reader",
    "synthesizer",
    "judge_a",
    "judge_b",
    "query_orchestrator",
]

DOMAIN_PROPOSER_ROLE = "domain_proposer"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_load_role_config_returns_dict_for_core_roles(role):
    from graph_wiki_core.roles import load_role_config

    cfg = load_role_config(role)
    assert isinstance(cfg, dict)
    assert "model_id" in cfg
    assert "region" in cfg
    assert "max_tokens" in cfg
    assert "max_concurrency" in cfg


def test_load_role_config_librarian_values():
    from graph_wiki_core.roles import load_role_config

    # 2026-05-30: librarian default changed to kimi-k2.5 (Haiku purged for quota exhaustion).
    cfg = load_role_config("librarian")
    assert cfg["model_id"] == "moonshotai.kimi-k2.5"
    assert cfg["max_tokens"] == 2048
    assert cfg["max_concurrency"] == 5


def test_ingest_proposal_roles_use_kimi_k25() -> None:
    from graph_wiki_core.roles import load_role_config

    expected = {
        "ingestor": 4096,
        "proposal_reasoner": 4096,
        "extractor": 2048,
    }
    for role, max_tokens in expected.items():
        cfg = load_role_config(role)
        assert cfg["model_id"] == "moonshotai.kimi-k2.5"
        assert cfg["region"] == "us-east-1"
        assert cfg["max_tokens"] == max_tokens
        assert "moonshotai.kimi-k2.5" in cfg["sweep_candidates"]


def test_query_orchestrator_role_uses_kimi_k25() -> None:
    from graph_wiki_core.roles import load_role_config, make_llm
    from langchain_aws import ChatBedrockConverse

    cfg = load_role_config("query_orchestrator")
    assert cfg["model_id"] == "moonshotai.kimi-k2.5"
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 4096
    assert cfg["max_concurrency"] == 1
    assert cfg["sweep_candidates"] == ["moonshotai.kimi-k2.5"]

    llm = make_llm("query_orchestrator")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == "moonshotai.kimi-k2.5"


def test_load_role_config_synthesizer_limits():
    from graph_wiki_core.roles import load_role_config

    cfg = load_role_config("synthesizer")
    # Synthesizer default after the post-Haiku-purge session (2026-05-30).
    assert cfg["model_id"] == "moonshotai.kimi-k2.5"
    assert cfg["max_tokens"] == 4096
    assert cfg["max_concurrency"] == 3


def test_drift_propagator_role_is_configured():
    """[M4 §4] The cross-page drift judge has a cheap-tier role with candidates."""
    from graph_wiki_core.roles import load_role_config

    cfg = load_role_config("drift_propagator")
    assert cfg["model_id"]
    assert cfg["max_concurrency"] >= 1
    assert cfg.get("sweep_candidates")


@pytest.mark.parametrize("role", ["skill_planner", "skill_synthesizer"])
def test_skill_roles_are_registered(role):
    from graph_wiki_core.roles import load_role_config

    cfg = load_role_config(role)
    assert cfg["model_id"]
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] > 0
    assert cfg["max_concurrency"] >= 1


# ---------------------------------------------------------------------------
# make_llm — basic construction + domain_proposer
# ---------------------------------------------------------------------------


def test_make_llm_preflight_returns_chatbedrockconverse_with_qwen3_arn():
    """The preflight role points at qwen3-32b as a cheap, fast smoke-test model."""
    from graph_wiki_core.roles import make_llm
    from langchain_aws import ChatBedrockConverse

    llm = make_llm("preflight")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == PREFLIGHT_ARN


def test_make_llm_unknown_role_raises_keyerror():
    from graph_wiki_core.roles import make_llm

    with pytest.raises(KeyError):
        make_llm("does-not-exist")


def test_domain_proposer_role():
    """Phase 48 D-19 + D-21: `[roles.domain_proposer]` is present with the
    expected config, `make_llm` instantiates successfully, and `model_override`
    swaps the model_id while preserving the rest of the role config.
    """
    from graph_wiki_core.roles import load_role_config, make_llm
    from langchain_aws import ChatBedrockConverse

    # D-19: raw role config matches the post-Haiku-purge spec.
    cfg = load_role_config(DOMAIN_PROPOSER_ROLE)
    assert cfg["model_id"] == KIMI_MODEL_ID
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 1024
    assert cfg["max_concurrency"] == 5

    # D-19: `make_llm("domain_proposer")` returns a working LLM handle.
    llm = make_llm(DOMAIN_PROPOSER_ROLE)
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == KIMI_MODEL_ID

    # D-21: `model_override` swaps the model_id while keeping the role's
    # other config intact.
    llm_override = make_llm(DOMAIN_PROPOSER_ROLE, model_override=NOVA_LITE_ARN)
    assert isinstance(llm_override, ChatBedrockConverse)
    actual_override = getattr(llm_override, "model_id", None) or getattr(llm_override, "model", None)
    assert actual_override == NOVA_LITE_ARN


def test_make_llm_librarian_sets_max_tokens():
    from graph_wiki_core.roles import make_llm
    from langchain_aws import ChatBedrockConverse

    llm = make_llm("librarian")
    assert isinstance(llm, ChatBedrockConverse)
    assert getattr(llm, "max_tokens", None) == 2048


# ---------------------------------------------------------------------------
# Workspace-override resolution path tests (Phase 20 / WMC-02).
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


def _write_synthetic_workspace(tmp_path, roles):
    """Build a minimal workspace dir with `.graph-wiki.yaml` carrying the given
    flattened top-level `roles:` mapping ({role_name: {field: value}})."""
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
                }
            ],
            "roles": roles,
        },
    )
    return workspace


def _write_vercel_workspace(tmp_path, role_name, model_id):
    return _write_synthetic_workspace(
        tmp_path,
        {
            role_name: {
                "backend": "vercel",
                "model_id": model_id,
                "max_tokens": 2048,
                "max_concurrency": 5,
            }
        },
    )


def test_make_llm_uses_workspace_role_when_present(tmp_path, monkeypatch, real_workspace_role_override):
    """Workspace-defined role config wins over packaged defaults."""
    from graph_wiki_core.roles import make_llm
    from langchain_aws import ChatBedrockConverse

    workspace = _write_synthetic_workspace(
        tmp_path,
        {
            "librarian": {
                "model_id": WORKSPACE_OVERRIDE_ARN,
                "region": "us-east-1",
                "max_tokens": 1024,
                "max_concurrency": 2,
            },
        },
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
    from graph_wiki_core.roles import make_llm
    from langchain_aws import ChatBedrockConverse

    workspace = _write_synthetic_workspace(
        tmp_path,
        {
            "librarian": {
                "model_id": WORKSPACE_OVERRIDE_ARN,
                "region": "us-east-1",
                "max_tokens": 1024,
                "max_concurrency": 2,
            },
        },
    )
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("scanner")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    # Scanner default per models.toml [roles.scanner] (2026-05-30: kimi-k2.5 after Haiku purge)
    assert actual == "moonshotai.kimi-k2.5"


def test_make_llm_falls_back_to_packaged_when_resolve_raises(monkeypatch, real_workspace_role_override):
    """Production path: `workspace_io.resolve()` raises RuntimeError →
    `_workspace_role_override` catches it → `make_llm` falls back to packaged
    `models.toml`. Drives the real try/except, not a stub (BLOCKER fix from
    plan-check).
    """
    from graph_wiki_core.roles import make_llm

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
    # Preflight default per models.toml [roles.preflight] (2026-05-30: qwen3-32b after Haiku purge)
    assert actual == PREFLIGHT_ARN


def test_make_llm_falls_back_when_helper_returns_none(monkeypatch):
    """Branch coverage: when `_workspace_role_override` returns None (for any
    reason — no workspace, role absent, ImportError), `make_llm` reads packaged
    defaults. NOTE: this test stubs the helper and does NOT exercise the
    `workspace_io.resolve()` raise path — see
    `test_make_llm_falls_back_to_packaged_when_resolve_raises` for that coverage.
    """
    from graph_wiki_core.roles import make_llm

    # The autouse fixture has already stubbed `_workspace_role_override` to
    # `lambda role: None` — so this test simply confirms the default branch
    # behavior of `make_llm` under that stub.
    llm = make_llm("preflight")
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    # Preflight default per models.toml [roles.preflight] (2026-05-30: qwen3-32b after Haiku purge)
    assert actual == PREFLIGHT_ARN


# ---------------------------------------------------------------------------
# Backend selection: default Bedrock + Vercel via workspace override
# ---------------------------------------------------------------------------


def test_default_backend_builds_bedrock_guard():
    """Regression: a role with no backend key is unchanged (Bedrock)."""
    from graph_wiki_core.roles import make_llm
    from model_adapter.loader import _GuardedChatBedrockConverse

    llm = make_llm("preflight")
    assert isinstance(llm, _GuardedChatBedrockConverse)


def _set_gateway_env(monkeypatch, key="test-key", base_url=None):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", key)
    if base_url is not None:
        monkeypatch.setenv("AI_GATEWAY_BASE_URL", base_url)
    else:
        monkeypatch.delenv("AI_GATEWAY_BASE_URL", raising=False)


def test_vercel_backend_builds_gateway_guard_with_config(tmp_path, monkeypatch, real_workspace_role_override):
    from graph_wiki_core.roles import make_llm
    from model_adapter.loader import _GuardedChatOpenAI

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
    from graph_wiki_core.roles import make_llm

    custom = "https://gw.example.test/v1"
    _set_gateway_env(monkeypatch, base_url=custom)
    workspace = _write_vercel_workspace(tmp_path, "librarian", GATEWAY_MODEL)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("librarian")
    assert str(getattr(llm, "openai_api_base", "")) == custom


def test_vercel_missing_key_raises(tmp_path, monkeypatch, real_workspace_role_override):
    from graph_wiki_core.roles import make_llm
    from model_adapter import GatewayAccessDenied

    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    workspace = _write_vercel_workspace(tmp_path, "librarian", GATEWAY_MODEL)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    with pytest.raises(GatewayAccessDenied) as exc_info:
        make_llm("librarian")
    assert "AI_GATEWAY_API_KEY" in str(exc_info.value)


def test_vercel_model_override(tmp_path, monkeypatch, real_workspace_role_override):
    from graph_wiki_core.roles import make_llm

    _set_gateway_env(monkeypatch)
    workspace = _write_vercel_workspace(tmp_path, "librarian", GATEWAY_MODEL)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("librarian", model_override="anthropic/claude-sonnet-4")
    actual_model = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    assert actual_model == "anthropic/claude-sonnet-4"


# ---------------------------------------------------------------------------
# Partial workspace override merge (bug fix: a workspace override carrying
# only a subset of {model_id, region, max_tokens, max_concurrency, backend}
# used to REPLACE the whole packaged role_cfg, so `role_cfg["model_id"]`
# raised a bare KeyError for any role-scoped `gw config set`. make_llm now
# merges the workspace override onto the packaged models.toml entry field by
# field: workspace wins per-field, packaged fills in everything else.
# ---------------------------------------------------------------------------


def test_make_llm_partial_workspace_override_merges_onto_packaged_defaults(
    tmp_path, monkeypatch, real_workspace_role_override
):
    """`gw config set roles.scanner.max_tokens 8192` (the reported repro) must
    not brick make_llm: scanner keeps its packaged model_id/region/etc. and
    only max_tokens changes.
    """
    from graph_wiki_core.roles import load_role_config, make_llm
    from langchain_aws import ChatBedrockConverse

    packaged = load_role_config("scanner")
    workspace = _write_synthetic_workspace(tmp_path, {"scanner": {"max_tokens": 8192}})
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("scanner")
    assert isinstance(llm, ChatBedrockConverse)
    actual_model = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual_model == packaged["model_id"]
    assert llm.region_name == packaged["region"]
    assert getattr(llm, "max_tokens", None) == 8192


def test_make_llm_full_workspace_override_wins_every_field(tmp_path, monkeypatch, real_workspace_role_override):
    """A fully-specified workspace override still wins on every field it sets
    (no packaged field leaks through when the workspace sets all of them)."""
    from graph_wiki_core.roles import make_llm
    from langchain_aws import ChatBedrockConverse

    workspace = _write_synthetic_workspace(
        tmp_path,
        {
            "scanner": {
                "model_id": WORKSPACE_OVERRIDE_ARN,
                "region": "us-west-2",
                "max_tokens": 111,
                "max_concurrency": 1,
            },
        },
    )
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("scanner")
    assert isinstance(llm, ChatBedrockConverse)
    actual_model = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual_model == WORKSPACE_OVERRIDE_ARN
    assert llm.region_name == "us-west-2"
    assert getattr(llm, "max_tokens", None) == 111


def test_make_llm_workspace_only_role_absent_from_packaged_models_toml(
    tmp_path, monkeypatch, real_workspace_role_override
):
    """A role with no packaged models.toml entry can still be fully defined by
    the workspace alone -- `roles.*` is an open wildcard in the config catalog
    (config_catalog.py), so `gw config set roles.<new-role>.model_id ...` is a
    legal way to introduce a role that only exists at the workspace layer.
    """
    from graph_wiki_core.roles import load_role_config, make_llm
    from langchain_aws import ChatBedrockConverse

    with pytest.raises(KeyError):
        load_role_config("workspace_only_role")

    workspace = _write_synthetic_workspace(
        tmp_path,
        {
            "workspace_only_role": {
                "model_id": WORKSPACE_OVERRIDE_ARN,
                "region": "us-west-2",
                "max_tokens": 256,
                "max_concurrency": 2,
            },
        },
    )
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    llm = make_llm("workspace_only_role")
    assert isinstance(llm, ChatBedrockConverse)
    actual_model = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual_model == WORKSPACE_OVERRIDE_ARN
    assert llm.region_name == "us-west-2"
    assert getattr(llm, "max_tokens", None) == 256


def test_make_llm_workspace_only_role_missing_model_id_raises_actionable_keyerror(
    tmp_path, monkeypatch, real_workspace_role_override
):
    """When a role has no packaged entry AND the workspace override omits
    model_id, make_llm still raises KeyError (unchanged failure mode) but with
    an actionable message instead of the bare `'model_id'` from a raw dict
    lookup.
    """
    from graph_wiki_core.roles import make_llm

    workspace = _write_synthetic_workspace(tmp_path, {"workspace_only_role": {"max_tokens": 256}})
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    with pytest.raises(KeyError, match="model_id"):
        make_llm("workspace_only_role")
