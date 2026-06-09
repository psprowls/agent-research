from __future__ import annotations

import json
import os
import threading
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


def test_load_oauth_token_missing_raises(monkeypatch):
    """Raise ValueError if token not found anywhere."""
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("HOME", raising=False)

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
