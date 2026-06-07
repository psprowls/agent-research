"""Tests for pytest_plugin fixtures and assertions."""

from __future__ import annotations

from pathlib import Path

from claude_code_evals.orchestrator import ScenarioRunResult
from claude_code_evals.pytest_plugin import assert_scenario
from claude_code_evals.schemas import Config, Scenario
from claude_code_evals.transcript import Transcript


def _minimal_result(tmp_path: Path) -> ScenarioRunResult:
    """Create a minimal ScenarioRunResult for testing."""
    s = Scenario.model_validate({"name": "x", "isolation_mode": "fixture", "fixture_dir": str(tmp_path)})
    c = Config.model_validate({"name": "base"})
    t = Transcript(
        final_assistant_text="done",
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
        turn_count=1,
    )
    return ScenarioRunResult(
        scenario=s,
        config=c,
        scenario_prompt="What is X?",
        run_dir=tmp_path,
        transcript=t,
        metrics={},
        verify_result={"success": True, "verifiers": []},
        verifier_instances=[],
    )


def test_assert_scenario_no_verifiers_passes(tmp_path: Path):
    """assert_scenario with empty verifier_instances runs without error."""
    result = _minimal_result(tmp_path)
    assert_scenario(result)


def test_assert_scenario_with_passing_verifier(tmp_path: Path):
    """assert_scenario with a passing verifier runs without error."""
    from claude_code_evals.verify.base import VerifierBase
    from deepeval.test_case import LLMTestCase

    class AlwaysPass(VerifierBase):
        """A simple verifier that always passes."""

        def measure(self, tc: LLMTestCase) -> float:
            self.score = 1.0
            self.reason = "ok"
            return 1.0

    result = _minimal_result(tmp_path)
    result.verifier_instances = [AlwaysPass(threshold=0.5)]
    assert_scenario(result)  # should not raise
