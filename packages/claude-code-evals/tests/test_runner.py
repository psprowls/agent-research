from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from claude_code_evals.runner import (
    EVAL_SYSTEM_PROMPT_IMPLEMENT,
    EVAL_SYSTEM_PROMPT_QA,
    load_oauth_token,
    prepare_injected_context,
    prepare_plugin_env,
    run_interactive,
    run_multi_turn,
    run_one_shot,
)


def _make_fake_proc(events: list[dict], *, returncode: int = 0, extra_lines: list[str] | None = None) -> MagicMock:
    lines = [json.dumps(e) for e in events] + list(extra_lines or [])
    jsonl = ("\n".join(lines) + "\n") if lines else ""
    mock = MagicMock()
    mock.stdout = iter(jsonl.splitlines(keepends=True))
    mock.returncode = returncode
    mock.terminate = MagicMock()
    mock.wait = MagicMock()
    return mock


def _capture_popen(proc: MagicMock):
    """Return (captured, patched_fn). captured holds the cmd/env/kwargs of the Popen call."""
    captured: dict = {}

    def _fake(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        captured["kwargs"] = kwargs
        return proc

    return captured, _fake


RESULT_EVENT = {
    "type": "result",
    "subtype": "success",
    "usage": {"input_tokens": 50, "output_tokens": 20, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
}

ASSISTANT_EVENT = {
    "type": "assistant",
    "message": {"content": [{"type": "text", "text": "Done."}]},
}


def test_run_one_shot_success(tmp_path: Path):
    proc = _make_fake_proc([ASSISTANT_EVENT, RESULT_EVENT])
    with patch("subprocess.Popen", return_value=proc):
        result, _ = run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=tmp_path,
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
        )
    assert result.final_status == "success"
    assert result.budget_exceeded is False
    assert result.wall_seconds >= 0


def test_run_one_shot_returns_jsonl(tmp_path: Path):
    proc = _make_fake_proc([ASSISTANT_EVENT, RESULT_EVENT])
    with patch("subprocess.Popen", return_value=proc):
        _, jsonl = run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=tmp_path,
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
        )
    events = [json.loads(line) for line in jsonl.splitlines() if line.strip()]
    types = [e["type"] for e in events]
    assert "assistant" in types
    assert "result" in types


def test_run_one_shot_error_status(tmp_path: Path):
    error_event = {
        "type": "result",
        "subtype": "error_max_turns",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }
    proc = _make_fake_proc([error_event])
    with patch("subprocess.Popen", return_value=proc):
        result, _ = run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=tmp_path,
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
        )
    assert result.final_status == "error_max_turns"


def test_run_one_shot_threads_oauth_token_and_strips_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-should-be-stripped")
    proc = _make_fake_proc([RESULT_EVENT])
    captured, fake = _capture_popen(proc)
    cfg = tmp_path / "cfg"
    with patch("subprocess.Popen", side_effect=fake):
        run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=cfg,
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
            oauth_token="sk-ant-oat01-resolved",
        )
    env = captured["env"]
    assert env["CLAUDE_CONFIG_DIR"] == str(cfg)
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-resolved"
    assert "ANTHROPIC_API_KEY" not in env


def test_run_one_shot_cmd_uses_append_system_prompt_not_config_dir(tmp_path: Path):
    proc = _make_fake_proc([RESULT_EVENT])
    captured, fake = _capture_popen(proc)
    with patch("subprocess.Popen", side_effect=fake):
        run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=tmp_path / "cfg",
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
        )
    cmd = captured["cmd"]
    assert "--config-dir" not in cmd
    assert "--append-system-prompt" in cmd
    assert "--add-dir" in cmd
    # stderr is merged into stdout so error text is captured
    assert captured["kwargs"].get("stderr") is not None


def test_run_one_shot_threads_plugin_dirs(tmp_path: Path):
    proc = _make_fake_proc([RESULT_EVENT])
    captured, fake = _capture_popen(proc)
    with patch("subprocess.Popen", side_effect=fake):
        run_one_shot(
            prompt="x",
            worktree_path=tmp_path,
            cfg_dir=tmp_path / "cfg",
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
            plugin_dirs=[tmp_path / "p1", tmp_path / "p2"],
        )
    cmd = captured["cmd"]
    assert cmd.count("--plugin-dir") == 2
    assert str(tmp_path / "p1") in cmd
    assert str(tmp_path / "p2") in cmd


