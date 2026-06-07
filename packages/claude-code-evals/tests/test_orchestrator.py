from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from claude_code_evals.orchestrator import ScenarioRunResult, run_one
from claude_code_evals.schemas import Config, Scenario


def _make_fixture_scenario(tmp_path: Path) -> tuple[Scenario, Config, Path]:
    wt_src = tmp_path / "fixture_src"
    wt_src.mkdir()
    (wt_src / "README.md").write_text("hello")
    scenario_dir = tmp_path / "evals" / "scenarios" / "test-scenario"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "prompt.md").write_text("What does README say?")

    s = Scenario.model_validate(
        {
            "name": "test-scenario",
            "isolation_mode": "fixture",
            "fixture_dir": str(wt_src),
            "verify": [],
        }
    )
    c = Config.model_validate({"name": "base"})
    evals_root = tmp_path / "evals"
    evals_root.mkdir(exist_ok=True)
    return s, c, evals_root


ASSISTANT_EVENT = json.dumps(
    {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "hello"}]},
    }
)
RESULT_EVENT = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }
)
FAKE_JSONL = f"{ASSISTANT_EVENT}\n{RESULT_EVENT}\n"


def _mock_popen():
    proc = MagicMock()
    proc.stdout = iter(FAKE_JSONL.splitlines(keepends=True))
    proc.returncode = 0
    proc.terminate = MagicMock()
    proc.wait = MagicMock()
    return proc


def test_run_one_returns_scenario_run_result(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert isinstance(result, ScenarioRunResult)
    assert result.scenario.name == "test-scenario"
    assert result.config.name == "base"


def test_run_one_transcript_parsed(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert result.transcript.final_assistant_text == "hello"
    assert result.transcript.input_tokens == 10


def test_run_one_verify_result(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert "success" in result.verify_result


def test_run_one_writes_run_dir(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert result.run_dir.exists()
    assert (result.run_dir / "transcript.json").exists()
    assert (result.run_dir / "metrics.json").exists()


def test_run_one_golden_fixture_raises(tmp_path: Path):
    wt_src = tmp_path / "fs"
    wt_src.mkdir()
    s = Scenario.model_validate(
        {
            "name": "bad",
            "isolation_mode": "fixture",
            "fixture_dir": str(wt_src),
            "verify": [{"kind": "golden", "path": "golden.patch"}],
        }
    )
    c = Config.model_validate({"name": "base"})
    with pytest.raises(ValueError, match="GoldenVerifier.*fixture"):
        run_one(s, c, evals_root=tmp_path)
