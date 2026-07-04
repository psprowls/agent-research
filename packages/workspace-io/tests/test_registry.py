"""Tests for workspace_io.registry — entry matching, precedence, validated writes."""

import json

import pytest
from workspace_io import manifest
from workspace_io.projection import projection_path
from workspace_io.registry import (
    ConfigEntry,
    EnvOnlyKeyError,
    InvalidValueError,
    LinkFileKeyError,
    ProvenanceKeyError,
    SecretKeyError,
    UnknownKeyError,
    resolve_key,
    set_key,
    unset_key,
)

CATALOG = (
    ConfigEntry(key="topic", type="str", default=None, description="Wiki display name."),
    ConfigEntry(
        key="workflow.commit_strategy",
        type="str",
        default="per-task",
        allowed=("per-task", "at-end"),
        description="Commit cadence.",
    ),
    ConfigEntry(key="state_gate.enabled", type="bool", default=True, description="Gate on/off."),
    ConfigEntry(key="state_gate.branches", type="list[str]", default=["main"], description="Gated branches."),
    ConfigEntry(key="roles.*.max_tokens", type="int", default=None, description="Role token cap."),
    ConfigEntry(
        key="GRAPH_WIKI_LOCK_TIMEOUT_MS",
        type="int",
        default=30_000,
        kind="env-only",
        env_var="GRAPH_WIKI_LOCK_TIMEOUT_MS",
        description="Graph DB lock timeout.",
    ),
    ConfigEntry(
        key="AI_GATEWAY_API_KEY",
        type="str",
        default=None,
        kind="env-only",
        env_var="AI_GATEWAY_API_KEY",
        secret=True,
        description="Gateway credential.",
    ),
)


@pytest.fixture
def workspace(tmp_path):
    manifest.write(tmp_path / ".graph-wiki.yaml", {"version": 2, "initialized_at": "2026-07-04", "plugins": []})
    return tmp_path


def test_resolve_default_origin(workspace):
    r = resolve_key(CATALOG, "workflow.commit_strategy", workspace=workspace, environ={})
    assert (r.value, r.origin) == ("per-task", "default")


def test_resolve_manifest_origin(workspace):
    set_key(CATALOG, "workflow.commit_strategy", "at-end", workspace=workspace)
    r = resolve_key(CATALOG, "workflow.commit_strategy", workspace=workspace, environ={})
    assert (r.value, r.origin) == ("at-end", "manifest")


def test_resolve_env_origin_shadows_manifest(workspace):
    r = resolve_key(
        CATALOG, "GRAPH_WIKI_LOCK_TIMEOUT_MS", workspace=workspace, environ={"GRAPH_WIKI_LOCK_TIMEOUT_MS": "5000"}
    )
    assert (r.value, r.origin) == ("5000", "env")


def test_set_writes_manifest_and_projection(workspace):
    set_key(CATALOG, "topic", "My Wiki", workspace=workspace)
    assert manifest.read(workspace / ".graph-wiki.yaml")["topic"] == "My Wiki"
    payload = json.loads(projection_path(workspace).read_text(encoding="utf-8"))
    assert payload["topic"] == "My Wiki"


def test_set_coerces_bool_and_list(workspace):
    set_key(CATALOG, "state_gate.enabled", "false", workspace=workspace)
    set_key(CATALOG, "state_gate.branches", "main,develop", workspace=workspace)
    data = manifest.read(workspace / ".graph-wiki.yaml")
    assert data["state_gate"] == {"enabled": False, "branches": ["main", "develop"]}


def test_set_enum_violation_raises(workspace):
    with pytest.raises(InvalidValueError, match="at-end"):
        set_key(CATALOG, "workflow.commit_strategy", "sometimes", workspace=workspace)


def test_set_int_wildcard_key(workspace):
    set_key(CATALOG, "roles.scanner.max_tokens", "512", workspace=workspace)
    assert manifest.read(workspace / ".graph-wiki.yaml")["roles"]["scanner"]["max_tokens"] == 512


def test_unset_removes_key(workspace):
    set_key(CATALOG, "topic", "My Wiki", workspace=workspace)
    unset_key(CATALOG, "topic", workspace=workspace)
    assert "topic" not in (workspace / ".graph-wiki.yaml").read_text(encoding="utf-8")


def test_refusals(workspace):
    with pytest.raises(EnvOnlyKeyError, match="export"):
        set_key(CATALOG, "GRAPH_WIKI_LOCK_TIMEOUT_MS", "1", workspace=workspace)
    with pytest.raises(SecretKeyError, match="never stored"):
        set_key(CATALOG, "AI_GATEWAY_API_KEY", "sk-x", workspace=workspace)
    with pytest.raises(LinkFileKeyError, match="link file"):
        set_key(CATALOG, "repo-directory", "/x", workspace=workspace)
    with pytest.raises(ProvenanceKeyError):
        set_key(CATALOG, "initialized_at", "2020-01-01", workspace=workspace)
    with pytest.raises(ProvenanceKeyError):
        set_key(CATALOG, "plugins", "[]", workspace=workspace)
    with pytest.raises(UnknownKeyError, match="did you mean"):
        set_key(CATALOG, "workflow.commit_stragety", "at-end", workspace=workspace)
