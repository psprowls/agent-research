from __future__ import annotations

"""Unit tests for the wiki_query MCP tool schema, validation, and progress behavior.

Requirements covered: MCP-02, MCP-04, MCP-06.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError


def test_wiki_query_tool_registered() -> None:
    """wiki_query tool is importable and callable (MCP-02)."""
    from code_wiki_mcp.server import wiki_query

    assert callable(wiki_query)
    assert wiki_query.__name__ == "wiki_query"


def test_wiki_query_input_default_top_k_is_5() -> None:
    """WikiQueryInput defaults to top_k=5."""
    from code_wiki_mcp.server import WikiQueryInput

    inp = WikiQueryInput(query="test query")
    assert inp.top_k == 5


def test_wiki_query_input_default_vault_path_is_empty() -> None:
    """WikiQueryInput defaults to vault_path='' (empty -> resolve from env)."""
    from code_wiki_mcp.server import WikiQueryInput

    inp = WikiQueryInput(query="test query")
    assert inp.vault_path == ""


def test_wiki_query_input_rejects_out_of_range_top_k() -> None:
    """WikiQueryInput rejects top_k > 10 with ValidationError (MCP-04)."""
    from code_wiki_mcp.server import WikiQueryInput

    with pytest.raises(ValidationError):
        WikiQueryInput(query="test query", top_k=11)


def test_wiki_query_input_rejects_top_k_too_low() -> None:
    """WikiQueryInput rejects top_k < 3 with ValidationError (MCP-04)."""
    from code_wiki_mcp.server import WikiQueryInput

    with pytest.raises(ValidationError):
        WikiQueryInput(query="test query", top_k=2)


def test_wiki_query_input_rejects_missing_query() -> None:
    """WikiQueryInput requires query field (MCP-04)."""
    from code_wiki_mcp.server import WikiQueryInput

    with pytest.raises(ValidationError):
        WikiQueryInput()  # type: ignore[call-arg]


async def test_wiki_query_calls_run_query_and_returns_output() -> None:
    """wiki_query calls run_query and returns WikiQueryOutput (CLI-03 single source of truth)."""
    from code_wiki_mcp.server import WikiQueryInput, WikiQueryOutput, wiki_query
    from code_wiki_agent.commands.query import QueryResult

    mock_result = QueryResult(
        answer="The SubagentPool manages concurrent fan-out.",
        citations=["SubagentPool"],
        pages_drilled=3,
        search_scores={
            "concepts/subagent-pool.md": {"bm25": 0.9, "embed": 0.85, "rrf": 0.03}
        },
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("code_wiki_mcp.server.run_query", new_callable=AsyncMock) as mock_run_query:
        mock_run_query.return_value = mock_result

        result = await wiki_query(WikiQueryInput(query="What does SubagentPool do?"), mock_ctx)

    assert isinstance(result, WikiQueryOutput)
    assert result.answer == "The SubagentPool manages concurrent fan-out."
    assert result.citations == ["SubagentPool"]
    assert result.pages_drilled == 3
    assert "concepts/subagent-pool.md" in result.search_scores
    mock_run_query.assert_awaited_once()


async def test_progress_called_at_start_and_end() -> None:
    """ctx.report_progress called at least twice (start + end) during wiki_query (MCP-06)."""
    from code_wiki_mcp.server import WikiQueryInput, wiki_query
    from code_wiki_agent.commands.query import QueryResult

    mock_result = QueryResult(
        answer="Answer text.",
        citations=[],
        pages_drilled=2,
        search_scores={},
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("code_wiki_mcp.server.run_query", new_callable=AsyncMock) as mock_run_query:
        mock_run_query.return_value = mock_result
        await wiki_query(WikiQueryInput(query="test"), mock_ctx)

    assert mock_ctx.report_progress.await_count >= 2


async def test_wiki_query_propagates_run_query_runtime_error() -> None:
    """wiki_query propagates RuntimeError from run_query (FastMCP wraps at JSON-RPC layer)."""
    from code_wiki_mcp.server import WikiQueryInput, wiki_query

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("code_wiki_mcp.server.run_query", new_callable=AsyncMock) as mock_run_query:
        mock_run_query.side_effect = RuntimeError("Vault not found")
        with pytest.raises(RuntimeError, match="Vault not found"):
            await wiki_query(WikiQueryInput(query="test"), mock_ctx)