def test_run_one_shot_is_error_result_captures_reason(tmp_path: Path):
    """An is_error result event (e.g. 'Not logged in') must surface as failure with a reason."""
    err_event = {
        "type": "result",
        "subtype": "success",
        "is_error": True,
        "result": "Not logged in · Please run /login",
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }
    proc = _make_fake_proc([err_event])
    captured, fake = _capture_popen(proc)
    with patch("subprocess.Popen", side_effect=fake):
        result, _ = run_one_shot(
            prompt="x", worktree_path=tmp_path, cfg_dir=tmp_path, system_prompt=EVAL_SYSTEM_PROMPT_QA
        )
    assert result.final_status != "success"
    assert result.error_reason is not None
    assert "Not logged in" in result.error_reason


def test_run_one_shot_no_result_nonzero_exit_is_error_with_stderr(tmp_path: Path):
    """The dead-flag crash: claude exits non-zero, no result event, stderr in the merged stream."""
    proc = _make_fake_proc([], returncode=1, extra_lines=["error: unknown option '--config-dir'"])
    captured, fake = _capture_popen(proc)
    with patch("subprocess.Popen", side_effect=fake):
        result, _ = run_one_shot(
            prompt="x", worktree_path=tmp_path, cfg_dir=tmp_path, system_prompt=EVAL_SYSTEM_PROMPT_QA
        )
    assert result.final_status == "error_no_result"
    assert result.exit_code == 1
    assert result.error_reason is not None
    assert "unknown option" in result.error_reason


def test_system_prompt_constants():
    assert "EVAL MODE" in EVAL_SYSTEM_PROMPT_QA
    assert "Q&A" in EVAL_SYSTEM_PROMPT_QA
    assert "EVAL MODE" in EVAL_SYSTEM_PROMPT_IMPLEMENT
    assert "IMPLEMENT" in EVAL_SYSTEM_PROMPT_IMPLEMENT


def test_injected_arm_prepends_wiki_pages(tmp_path: Path):
    """Injected arm prepends wiki page text to the system prompt."""
    # Mock the wiki file system
    wiki_root = tmp_path / "test-wiki"
    (wiki_root / "wiki" / "concepts").mkdir(parents=True)
    with open(wiki_root / "wiki" / "concepts" / "design-tokens.md", "w") as f:
        f.write("# Design Tokens\n\nTokens are defined in config.ts")

    base_prompt = "Use this knowledge:"
    context = prepare_injected_context(
        base_prompt=base_prompt,
        wiki_root=str(wiki_root),
        inject_paths=["concepts/design-tokens.md"],
    )

    assert "Design Tokens" in context
    assert "Tokens are defined in config.ts" in context
    assert base_prompt in context


def test_plugin_arm_sets_wiki_workspace_env():
    """Plugin arm sets GRAPH_WIKI_WORKSPACE env var for the subprocess."""
    plugin_config = {
        "model": "claude-opus-4-8",
        "environment": {
            "GRAPH_WIKI_WORKSPACE": "~/Personal/graph-wiki/mono-repo-eval-551f7ed8",
        },
    }

    env = prepare_plugin_env(plugin_config)

    assert "GRAPH_WIKI_WORKSPACE" in env
    expanded = os.path.expanduser("~/Personal/graph-wiki/mono-repo-eval-551f7ed8")
    assert env["GRAPH_WIKI_WORKSPACE"] == expanded


def test_load_oauth_token_from_env_var(monkeypatch):
    """Load token from CLAUDE_CODE_OAUTH_TOKEN env var (priority 1)."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-env-token")
    token = load_oauth_token()
    assert token == "sk-ant-oat01-env-token"


def test_load_oauth_token_from_git_ignored_file(tmp_path: Path, monkeypatch):
    """Load token from eval/.secrets file (priority 3, when env not set)."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)

    # Create eval/.secrets
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    secrets_file = eval_dir / ".secrets"
    secrets_file.write_text("sk-ant-oat01-file-token\n")

    token = load_oauth_token()
    assert token == "sk-ant-oat01-file-token"


