"""Unit tests for the unified prose-refresh agent's parser and prompt builder."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from graph_wiki_core.commands.prose_refresh import (
    MAX_PROSE_REFRESH_ITERS,
    build_prose_refresh_prompt,
    build_prose_refresh_tools,
    parse_prose_refresher_output,
    run_prose_refresh,
)
from graph_wiki_core.commands.scan_contract import ProseRefreshTask
from langchain_core.tools import tool

ALLOWED = ["## Narrative", "## Purpose"]


def _payload(**over):
    base = {
        "sections": [{"heading": "## Narrative", "replacement_markdown": "New prose."}],
        "file_map_descriptions": {"src/x.py": "does x"},
        "dir_descriptions": {"src": "sources"},
        "overview": "pkg overview",
    }
    base.update(over)
    return json.dumps(base)


def test_parse_happy_path():
    r = parse_prose_refresher_output(_payload(), allowed_headings=ALLOWED)
    assert r.error is None
    assert r.sections == {"## Narrative": "New prose."}
    assert r.file_map_descriptions == {"src/x.py": "does x"}
    assert r.dir_descriptions == {"src": "sources"}
    assert r.overview == "pkg overview"


def test_parse_normalizes_bare_heading_and_tolerates_fence():
    raw = "```json\n" + _payload(sections=[{"heading": "Narrative", "replacement_markdown": "Prose."}]) + "\n```"
    r = parse_prose_refresher_output(raw, allowed_headings=ALLOWED)
    assert r.sections == {"## Narrative": "Prose."}


def test_parse_drops_deterministic_unknown_and_todo_bodies():
    raw = _payload(
        sections=[
            {"heading": "## Referenced in wiki", "replacement_markdown": "hax"},
            {"heading": "## Unknown", "replacement_markdown": "x"},
            {"heading": "## Purpose", "replacement_markdown": "TODO"},
            {"heading": "## Narrative", "replacement_markdown": "   "},
        ]
    )
    r = parse_prose_refresher_output(raw, allowed_headings=ALLOWED)
    assert r.sections == {} and r.error is None


def test_parse_invalid_json_returns_error():
    r = parse_prose_refresher_output("not json", allowed_headings=ALLOWED)
    assert r.sections == {} and r.error is not None


def test_parse_non_object_returns_error():
    r = parse_prose_refresher_output("[1,2]", allowed_headings=ALLOWED)
    assert r.error is not None


def _task(**over):
    base = dict(
        uri="pkg:demo",
        kind="package",
        name="demo",
        page_path="/w/entities/pkg_demo.md",
        graph_path="packages/demo",
        language="python",
        entity_root="packages/demo",
        trigger="diff",
        diff="diff --git a/x b/x\n@@ -1 +1 @@\n+x\n",
        changed_files=["x"],
        page_content="# demo page",
        file_map_rows="| `x.py` | file | — TODO |",
        prose_sections={"## Narrative": "old"},
        graph_context="Language: python",
        owning_short_head=None,
    )
    base.update(over)
    return ProseRefreshTask(**base)


def test_prompt_diff_first():
    prompt = build_prose_refresh_prompt(_task())
    assert prompt.index("@@ -1 +1 @@") < prompt.index("## Narrative")
    assert "Language: python" in prompt and "# demo page" in prompt


def test_prompt_first_fill_variant():
    prompt = build_prose_refresh_prompt(_task(trigger="first_fill", diff=None))
    assert "first fill — no diff" in prompt


def test_prompt_history_rewritten_variant():
    prompt = build_prose_refresh_prompt(_task(trigger="diff", diff=None))
    assert "history rewritten" in prompt


def test_build_prose_refresh_tools_rejects_reads_outside_entity_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    root = repo / "packages" / "demo"
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (repo / "secret.txt").write_text("secret", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    tools = {
        agent_tool.name: agent_tool
        for agent_tool in build_prose_refresh_tools(repo=repo, entity_root="packages/demo", wiki=wiki, graph_tools=[])
    }

    assert "name = 'demo'" in tools["read_repo_file"].invoke({"path": "pyproject.toml"})
    assert tools["read_repo_file"].invoke({"path": "../secret.txt"}).startswith("ERROR: path is outside entity root")
    assert tools["list_repo_tree"].invoke({"path": "."}).startswith("pyproject.toml")


def test_build_prose_refresh_tools_names_and_ordering_with_filtered_graph_tools(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "packages" / "demo").mkdir(parents=True)
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "demo.md").write_text("---\ntitle: demo\n---\n\nBody", encoding="utf-8")

    @tool
    def cg_find(name: str) -> str:
        """Find a graph node."""
        return f"find:{name}"

    @tool
    def cg_callers(name: str) -> str:
        """Not allowed for prose-refresh."""
        return name

    tools = build_prose_refresh_tools(
        repo=repo,
        entity_root="packages/demo",
        wiki=wiki,
        graph_tools=[cg_find, cg_callers],
    )
    names = [agent_tool.name for agent_tool in tools]

    assert names == ["read_repo_file", "list_repo_tree", "read_wiki_page", "cg_find"]


def test_build_prose_refresh_tools_empty_entity_root_falls_back_to_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("root readme", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    tools = {
        agent_tool.name: agent_tool
        for agent_tool in build_prose_refresh_tools(repo=repo, entity_root="", wiki=wiki, graph_tools=[])
    }

    assert tools["read_repo_file"].invoke({"path": "README.md"}) == "root readme"


@pytest.mark.asyncio
async def test_run_prose_refresh_happy_path(monkeypatch, tmp_path: Path) -> None:
    task = _task()
    fake_llm = MagicMock()

    async def fake_loop(**kwargs):
        assert kwargs["llm"] is fake_llm
        assert kwargs["max_iterations"] == MAX_PROSE_REFRESH_ITERS
        assert kwargs["cap_label"] == "prose_refresher"
        return MagicMock(
            status="ok",
            final_text=_payload(),
            error=None,
        )

    monkeypatch.setattr("graph_wiki_core.commands.prose_refresh.run_tool_loop", fake_loop)

    result = await run_prose_refresh(
        llm=fake_llm,
        task=task,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.uri == task.uri
    assert result.sections == {"## Narrative": "New prose."}
    assert result.error is None


@pytest.mark.asyncio
async def test_run_prose_refresh_loop_failure_status_sets_error(monkeypatch, tmp_path: Path) -> None:
    task = _task()

    async def fake_loop(**_kwargs):
        return MagicMock(status="failed", final_text="", error="tool loop blew up")

    monkeypatch.setattr("graph_wiki_core.commands.prose_refresh.run_tool_loop", fake_loop)

    result = await run_prose_refresh(
        llm=MagicMock(),
        task=task,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.uri == task.uri
    assert result.error == "tool loop blew up"
    assert result.sections == {}


@pytest.mark.asyncio
async def test_run_prose_refresh_parse_failure_sets_error_and_uri(monkeypatch, tmp_path: Path) -> None:
    task = _task()

    async def fake_loop(**_kwargs):
        return MagicMock(status="ok", final_text="not json", error=None)

    monkeypatch.setattr("graph_wiki_core.commands.prose_refresh.run_tool_loop", fake_loop)

    result = await run_prose_refresh(
        llm=MagicMock(),
        task=task,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.uri == task.uri
    assert result.sections == {}
    assert result.error is not None


@pytest.mark.asyncio
async def test_run_prose_refresh_preserves_iteration_cap_warning_on_ok_status(monkeypatch, tmp_path: Path) -> None:
    task = _task()

    async def fake_loop(**_kwargs):
        return MagicMock(
            status="ok",
            final_text=_payload(),
            error="prose_refresher hit iteration cap (50) after producing text",
        )

    monkeypatch.setattr("graph_wiki_core.commands.prose_refresh.run_tool_loop", fake_loop)

    result = await run_prose_refresh(
        llm=MagicMock(),
        task=task,
        repo=tmp_path / "repo",
        wiki=tmp_path / "wiki",
        graph_tools=[],
    )

    assert result.uri == task.uri
    assert result.sections == {"## Narrative": "New prose."}
    assert result.error == "prose_refresher hit iteration cap (50) after producing text"
