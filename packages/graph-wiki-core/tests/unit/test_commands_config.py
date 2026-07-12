"""Round-trip tests for gw config core logic against a pinned tmp workspace."""

import json

import pytest
from graph_wiki_core.commands.config import (
    run_config_get,
    run_config_list,
    run_config_set,
    run_config_sync,
    run_config_unset,
)
from workspace_io import manifest
from workspace_io.projection import projection_path
from workspace_io.registry import EnvOnlyKeyError, InvalidValueError, UnknownKeyError


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    manifest.write(tmp_path / ".graph-wiki.yaml", {"version": 2, "initialized_at": "2026-07-04", "plugins": []})
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    return tmp_path


async def test_set_get_unset_roundtrip(workspace):
    await run_config_set("workflow.commit_strategy", "at-end")
    got = await run_config_get("workflow.commit_strategy")
    assert (got.value, got.origin) == ("at-end", "manifest")
    got = await run_config_unset("workflow.commit_strategy")
    assert (got.value, got.origin) == ("per-task", "default")
    got = await run_config_get("workflow.commit_strategy")
    assert (got.value, got.origin) == ("per-task", "default")


async def test_set_env_only_key_refused(workspace):
    with pytest.raises(EnvOnlyKeyError):
        await run_config_set("GRAPH_WIKI_ROUTING_GUARD", "0")


async def test_get_unknown_key_suggests(workspace):
    with pytest.raises(UnknownKeyError, match="did you mean"):
        await run_config_get("workflw.commit_strategy")


async def test_list_masks_secrets_and_expands_wildcards(workspace, monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "sk-secret")
    await run_config_set("roles.scanner.max_tokens", "512")
    await run_config_set("plugin.backend_overrides.scan", "bedrock")
    rows = await run_config_list()
    by_key = {r.key: r for r in rows}
    assert by_key["AI_GATEWAY_API_KEY"].value == "••••"
    assert by_key["roles.scanner.max_tokens"].value == 512
    # Trailing-wildcard shape (plugin.backend_overrides.*) expands too, once.
    assert [r.key for r in rows].count("plugin.backend_overrides.scan") == 1
    assert by_key["plugin.backend_overrides.scan"].value == "bedrock"
    assert by_key["workflow.commit_strategy"].origin == "default"


async def test_sync_regenerates_projection(workspace):
    projection_path(workspace).unlink(missing_ok=True)
    out = await run_config_sync()
    assert out == projection_path(workspace)
    assert json.loads(out.read_text(encoding="utf-8"))["version"] == 2


async def test_guidance_enabled_roundtrip(workspace):
    """The catalog entry and manifest.write() must agree — registry.set_key()
    raises if the written key does not survive the round-trip."""
    got = await run_config_get("guidance.enabled")
    assert (got.value, got.origin) == (False, "default")

    got = await run_config_set("guidance.enabled", "true")
    assert (got.value, got.origin) == (True, "manifest")
    assert manifest.read(workspace / ".graph-wiki.yaml")["guidance"] == {"enabled": True}

    got = await run_config_unset("guidance.enabled")
    assert (got.value, got.origin) == (False, "default")


async def test_guidance_enabled_set_false_is_equivalent_to_unset(workspace):
    """False is the entry default, so write() omits the block; the registry's
    persistence check tolerates that (persisted is None and value == default)."""
    got = await run_config_set("guidance.enabled", "false")
    assert (got.value, got.origin) == (False, "manifest")
    assert "guidance:" not in (workspace / ".graph-wiki.yaml").read_text(encoding="utf-8")


async def test_guidance_enabled_rejects_non_bool(workspace):
    with pytest.raises(InvalidValueError):
        await run_config_set("guidance.enabled", "sometimes")


async def test_guidance_enabled_lands_in_projection(workspace):
    await run_config_set("guidance.enabled", "true")
    payload = json.loads(projection_path(workspace).read_text(encoding="utf-8"))
    assert payload["guidance"] == {"enabled": True}