def test_load_oauth_token_from_explicit_path(tmp_path: Path, monkeypatch):
    """Load token from explicit file path (priority 2)."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    # Create a custom token file
    token_file = tmp_path / "my-token"
    token_file.write_text("sk-ant-oat01-explicit-token\n")

    token = load_oauth_token(token_file_path=str(token_file))
    assert token == "sk-ant-oat01-explicit-token"


def test_load_oauth_token_from_home_config(tmp_path: Path, monkeypatch):
    """Load token from ~/.config/cc-eval/token (priority 4)."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)

    # Mock home directory
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # Create ~/.config/cc-eval/token
    config_dir = home / ".config" / "cc-eval"
    config_dir.mkdir(parents=True)
    token_file = config_dir / "token"
    token_file.write_text("sk-ant-oat01-home-token\n")

    token = load_oauth_token()
    assert token == "sk-ant-oat01-home-token"


def test_load_oauth_token_missing_raises(tmp_path: Path, monkeypatch):
    """Raise ValueError if token not found anywhere."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="OAuth token not found"):
        load_oauth_token()


def test_load_oauth_token_env_precedence(tmp_path: Path, monkeypatch):
    """Verify env var takes precedence over file locations."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-env")
    monkeypatch.chdir(tmp_path)

    # Create eval/.secrets with different token
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    secrets_file = eval_dir / ".secrets"
    secrets_file.write_text("sk-ant-oat01-file\n")

    token = load_oauth_token()
    # Should return env var, not file
    assert token == "sk-ant-oat01-env"


def test_load_oauth_token_strips_whitespace(tmp_path: Path, monkeypatch):
    """Token is stripped of leading/trailing whitespace."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)

    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    secrets_file = eval_dir / ".secrets"
    secrets_file.write_text("  sk-ant-oat01-token-with-whitespace  \n")

    token = load_oauth_token()
    assert token == "sk-ant-oat01-token-with-whitespace"


def test_run_interactive_returns_completed_when_done_file_appears(tmp_path):
    done_file = tmp_path / ".eval-done"

    def _touch_after_short_delay():
        import time

        time.sleep(0.05)
        done_file.touch()

    t = threading.Thread(target=_touch_after_short_delay, daemon=True)
    t.start()

    result, jsonl = run_interactive(worktree_path=tmp_path, poll_interval=0.01)
    t.join(timeout=1)

    assert result.final_status == "completed_interactive"
    assert result.budget_exceeded is False
    assert jsonl == ""


def test_run_interactive_budget_exceeded_when_timeout(tmp_path):
    result, jsonl = run_interactive(
        worktree_path=tmp_path,
        poll_interval=0.01,
        max_wait_seconds=0.05,
    )
    assert result.final_status == "budget_exceeded"
    assert result.budget_exceeded is True
    assert jsonl == ""


# --- multi-turn (async runner, fake-CLI subprocess fixtures) ---

FAKE_CLI_PRELUDE = """\
import json, sys, time

def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\\n")
    sys.stdout.flush()

def assistant(*texts):
    emit({"type": "assistant",
          "message": {"content": [{"type": "text", "text": t} for t in texts]}})

def result(**kw):
    ev = {"type": "result", "subtype": "success", "usage": {}}
    ev.update(kw)
    emit(ev)

def read_reply():
    return sys.stdin.readline()
"""


class _StubSimulator:
    """Duck-typed stand-in for AutoUserSimulator."""

    def __init__(self, replies: list[str | None], *, reply_delay: float = 0.0):
        self._replies = list(replies)
        self._reply_delay = reply_delay
        self.calls: list[tuple[str, str]] = []
        self.input_tokens = 7
        self.output_tokens = 3

    def reply(self, full_text: str, final_block: str) -> str | None:
        if self._reply_delay:
            time.sleep(self._reply_delay)
        self.calls.append((full_text, final_block))
        if not self._replies:
            return None
        return self._replies.pop(0)


def _run_fake_multi_turn(
    tmp_path: Path,
    body: str,
    simulator: _StubSimulator,
    *,
    max_turns: int = 20,
    max_wall_seconds: float = 10.0,
):
    """Write a fake CLI script and drive run_multi_turn against it."""
    script = tmp_path / "fake_cli.py"
    script.write_text(FAKE_CLI_PRELUDE + body)
    fake_cmd = [sys.executable, str(script)]
    with patch("claude_code_evals.runner._build_cmd", return_value=fake_cmd):
        return run_multi_turn(
            prompt="task",
            worktree_path=tmp_path,
            cfg_dir=tmp_path,
            system_prompt="sys",
            simulator=simulator,  # type: ignore[arg-type]  # duck-typed stand-in
            max_turns=max_turns,
            max_wall_seconds=max_wall_seconds,
        )


def test_multi_turn_success_and_simulator_io(tmp_path: Path):
    body = """
