from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from claude_code_evals.orchestrator import ScenarioRunResult, run_one
from claude_code_evals.runner import RunResult
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


@pytest.fixture(autouse=True)
def _oauth_token(monkeypatch):
    """Real runs require a subscription token; provide a fake one for the mocked-subprocess tests."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-fake")


def _mock_popen(jsonl: str = FAKE_JSONL, returncode: int = 0):
    proc = MagicMock()
    proc.stdout = iter(jsonl.splitlines(keepends=True))
    proc.returncode = returncode
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


def test_run_one_missing_oauth_token_fails_fast(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with pytest.raises(RuntimeError, match="setup-token"):
        run_one(s, c, evals_root=evals_root)


def test_run_one_infra_error_surfaces_reason_and_skips_judge(tmp_path: Path):
    """A crashed run (no result event) is recorded as failure with a reason; the LLM judge is skipped."""
    scenario_dir = tmp_path / "evals" / "scenarios" / "test-scenario"
    scenario_dir.mkdir(parents=True)
    s = Scenario.model_validate(
        {
            "name": "test-scenario",
            "isolation_mode": "fixture",
            "fixture_dir": str(tmp_path / "fixture_src"),
            "verify": [{"kind": "rubric", "path": "rubric.md"}],
        }
    )
    (scenario_dir / "rubric.md").write_text("score it")
    (tmp_path / "fixture_src").mkdir(exist_ok=True)
    c = Config.model_validate({"name": "base"})
    evals_root = tmp_path / "evals"

    crash_proc = _mock_popen(jsonl="error: unknown option '--config-dir'\n", returncode=1)
    with patch("subprocess.Popen", return_value=crash_proc):
        result = run_one(s, c, evals_root=evals_root)

    assert result.verify_result["success"] is False
    meta = json.loads((result.run_dir / "meta.json").read_text())
    assert meta["final_status"] == "error_no_result"
    assert "unknown option" in (meta["error_reason"] or "")
    # judge must not run on a crashed transcript
    assert result.verify_result.get("verifiers") == []


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


# --- Mode dispatch tests ---


def _base_scenario(**overrides) -> Scenario:
    base = {
        "name": "test-scenario",
        "isolation_mode": "fixture",
        "fixture_dir": "fixtures/",
        "verify": [],
    }
    base.update(overrides)
    return Scenario.model_validate(base)


def _base_config() -> Config:
    return Config.model_validate({"name": "base", "model": "claude-sonnet-4-6"})


def _empty_run_result(status: str = "success") -> RunResult:
    return RunResult(final_status=status, budget_exceeded=False, wall_seconds=0.1)


def test_orchestrator_calls_run_one_shot_for_headless_no_auto_user(tmp_path):
    scenario = _base_scenario()
    config = _base_config()
    (tmp_path / "scenarios" / "test-scenario").mkdir(parents=True)
    (tmp_path / "scenarios" / "test-scenario" / "prompt.md").write_text("Do X")

    with (
        patch("claude_code_evals.orchestrator.FixtureIsolation") as MockIso,
        patch("claude_code_evals.orchestrator.run_one_shot", return_value=(_empty_run_result(), "")) as mock_shot,
        patch("claude_code_evals.orchestrator.run_multi_turn") as mock_multi,
        patch("claude_code_evals.orchestrator.run_interactive") as mock_interactive,
    ):
        iso_instance = MagicMock()
        iso_instance.__enter__ = MagicMock(return_value=iso_instance)
        iso_instance.__exit__ = MagicMock(return_value=False)
        iso_instance.worktree_path = tmp_path
        iso_instance.cfg_dir = tmp_path
        iso_instance.oauth_token = "tok"
        MockIso.return_value = iso_instance

        run_one(scenario, config, evals_root=tmp_path)

    mock_shot.assert_called_once()
    mock_multi.assert_not_called()
    mock_interactive.assert_not_called()


def test_orchestrator_calls_run_interactive_for_interactive_mode(tmp_path):
    scenario = _base_scenario(mode="interactive")
    config = _base_config()
    (tmp_path / "scenarios" / "test-scenario").mkdir(parents=True)
    (tmp_path / "scenarios" / "test-scenario" / "prompt.md").write_text("Do X")

    with (
        patch("claude_code_evals.orchestrator.FixtureIsolation") as MockIso,
        patch("claude_code_evals.orchestrator.run_one_shot") as mock_shot,
        patch(
            "claude_code_evals.orchestrator.run_interactive",
            return_value=(_empty_run_result("completed_interactive"), ""),
        ) as mock_interactive,
    ):
        iso_instance = MagicMock()
        iso_instance.__enter__ = MagicMock(return_value=iso_instance)
        iso_instance.__exit__ = MagicMock(return_value=False)
        iso_instance.worktree_path = tmp_path
        iso_instance.cfg_dir = tmp_path
        iso_instance.oauth_token = "tok"
        MockIso.return_value = iso_instance

        result = run_one(scenario, config, evals_root=tmp_path)

    mock_interactive.assert_called_once()
    mock_shot.assert_not_called()
    assert result.final_status == "completed_interactive"


def test_orchestrator_calls_run_multi_turn_when_auto_user_set(tmp_path):
    auto_user_yaml = tmp_path / "auto_user.yaml"
    auto_user_yaml.write_text(
        "model: claude-haiku-4-5-20251001\nmax_replies: 3\nstop_on: '<DONE>'\nsystem_prompt: Drive.\n"
    )
    scenario = _base_scenario(auto_user=str(auto_user_yaml))
    config = _base_config()
    (tmp_path / "scenarios" / "test-scenario").mkdir(parents=True)
    (tmp_path / "scenarios" / "test-scenario" / "prompt.md").write_text("Do X")

    with (
        patch("claude_code_evals.orchestrator.FixtureIsolation") as MockIso,
        patch("claude_code_evals.orchestrator.run_one_shot") as mock_shot,
        patch("claude_code_evals.orchestrator.run_multi_turn", return_value=(_empty_run_result(), "")) as mock_multi,
    ):
        iso_instance = MagicMock()
        iso_instance.__enter__ = MagicMock(return_value=iso_instance)
        iso_instance.__exit__ = MagicMock(return_value=False)
        iso_instance.worktree_path = tmp_path
        iso_instance.cfg_dir = tmp_path
        iso_instance.oauth_token = "tok"
        MockIso.return_value = iso_instance

        run_one(scenario, config, evals_root=tmp_path)

    mock_multi.assert_called_once()
    mock_shot.assert_not_called()
