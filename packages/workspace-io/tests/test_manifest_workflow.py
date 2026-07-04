"""Tests for the workflow: block and flattened roles: mapping in .graph-wiki.yaml."""

from pathlib import Path

import pytest
from workspace_io import manifest

MINIMAL = "version: 2\ninitialized_at: 2026-07-04\nplugins: []\n"


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / ".graph-wiki.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_workflow_absent_normalizes_to_default(tmp_path):
    p = _write(tmp_path, MINIMAL)
    data = manifest.read(p)
    assert data["workflow"] == {"commit_strategy": "per-task", "model_routing": {}}


def test_workflow_roundtrip(tmp_path):
    p = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-07-04",
        "plugins": [],
        "workflow": {
            "commit_strategy": "at-end",
            "model_routing": {"mechanical": "haiku", "standard": "sonnet", "frontier": "inherit"},
        },
    }
    manifest.write(p, data)
    back = manifest.read(p)
    assert back["workflow"]["commit_strategy"] == "at-end"
    assert back["workflow"]["model_routing"]["mechanical"] == "haiku"


def test_workflow_default_not_written_to_disk(tmp_path):
    p = tmp_path / ".graph-wiki.yaml"
    manifest.write(
        p,
        {
            "version": 2,
            "initialized_at": "2026-07-04",
            "plugins": [],
            "workflow": {"commit_strategy": "per-task", "model_routing": {}},
        },
    )
    assert "workflow" not in p.read_text(encoding="utf-8")


def test_workflow_invalid_commit_strategy_raises(tmp_path):
    p = _write(tmp_path, MINIMAL + "workflow:\n  commit_strategy: sometimes\n")
    with pytest.raises(RuntimeError, match="commit_strategy"):
        manifest.read(p)


def test_workflow_unknown_tier_raises(tmp_path):
    p = _write(tmp_path, MINIMAL + "workflow:\n  model_routing:\n    turbo: haiku\n")
    with pytest.raises(RuntimeError, match="model_routing"):
        manifest.read(p)


def test_roles_flattened_roundtrip(tmp_path):
    p = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-07-04",
        "plugins": [],
        "roles": {"scanner": {"model_id": "zai.glm-5", "max_tokens": 1024}},
    }
    manifest.write(p, data)
    back = manifest.read(p)
    assert back["roles"]["scanner"]["model_id"] == "zai.glm-5"


def test_roles_absent_normalizes_to_empty(tmp_path):
    p = _write(tmp_path, MINIMAL)
    assert manifest.read(p)["roles"] == {}


def test_roles_unknown_field_raises(tmp_path):
    p = _write(tmp_path, MINIMAL + "roles:\n  scanner:\n    temperature: 0.5\n")
    with pytest.raises(RuntimeError, match="roles"):
        manifest.read(p)


def test_plugins_roles_not_emitted(tmp_path):
    p = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-07-04",
        "plugins": [
            {
                "name": "graph-wiki-agent",
                "installed_version": "1.0",
                "applied_version": "1.0",
                "roles": [{"name": "scanner"}],
            }
        ],
    }
    manifest.write(p, data)
    text = p.read_text(encoding="utf-8")
    assert "roles" not in text  # neither nested nor top-level (empty)


def test_read_roles_returns_flattened_mapping(tmp_path):
    p = tmp_path / ".graph-wiki.yaml"
    manifest.write(
        p, {"version": 2, "initialized_at": "2026-07-04", "plugins": [], "roles": {"librarian": {"backend": "vercel"}}}
    )
    assert manifest.read_roles(p) == {"librarian": {"backend": "vercel"}}


def test_read_roles_missing_manifest_returns_empty(tmp_path):
    assert manifest.read_roles(tmp_path / ".graph-wiki.yaml") == {}