assistant("Hello ", "World")
result()
line = read_reply()
assert json.loads(line)["message"]["content"] == "keep going"
assistant("turn two")
result()
read_reply()
"""
    sim = _StubSimulator(["keep going", None])
    res, raw = _run_fake_multi_turn(tmp_path, body, sim)
    assert res.final_status == "success"
    assert not res.budget_exceeded
    # full text = all blocks concatenated; final block = last block only
    assert sim.calls[0] == ("Hello World", "World")
    assert sim.calls[1] == ("turn two", "turn two")
    assert res.simulator_input_tokens == 7
    assert res.simulator_output_tokens == 3
    assert '"turn two"' in raw


def test_multi_turn_error_result_classified(tmp_path: Path):
    body = """
assistant("boom")
result(subtype="error_during_execution", is_error=True, result="kaboom happened")
"""
    sim = _StubSimulator(["never sent"])
    res, _ = _run_fake_multi_turn(tmp_path, body, sim)
    assert res.final_status == "error_during_execution"
    assert "kaboom" in (res.error_reason or "")
    assert sim.calls == []  # verifiers must not see this as a normal end


def test_multi_turn_no_result_event_surfaces_stderr(tmp_path: Path):
    body = """
sys.stderr.write("auth failure: bad token\\n")
sys.stderr.flush()
sys.exit(1)
"""
    res, _ = _run_fake_multi_turn(tmp_path, body, _StubSimulator([]))
    assert res.final_status == "error_no_result"
    assert "auth failure" in (res.error_reason or "")


def test_multi_turn_cli_death_on_reply_write(tmp_path: Path):
    # CLI exits right after its first result; the reply write hits a dead pipe.
    # reply_delay gives the event loop time to observe the child's death so the
    # stdin transport reliably raises instead of racing to a stdout EOF.
    body = """
assistant("turn one")
result()
sys.stdin.close()
sys.exit(0)
"""
    sim = _StubSimulator(["next"], reply_delay=0.3)
    res, _ = _run_fake_multi_turn(tmp_path, body, sim)
    assert res.final_status == "error_cli_died"


def test_multi_turn_wall_clock_timeout_on_silent_hang(tmp_path: Path):
    body = """
time.sleep(30)
"""
    res, _ = _run_fake_multi_turn(tmp_path, body, _StubSimulator([]), max_wall_seconds=0.5)
    assert res.final_status == "budget_exceeded"
    assert res.budget_exceeded


def test_multi_turn_max_turns_enforced(tmp_path: Path):
    body = """
for i in range(10):
    assistant("turn %d" % i)
    result()
    if not read_reply():
        break
"""
    sim = _StubSimulator(["go"] * 10)
    res, _ = _run_fake_multi_turn(tmp_path, body, sim, max_turns=2)
    assert res.final_status == "budget_exceeded"
    assert res.budget_exceeded
    assert "max_turns (2)" in (res.error_reason or "")
    assert len(sim.calls) == 1  # cap hit on the 2nd result, before a 2nd reply


def test_multi_turn_large_line_exceeds_default_stream_limit(tmp_path: Path):
    # A single stream-json line >64KB (large tool results are routine) must not
    # crash the run: asyncio's default 64KB readline limit raises ValueError.
    body = """
assistant("x" * 100_000)
result()
read_reply()
"""
    sim = _StubSimulator([])
    res, _ = _run_fake_multi_turn(tmp_path, body, sim)
    assert res.final_status == "success"
