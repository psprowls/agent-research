from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from claude_code_evals.runner import EVAL_SYSTEM_PROMPT_IMPLEMENT, EVAL_SYSTEM_PROMPT_QA, run_one_shot


def _make_fake_proc(events: list[dict]) -> MagicMock:
    jsonl = "\n".join(json.dumps(e) for e in events) + "\n"
    mock = MagicMock()
    mock.stdout = iter(jsonl.splitlines(keepends=True))
    mock.returncode = 0
    mock.terminate = MagicMock()
    mock.wait = MagicMock()
    return mock


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


def test_system_prompt_constants():
    assert "EVAL MODE" in EVAL_SYSTEM_PROMPT_QA
    assert "Q&A" in EVAL_SYSTEM_PROMPT_QA
    assert "EVAL MODE" in EVAL_SYSTEM_PROMPT_IMPLEMENT
    assert "IMPLEMENT" in EVAL_SYSTEM_PROMPT_IMPLEMENT
