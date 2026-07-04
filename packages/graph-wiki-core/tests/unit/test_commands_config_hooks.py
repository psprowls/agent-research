"""Merge/dedup tests for gw config hooks + the env-block writer."""

import json
from pathlib import Path

import pytest
from graph_wiki_core.commands.config import (
    HookWiring,
    run_config_hooks,
    write_workspace_env_block,
)


@pytest.fixture
def scripts_dir(tmp_path):
    d = tmp_path / "examples"
    d.mkdir()
    for name in (
        "post-task-complete-revalidate.sh",
        "stop-revalidate-user-gates.sh",
        "session-end-transcript-capture.sh",
    ):
        (d / name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    return d


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / ".claude").mkdir(parents=True)
    return r


def _settings(repo: Path) -> dict:
    return json.loads((repo / ".claude" / "settings.local.json").read_text(encoding="utf-8"))


async def test_enable_gates_merges_hooks_and_deny(repo, scripts_dir):
    result = await run_config_hooks("enable", "gates", repo_root=repo, scripts_dir=scripts_dir)
    s = _settings(repo)
    post = s["hooks"]["PostToolUse"]
    assert any("post-task-complete-revalidate.sh" in h["command"] for e in post for h in e["hooks"])
    stop = s["hooks"]["Stop"]
    assert any("stop-revalidate-user-gates.sh" in h["command"] for e in stop for h in e["hooks"])
    assert "EnterPlanMode" in s["permissions"]["deny"]
    assert result.changed


async def test_enable_preserves_existing_settings(repo, scripts_dir):
    target = repo / ".claude" / "settings.local.json"
    target.write_text(
        json.dumps(
            {
                "env": {"FOO": "bar"},
                "hooks": {
                    "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "bash other.sh"}]}]
                },
            }
        ),
        encoding="utf-8",
    )
    await run_config_hooks("enable", "gates", repo_root=repo, scripts_dir=scripts_dir)
    s = _settings(repo)
    assert s["env"] == {"FOO": "bar"}
    assert any("other.sh" in h["command"] for e in s["hooks"]["PostToolUse"] for h in e["hooks"])


async def test_enable_twice_is_noop(repo, scripts_dir):
    await run_config_hooks("enable", "transcript", repo_root=repo, scripts_dir=scripts_dir)
    first = _settings(repo)
    result = await run_config_hooks("enable", "transcript", repo_root=repo, scripts_dir=scripts_dir)
    assert _settings(repo) == first
    assert not result.changed


async def test_disable_removes_what_enable_added(repo, scripts_dir):
    await run_config_hooks("enable", "gates", repo_root=repo, scripts_dir=scripts_dir)
    await run_config_hooks("disable", "gates", repo_root=repo, scripts_dir=scripts_dir)
    s = _settings(repo)
    assert not any("revalidate" in h["command"] for arr in s.get("hooks", {}).values() for e in arr for h in e["hooks"])
    assert "EnterPlanMode" not in s.get("permissions", {}).get("deny", [])


def test_hook_wiring_tables_reference_real_scripts():
    repo_root = Path(__file__).resolve().parents[4]
    examples = repo_root / "plugins" / "graph-wiki" / "hooks" / "examples"
    for wiring in HookWiring.for_feature("gates") + HookWiring.for_feature("transcript"):
        assert (examples / wiring.script).is_file(), wiring.script


async def test_write_env_block_merges(repo, tmp_path):
    ws = tmp_path / "ws"
    out = write_workspace_env_block(repo, ws)
    s = _settings(repo)
    assert s["env"]["GRAPH_WIKI_WORKSPACE"] == str(ws.resolve())
    assert out == repo / ".claude" / "settings.local.json"
