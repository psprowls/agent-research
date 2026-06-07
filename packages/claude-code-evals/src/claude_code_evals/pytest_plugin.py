"""pytest plugin: fixtures for running eval scenarios in test suites."""

from __future__ import annotations

import os
from pathlib import Path

import deepeval
import pytest
from deepeval.test_case import LLMTestCase

from claude_code_evals.orchestrator import ScenarioRunResult, run_one
from claude_code_evals.schemas import Config, Scenario


@pytest.fixture
def evals_root(request) -> Path:
    """Resolve evals root: --evals-root flag → CLAUDE_CODE_EVALS_ROOT env → cwd."""
    cli_val = request.config.getoption("--evals-root", default=None)
    if cli_val:
        return Path(cli_val)
    env_val = os.environ.get("CLAUDE_CODE_EVALS_ROOT")
    if env_val:
        return Path(env_val)
    return Path.cwd()


@pytest.fixture
def run_scenario(evals_root: Path):
    """Return a callable: run_scenario(name, config=None) → ScenarioRunResult."""

    def _run(scenario_name: str, config: str | None = None) -> ScenarioRunResult:
        scenario_dir = evals_root / "scenarios" / scenario_name
        scenario = Scenario.from_path(scenario_dir / "scenario.yaml")
        config_name = config or (scenario.configs[0] if scenario.configs else "base")
        cfg = Config.from_path(evals_root / "configs" / f"{config_name}.yaml")
        return run_one(scenario, cfg, evals_root=evals_root)

    return _run


def assert_scenario(result: ScenarioRunResult) -> None:
    """Bridge ScenarioRunResult → deepeval assert_test.

    If no verifiers are present, assertion passes trivially.
    Otherwise, runs deepeval.assert_test with all verifiers.
    """
    if not result.verifier_instances:
        return

    test_case = LLMTestCase(
        input=result.scenario_prompt,
        actual_output=result.transcript.final_assistant_text,
    )
    deepeval.assert_test(test_case, result.verifier_instances)


def pytest_addoption(parser) -> None:
    """Register --evals-root CLI flag."""
    parser.addoption("--evals-root", action="store", default=None, help="Path to evals/ directory")


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "eval: mark test as requiring CLAUDE_CODE_RUN_EVALS=1")
    config.addinivalue_line("markers", "integration: mark test as requiring subprocess/real claude binary")
