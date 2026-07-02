import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOK = REPO_ROOT / "plugins" / "graph-wiki" / "hooks" / "skill-doc-routing"


def run_hook(payload: dict, extra_env: dict | None = None, cwd: Path | None = None):
    env = os.environ.copy()
    env.pop("GRAPH_WIKI_WORKSPACE", None)
    # The hook mirrors session-start's 3-way platform JSON branching; under
    # Claude Code (where this hook runs) CLAUDE_PLUGIN_ROOT is set, selecting
    # the nested hookSpecificOutput shape these tests assert. Pin it so the
    # test isn't sensitive to the runner's ambient env, and clear the sibling
    # platform vars so the Claude Code branch is selected deterministically.
    env.pop("CURSOR_PLUGIN_ROOT", None)
    env.pop("COPILOT_CLI", None)
    env.setdefault("CLAUDE_PLUGIN_ROOT", str(REPO_ROOT / "plugins" / "graph-wiki"))
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else None,
    )
    return proc


def test_non_matching_skill_fast_allows():
    proc = run_hook({"tool_name": "Skill", "tool_input": {"skill_name": "graph-wiki:lint"}})
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "additionalContext" not in out["hookSpecificOutput"]


def test_brainstorming_injects_static_pointer(tmp_path):
    proc = run_hook(
        {"tool_name": "Skill", "tool_input": {"skill_name": "graph-wiki:brainstorming"}},
        extra_env={"GRAPH_WIKI_WORKSPACE": str(tmp_path)},
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "wiki/work/<slug>/" in ctx
    assert "01-design-spec.md" in ctx
    assert "artifact.path" in ctx
    assert str(tmp_path / "raw" / "specs") not in ctx


def test_writing_plans_injects_static_pointer(tmp_path):
    proc = run_hook(
        {"tool_name": "Skill", "tool_input": {"skill_name": "graph-wiki:writing-plans"}},
        extra_env={"GRAPH_WIKI_WORKSPACE": str(tmp_path)},
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "02-plan-plan.md" in ctx
    assert str(tmp_path / "raw" / "plans") not in ctx


def test_unresolvable_workspace_warns_and_allows(tmp_path):
    # No GRAPH_WIKI_WORKSPACE and a non-repo cwd → resolution raises → warn path.
    proc = run_hook(
        {"tool_name": "Skill", "tool_input": {"skill_name": "graph-wiki:brainstorming"}},
        cwd=tmp_path,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "systemMessage" in out
