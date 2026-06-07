from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _page(path: Path, title: str | None = None, kind: str | None = None, **frontmatter: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, str] = {}
    if title is not None:
        metadata["title"] = title
    if kind is not None:
        metadata["kind"] = kind
    metadata.update(frontmatter)
    yaml_lines = [f"{key}: {value}" for key, value in metadata.items()]
    path.write_text("---\n" + "\n".join(yaml_lines) + "\n---\n\nBody text for " + path.stem, encoding="utf-8")
    return path


def test_build_reasoner_tools_wires_source_chunk_and_allowed_graph_tools(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import build_reasoner_tools
    from langchain_core.tools import tool

    @tool
    def cg_find(name: str) -> str:
        """Find a graph node."""
        return name

    @tool
    def cg_callers(name: str) -> str:
        """Find callers."""
        return name

    tools = {
        reasoner_tool.name: reasoner_tool
        for reasoner_tool in build_reasoner_tools(
            wiki=tmp_path / "wiki",
            chunks=["one", "two"],
            graph_tools=[cg_find, cg_callers],
        )
    }

    assert tools["read_source_chunk"].invoke({"index": 1}) == "two"
    assert "ERROR" in tools["read_source_chunk"].invoke({"index": 4})
    assert "read_wiki_page" in tools
    assert "search_wiki_catalog" in tools
    assert "cg_find" in tools
    assert "cg_callers" not in tools


@pytest.mark.asyncio
async def test_run_proposal_reasoner_handles_one_tool_call(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import run_proposal_reasoner

    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "ownership.md", "Ownership", "concept")
    source_page = wiki / "sources" / "spec.md"
    _page(source_page, "Spec", "source")

    first = MagicMock(
        content="",
        tool_calls=[{"name": "read_wiki_page", "args": {"path": "concepts/ownership.md"}, "id": "call_1"}],
    )
    second = MagicMock(content="Candidate: update Ownership", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

    with patch("graph_wiki_core.commands.proposal_reasoner.make_llm", return_value=llm):
        result = await run_proposal_reasoner(
            wiki=wiki,
            source_path=tmp_path / "source.md",
            source_text="Full source text",
            source_page_path=source_page,
            source_page_text=source_page.read_text(encoding="utf-8"),
            entity_uri=None,
            entity_stem=None,
            graph_tools=[],
        )

    assert result.status == "ok"
    assert result.analysis == "Candidate: update Ownership"
    assert llm.ainvoke.call_count == 2
    assert llm.bind_tools.call_count == 1
