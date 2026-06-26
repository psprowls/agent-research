"""Role resolution tests for graph_wiki_core.roles."""

from __future__ import annotations

import pytest
from graph_wiki_core import roles
from model_adapter.loader import _GuardedChatBedrockConverse


def test_load_role_config_returns_scanner_with_sweep_candidates() -> None:
    cfg = roles.load_role_config("scanner")
    assert cfg["model_id"]
    assert "sweep_candidates" in cfg


def test_load_role_config_unknown_role_raises() -> None:
    with pytest.raises(KeyError):
        roles.load_role_config("nope-not-a-role")


def test_make_llm_uses_role_model_id() -> None:
    cfg = roles.load_role_config("scanner")
    llm = roles.make_llm("scanner")
    assert isinstance(llm, _GuardedChatBedrockConverse)
    assert llm._model_id_for_errors == cfg["model_id"]


def test_make_llm_model_override() -> None:
    llm = roles.make_llm("scanner", model_override="override.model")
    assert llm._model_id_for_errors == "override.model"


def test_make_llm_honors_workspace_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        roles,
        "_workspace_role_override",
        lambda role: {"model_id": "ws.override", "region": "us-west-2"},
    )
    llm = roles.make_llm("scanner")
    assert llm._model_id_for_errors == "ws.override"
    assert llm.region_name == "us-west-2"
