from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from claude_code_evals.judge import ClaudeCodeJudge, JudgeResult, _run_claude_judge


def _fake_result(text: str) -> JudgeResult:
    return JudgeResult(stdout=text, input_tokens=10, output_tokens=5)


def test_get_model_name():
    judge = ClaudeCodeJudge(model="claude-haiku-4-5-20251001")
    assert judge.get_model_name() == "claude-haiku-4-5-20251001"


def test_generate_returns_stdout():
    judge = ClaudeCodeJudge()
    with patch("claude_code_evals.judge._run_claude_judge", return_value=_fake_result("score: 4")):
        result = judge.generate("rate this")
    assert result == "score: 4"


def test_run_claude_judge_parses_text():
    """_run_claude_judge parses stream-json and returns text."""
    assistant_event = json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "4"}]},
        }
    )
    result_event = json.dumps(
        {
            "type": "result",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 2,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        }
    )
    fake_stdout = f"{assistant_event}\n{result_event}\n"

    mock_proc = MagicMock()
    mock_proc.stdout = iter(fake_stdout.splitlines(keepends=True))
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        mock_proc.__enter__ = lambda s: s
        mock_proc.__exit__ = MagicMock(return_value=False)
        result = _run_claude_judge("rate this", model="claude-haiku-4-5-20251001")

    assert result.stdout == "4"
    assert result.input_tokens == 10
    assert result.output_tokens == 2
