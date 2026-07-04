"""Subprocess tests for session-start's config.json notices and warnings."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOK = REPO_ROOT / "plugins" / "graph-wiki" / "hooks" / "session-start"


def run_hook(workspace: Path):
    env = os.environ.copy()
    env["GRAPH_WIKI_WORKSPACE"] = str(workspace)
    env.pop("CURSOR_PLUGIN_ROOT", None)
    env.pop("COPILOT_CLI", None)
    env.setdefault("CLAUDE_PLUGIN_ROOT", str(REPO_ROOT / "plugins" / "graph-wiki"))
    proc = subprocess.run(["bash", str(HOOK)], input="{}", capture_output=True, text=True, env=env, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def _seed(tmp_path: Path, *, workflow: dict | None = None, stale: bool = False) -> Path:
    ws = tmp_path / "ws"
    (ws / ".graph-wiki").mkdir(parents=True)
    manifest = ws / ".graph-wiki.yaml"
    manifest.write_text("version: 2\ninitialized_at: 2026-07-04\nplugins: []\n", encoding="utf-8")
    payload: dict = {"version": 2}
    if workflow:
        payload["workflow"] = workflow
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if stale:
        digest = "0" * 64
    payload["_meta"] = {"manifest_sha256": digest, "manifest_mtime": 0}
    (ws / ".graph-wiki" / "config.json").write_text(json.dumps(payload), encoding="utf-8")
    return ws


def test_routing_notice_from_config_json(tmp_path):
    ws = _seed(tmp_path, workflow={"model_routing": {"mechanical": "haiku"}})
    ctx = run_hook(ws)
    assert "model-routing-active" in ctx
    assert "GRAPH_WIKI_ROUTING_GUARD" in ctx
    assert "SUPERPOWERS_ROUTING_GUARD" not in ctx


def test_no_routing_notice_when_absent(tmp_path):
    ctx = run_hook(_seed(tmp_path))
    assert "model-routing-active" not in ctx
    assert "workflow-config-active" not in ctx
    assert "graph-wiki-config-stale" not in ctx
    assert "graph-wiki-legacy-config" not in ctx


def test_fail_open_on_garbage_config_json(tmp_path):
    """A corrupt config.json must not break the hook: exit 0, valid JSON, no notices."""
    ws = _seed(tmp_path)
    (ws / ".graph-wiki" / "config.json").write_text("not json{{{", encoding="utf-8")
    ctx = run_hook(ws)  # run_hook asserts exit 0 and parses the hook JSON
    assert "model-routing-active" not in ctx
    assert "workflow-config-active" not in ctx
    assert "graph-wiki-config-stale" not in ctx
    assert "graph-wiki-legacy-config" not in ctx


def test_commit_strategy_notice(tmp_path):
    ws = _seed(tmp_path, workflow={"commit_strategy": "at-end"})
    ctx = run_hook(ws)
    assert "workflow-config-active" in ctx
    assert "at-end" in ctx


def test_staleness_warning_instructs_sync(tmp_path):
    ws = _seed(tmp_path, stale=True)
    ctx = run_hook(ws)
    assert "gw config sync" in ctx


def test_legacy_json_warning(tmp_path):
    ws = _seed(tmp_path)
    (ws / ".graph-wiki" / "model-routing.json").write_text("{}", encoding="utf-8")
    ctx = run_hook(ws)
    assert "legacy" in ctx.lower()
    assert "model-routing.json" in ctx
