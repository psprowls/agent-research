"""Tests for the workflow: block and flattened roles: mapping in .graph-wiki.yaml."""

from pathlib import Path

import pytest
import yaml
from workspace_io import manifest

MINIMAL = "version: 2\ninitialized_at: 2026-07-04\nplugins: []\n"


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / ".graph-wiki.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_workflow_absent_normalizes_to_default(tmp_path):
    p = _write(tmp_path, MINIMAL)
    data = manifest.read(p)
    assert data["workflow"] == {"commit_strategy": "per-task", "model_routing": {}, "auto_drive": {}}


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


# ---------------------------------------------------------------------------
# workflow.auto_drive block (Orca auto-drive config — child 1 of the epic)
# ---------------------------------------------------------------------------


def test_auto_drive_absent_normalizes_to_empty(tmp_path):
    p = _write(tmp_path, MINIMAL)
    assert manifest.read(p)["workflow"]["auto_drive"] == {}


def test_auto_drive_absent_with_workflow_block(tmp_path):
    p = _write(tmp_path, MINIMAL + "workflow:\n  commit_strategy: at-end\n")
    assert manifest.read(p)["workflow"]["auto_drive"] == {}


def test_auto_drive_full_block_accepted(tmp_path):
    p = _write(
        tmp_path,
        MINIMAL
        + (
            "workflow:\n"
            "  auto_drive:\n"
            "    max_parallel: 3\n"
            "    permission_mode: bypassPermissions\n"
            "    models:\n"
            "      design: claude-fable-5\n"
            "      execute: claude-sonnet-5\n"
            "    overrides:\n"
            "      - match: {phase: execute, kind: [bug, tech-debt], effort: [xtra-small, small]}\n"
            "        model: claude-haiku-4-5\n"
            "      - match: {phase: plan, kind: epic}\n"
            "        model: claude-fable-5\n"
            "        reasoning_effort: high\n"
        ),
    )
    block = manifest.read(p)["workflow"]["auto_drive"]
    assert block["max_parallel"] == 3
    assert block["permission_mode"] == "bypassPermissions"
    assert block["models"] == {"design": "claude-fable-5", "execute": "claude-sonnet-5"}
    assert block["overrides"][0]["match"]["kind"] == ["bug", "tech-debt"]
    assert block["overrides"][1]["reasoning_effort"] == "high"


@pytest.mark.parametrize(
    "body",
    [
        "workflow:\n  auto_drive: notamapping\n",
        "workflow:\n  auto_drive:\n    nope: 1\n",
        "workflow:\n  auto_drive:\n    max_parallel: 0\n",
        "workflow:\n  auto_drive:\n    max_parallel: true\n",
        "workflow:\n  auto_drive:\n    max_parallel: notanint\n",
        "workflow:\n  auto_drive:\n    permission_mode: ''\n",
        "workflow:\n  auto_drive:\n    models: [design]\n",
        "workflow:\n  auto_drive:\n    models:\n      done: m\n",
        "workflow:\n  auto_drive:\n    models:\n      design: ''\n",
        "workflow:\n  auto_drive:\n    overrides: {}\n",
        "workflow:\n  auto_drive:\n    overrides: [notamapping]\n",
        "workflow:\n  auto_drive:\n    overrides:\n      - model: m\n",
        "workflow:\n  auto_drive:\n    overrides:\n      - match: {phase: plan}\n",
        "workflow:\n  auto_drive:\n    overrides:\n      - match: {}\n        model: m\n",
        "workflow:\n  auto_drive:\n    overrides:\n      - match: {nope: x}\n        model: m\n",
        "workflow:\n  auto_drive:\n    overrides:\n      - match: {phase: ''}\n        model: m\n",
        "workflow:\n  auto_drive:\n    overrides:\n      - match: {kind: []}\n        model: m\n",
        "workflow:\n  auto_drive:\n    overrides:\n      - match: {phase: plan}\n        model: ''\n",
        (
            "workflow:\n  auto_drive:\n    overrides:\n      - match: {phase: plan}\n"
            "        model: m\n        reasoning_effort: extreme\n"
        ),
        "workflow:\n  auto_drive:\n    overrides:\n      - match: {phase: plan}\n        model: m\n        nope: 1\n",
    ],
)
def test_auto_drive_rejects_bad_shapes(tmp_path, body):
    p = _write(tmp_path, MINIMAL + body)
    with pytest.raises(RuntimeError):
        manifest.read(p)


def test_auto_drive_write_round_trip(tmp_path):
    p = tmp_path / ".graph-wiki.yaml"
    block = {
        "max_parallel": 2,
        "overrides": [{"match": {"phase": "plan"}, "model": "claude-sonnet-5"}],
    }
    manifest.write(
        p,
        {"version": 2, "initialized_at": "2026-08-07", "plugins": [], "workflow": {"auto_drive": block}},
    )
    assert manifest.read(p)["workflow"]["auto_drive"] == block


def test_auto_drive_empty_not_written_to_disk(tmp_path):
    p = tmp_path / ".graph-wiki.yaml"
    manifest.write(
        p,
        {"version": 2, "initialized_at": "2026-08-07", "plugins": [], "workflow": {"auto_drive": {}}},
    )
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "workflow" not in raw
