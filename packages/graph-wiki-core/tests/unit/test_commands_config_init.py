"""Non-interactive gw config init: every answer lands through set/hooks paths."""

import pytest
from graph_wiki_core.commands.config import InitAnswers, run_config_init
from workspace_io import manifest


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    manifest.write(tmp_path / ".graph-wiki.yaml", {"version": 2, "initialized_at": "2026-07-04", "plugins": []})
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    return tmp_path


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / ".claude").mkdir(parents=True)
    return r


@pytest.fixture
def scripts_dir(tmp_path):
    d = tmp_path / "examples"
    d.mkdir()
    for name in (
        "post-task-complete-revalidate.sh",
        "stop-revalidate-user-gates.sh",
        "session-end-transcript-capture.sh",
    ):
        (d / name).write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    return d


async def test_guided_routing_and_at_end(workspace, repo, scripts_dir):
    result = await run_config_init(
        InitAnswers(model_routing="guided", commit_strategy="at-end", gates=False, transcript=False, write_env=False),
        repo_root=repo,
        scripts_dir=scripts_dir,
    )
    data = manifest.read(workspace / ".graph-wiki.yaml")
    assert data["workflow"]["model_routing"] == {"mechanical": "haiku", "standard": "sonnet", "frontier": "inherit"}
    assert data["workflow"]["commit_strategy"] == "at-end"
    assert result.actions  # human-readable log of what was applied


async def test_fixed_routing_and_off(workspace, repo, scripts_dir):
    await run_config_init(InitAnswers(model_routing="fixed:sonnet"), repo_root=repo, scripts_dir=scripts_dir)
    data = manifest.read(workspace / ".graph-wiki.yaml")
    assert set(data["workflow"]["model_routing"].values()) == {"sonnet"}
    await run_config_init(InitAnswers(model_routing="off"), repo_root=repo, scripts_dir=scripts_dir)
    assert manifest.read(workspace / ".graph-wiki.yaml")["workflow"]["model_routing"] == {}


async def test_none_answers_change_nothing(workspace, repo, scripts_dir):
    before = (workspace / ".graph-wiki.yaml").read_text(encoding="utf-8")
    result = await run_config_init(InitAnswers(), repo_root=repo, scripts_dir=scripts_dir)
    assert (workspace / ".graph-wiki.yaml").read_text(encoding="utf-8") == before
    assert result.actions == []


async def test_gates_and_env_block(workspace, repo, scripts_dir):
    import json

    await run_config_init(InitAnswers(gates=True, write_env=True), repo_root=repo, scripts_dir=scripts_dir)
    s = json.loads((repo / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
    assert s["env"]["GRAPH_WIKI_WORKSPACE"] == str(workspace)
    assert "EnterPlanMode" in s["permissions"]["deny"]
