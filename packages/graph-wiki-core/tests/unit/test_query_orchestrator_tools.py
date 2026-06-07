"""Planning-tool tests for the query orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.tools import tool


def _page(path: Path, title: str, kind: str = "concept", body: str = "Body text") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\nkind: {kind}\n---\n\n{body}", encoding="utf-8")
    return path


def test_build_orchestrator_context_includes_initial_candidates_and_capabilities(tmp_path: Path) -> None:
    from graph_wiki_core.commands.query_orchestrator import InitialCandidate, build_orchestrator_context

    wiki = tmp_path / "wiki"
    page = _page(wiki / "concepts" / "ownership.md", "Ownership", body="Ownership page body")
    candidate = InitialCandidate(
        path="concepts/ownership.md",
        score=0.75,
        excerpt="Ownership excerpt",
        freshness="fresh",
        staleness_reason=None,
    )

    context = build_orchestrator_context(
        query="Who owns query planning?",
        wiki=wiki,
        repo_root=tmp_path / "repo",
        initial_candidates=[candidate],
        graph_tools=[],
    )

    assert context.query == "Who owns query planning?"
    assert context.wiki_root == wiki.resolve()
    assert context.repo_root == (tmp_path / "repo").resolve()
    assert context.initial_candidates == (candidate,)
    assert context.graph_tools_available is False
    assert "librarian" in context.worker_capabilities
    assert "code_reader" in context.worker_capabilities
    assert "answer_markdown" in context.answer_contract
    assert page.exists()


def test_build_orchestrator_tools_exposes_bounded_wiki_tools_and_capabilities(tmp_path: Path) -> None:
    from graph_wiki_core.commands.query_orchestrator import build_orchestrator_tools

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", "Ownership", body="Ownership page body")
    (tmp_path / "secret.md").write_text("secret", encoding="utf-8")

    tools = {query_tool.name: query_tool for query_tool in build_orchestrator_tools(wiki=wiki, graph_tools=[])}

    assert set(tools) == {"read_wiki_page", "search_wiki", "list_worker_capabilities"}
    assert tools["read_wiki_page"].invoke({"path": "concepts/ownership.md"}).startswith("# Ownership")
    assert tools["read_wiki_page"].invoke({"path": "../secret.md"}).startswith("ERROR: path is outside wiki")

    search_rows = json.loads(tools["search_wiki"].invoke({"query": "ownership", "kind": "concept", "top_k": 5}))
    assert [row["path"] for row in search_rows] == ["concepts/ownership.md"]

    capabilities = json.loads(tools["list_worker_capabilities"].invoke({}))
    assert sorted(capabilities) == ["code_reader", "librarian"]
    assert "target_paths_or_hints" in capabilities["code_reader"]["required_fields"]


def test_build_orchestrator_tools_filters_graph_tools_to_find_and_describe(tmp_path: Path) -> None:
    from graph_wiki_core.commands.query_orchestrator import build_orchestrator_tools

    @tool
    def cg_find(name: str) -> str:
        """Find a graph node."""
        return name

    @tool
    def cg_describe(kind: str, identifier: str) -> str:
        """Describe a graph node."""
        return f"{kind}:{identifier}"

    @tool
    def cg_callers(name: str) -> str:
        """Find graph callers."""
        return name

    tools = {
        query_tool.name: query_tool
        for query_tool in build_orchestrator_tools(
            wiki=tmp_path / "wiki",
            graph_tools=[cg_find, cg_describe, cg_callers],
        )
    }

    assert "cg_find" in tools
    assert "cg_describe" in tools
    assert "cg_callers" not in tools


def test_build_orchestrator_tools_does_not_expose_direct_repo_file_reads(tmp_path: Path) -> None:
    from graph_wiki_core.commands.query_orchestrator import build_orchestrator_tools

    tools = build_orchestrator_tools(wiki=tmp_path / "wiki", graph_tools=[])

    forbidden_names = {"read_repo_file", "read_source_file", "read_file_bounded", "read_source_chunk"}
    assert forbidden_names.isdisjoint({query_tool.name for query_tool in tools})
