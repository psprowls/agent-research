"""user_simulator model selection — default vs override."""

from __future__ import annotations

from claude_code_evals.schemas import AutoUser
from claude_code_evals.user_simulator import _USER_SIM_MODEL, AutoUserSimulator


def _cfg(model=None):
    return AutoUser(system_prompt="be brief", stop_on="DONE", model=model)


def test_default_model_when_config_model_none() -> None:
    sim = AutoUserSimulator(_cfg(model=None), task_prompt="t")
    assert sim._llm._model_id_for_errors == _USER_SIM_MODEL


def test_override_model_honored() -> None:
    sim = AutoUserSimulator(_cfg(model="my.model"), task_prompt="t")
    assert sim._llm._model_id_for_errors == "my.model"
