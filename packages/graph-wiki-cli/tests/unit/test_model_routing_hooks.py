"""Subprocess tests: routing hooks read <workspace>/.graph-wiki/config.json."""

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOKS = REPO_ROOT / "plugins" / "graph-wiki" / "hooks"


def run_hook(hook: str, payload: dict, workspace: Path):
    env = os.environ.copy()
    env["GRAPH_WIKI_WORKSPACE"] = str(workspace)
    env.pop("CURSOR_PLUGIN_ROOT", None)
    env.pop("COPILOT_CLI", None)
    env.setdefault("CLAUDE_PLUGIN_ROOT", str(REPO_ROOT / "plugins" / "graph-wiki"))
    return subprocess.run(
        ["bash", str(HOOKS / hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def _seed_workspace(tmp_path: Path, routing: dict | None) -> Path:
    ws = tmp_path / "ws"
    (ws / ".graph-wiki").mkdir(parents=True)
    (ws / ".graph-wiki.yaml").write_text("version: 2\ninitialized_at: 2026-07-04\nplugins: []\n", encoding="utf-8")
    payload: dict = {"version": 2}
    if routing is not None:
        payload["workflow"] = {"model_routing": routing}
    (ws / ".graph-wiki" / "config.json").write_text(json.dumps(payload), encoding="utf-8")
    return ws


PLAN_SHAPED = {
    "tool_name": "TaskCreate",
    "tool_input": {
        "subject": "Task 1: build the thing",
        "description": "**Goal:** x\n**Acceptance Criteria:** y\n**Verify:** z",
    },
}


def test_taskcreate_dormant_without_config_json(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".graph-wiki").mkdir(parents=True)
    proc = run_hook("pre-taskcreate-model-tier", PLAN_SHAPED, ws)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_taskcreate_dormant_with_empty_routing(tmp_path):
    ws = _seed_workspace(tmp_path, routing=None)
    proc = run_hook("pre-taskcreate-model-tier", PLAN_SHAPED, ws)
    assert proc.returncode == 0


def test_taskcreate_blocks_plan_shaped_without_fence_when_routing_active(tmp_path):
    ws = _seed_workspace(tmp_path, routing={"mechanical": "haiku", "standard": "sonnet"})
    proc = run_hook("pre-taskcreate-model-tier", PLAN_SHAPED, ws)
    assert proc.returncode == 2
    assert "config.json" in proc.stderr


def test_agent_hook_dormant_with_empty_routing(tmp_path):
    ws = _seed_workspace(tmp_path, routing=None)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("", encoding="utf-8")
    proc = run_hook(
        "pre-agent-model-routing",
        {"tool_name": "Agent", "tool_input": {"model": "opus"}, "transcript_path": str(transcript)},
        ws,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_no_home_fallback_left_in_sources():
    for hook in ("pre-agent-model-routing", "pre-taskcreate-model-tier", "session-start"):
        text = (HOOKS / hook).read_text(encoding="utf-8")
        assert ".claude/graph-wiki" not in text, hook
        assert "model-routing.json" not in text or hook == "session-start", hook
