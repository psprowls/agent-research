"""Integration test for the opt-in SessionEnd transcript-capture hook.

# integration-gate-allow
Shells out to the real bash script (not a mock) against a fixture project
directory shaped like real `~/.claude/projects/*` output. This does NOT touch
any external network service (no Bedrock, no API) — it's a subprocess call
against tmp_path fixtures, <1s. Carries the `# integration-gate-allow` marker
instead of the canonical GRAPH_WIKI_RUN_INTEGRATION env gate (see
docs/notes/testing.md), matching packages/graph-io/tests/integration/
test_multi_repo_update.py. Keeps `pytest.mark.integration` so the default
`-m "not integration"` run still skips it; opt in with `-m integration`.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOK = REPO_ROOT / "plugins" / "graph-wiki" / "hooks" / "examples" / "session-end-transcript-capture.sh"


def _make_workspace(tmp_path: Path, *, slug: str, phase: str) -> Path:
    workspace = tmp_path / "ws"
    (workspace / "wiki" / "work" / slug).mkdir(parents=True)
    (workspace / ".graph-wiki").mkdir(parents=True)
    pointer = {"slug": slug, "phase": phase, "updated": "2026-06-30T00:00:00+00:00"}
    (workspace / ".graph-wiki" / "active-work.json").write_text(json.dumps(pointer), encoding="utf-8")
    return workspace


def _make_transcript_with_sidechains(tmp_path: Path, *, session_id: str, agent_ids: list[str]) -> Path:
    project_dir = tmp_path / "projects" / "-fake-project"
    project_dir.mkdir(parents=True)
    transcript = project_dir / f"{session_id}.jsonl"
    transcript.write_text('{"type": "user", "message": {}}\n', encoding="utf-8")
    if agent_ids:
        sidechain_dir = project_dir / session_id / "subagents"
        sidechain_dir.mkdir(parents=True)
        for agent_id in agent_ids:
            (sidechain_dir / f"agent-{agent_id}.jsonl").write_text('{"type": "assistant"}\n', encoding="utf-8")
            (sidechain_dir / f"agent-{agent_id}.meta.json").write_text(
                json.dumps({"agentType": "Explore", "description": "look around"}), encoding="utf-8"
            )
    return transcript


def run_hook(payload: dict, *, cwd: Path, extra_env: dict[str, str] | None = None):
    env = os.environ.copy()
    env["GRAPH_WIKI_WORKSPACE"] = str(cwd)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
    )
    return proc


def test_copies_main_and_subagent_transcripts(tmp_path):
    workspace = _make_workspace(tmp_path, slug="fix-bug", phase="execute")
    transcript = _make_transcript_with_sidechains(tmp_path, session_id="sess1", agent_ids=["explore", "1"])

    proc = run_hook({"session_id": "sess1", "transcript_path": str(transcript)}, cwd=workspace)

    assert proc.returncode == 0
    item_dir = workspace / "wiki" / "work" / "fix-bug"
    assert (item_dir / "03-execute.jsonl").read_text(encoding="utf-8") == transcript.read_text(encoding="utf-8")
    assert (item_dir / "03-execute-subagent-explore.jsonl").exists()
    assert (item_dir / "03-execute-subagent-1.jsonl").exists()
    assert not any(item_dir.glob("*.meta.json"))


def test_no_subagents_dir_still_copies_main(tmp_path):
    workspace = _make_workspace(tmp_path, slug="fix-bug", phase="design")
    transcript = _make_transcript_with_sidechains(tmp_path, session_id="sess2", agent_ids=[])

    proc = run_hook({"session_id": "sess2", "transcript_path": str(transcript)}, cwd=workspace)

    assert proc.returncode == 0
    item_dir = workspace / "wiki" / "work" / "fix-bug"
    assert (item_dir / "01-design.jsonl").exists()


def test_missing_pointer_is_a_silent_noop(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "wiki" / "work").mkdir(parents=True)
    transcript = _make_transcript_with_sidechains(tmp_path, session_id="sess3", agent_ids=[])

    proc = run_hook({"session_id": "sess3", "transcript_path": str(transcript)}, cwd=workspace)

    assert proc.returncode == 0
    assert not list((workspace / "wiki" / "work").glob("*.jsonl"))


def test_malformed_pointer_is_a_silent_noop(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "wiki" / "work" / "fix-bug").mkdir(parents=True)
    (workspace / ".graph-wiki").mkdir(parents=True)
    (workspace / ".graph-wiki" / "active-work.json").write_text("{not json", encoding="utf-8")
    transcript = _make_transcript_with_sidechains(tmp_path, session_id="sess4", agent_ids=[])

    proc = run_hook({"session_id": "sess4", "transcript_path": str(transcript)}, cwd=workspace)

    assert proc.returncode == 0
    assert not list((workspace / "wiki" / "work" / "fix-bug").glob("*.jsonl"))


def test_missing_transcript_path_exits_zero(tmp_path):
    workspace = _make_workspace(tmp_path, slug="fix-bug", phase="design")

    proc = run_hook({"session_id": "sess5", "transcript_path": "/no/such/file.jsonl"}, cwd=workspace)

    assert proc.returncode == 0
    assert not any((workspace / "wiki" / "work" / "fix-bug").glob("*.jsonl"))


def test_guard_disabled_skips_capture(tmp_path):
    workspace = _make_workspace(tmp_path, slug="fix-bug", phase="execute")
    transcript = _make_transcript_with_sidechains(tmp_path, session_id="sess6", agent_ids=["explore"])

    proc = run_hook(
        {"session_id": "sess6", "transcript_path": str(transcript)},
        cwd=workspace,
        extra_env={"GRAPH_WIKI_TRANSCRIPT_CAPTURE_GUARD": "0"},
    )

    assert proc.returncode == 0
    item_dir = workspace / "wiki" / "work" / "fix-bug"
    assert not list(item_dir.glob("*.jsonl"))
