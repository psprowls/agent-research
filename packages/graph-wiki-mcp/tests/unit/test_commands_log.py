"""Package-local MCP tests for the log tool.

CLI presentation coverage moved to packages/graph-wiki-cli/tests/unit/test_commands_log.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_log_result():
    from graph_wiki_core.commands.log import LogResult

    return LogResult(
        status="ok",
        log_path="/wiki/log.md",
        date="2026-05-14",
        op="note",
        title="test entry",
        header="## [2026-05-14] note | test entry",
        detail=None,
    )


def test_wiki_log_input_rejects_missing_required_fields() -> None:
    """WikiLogInput raises ValidationError when op or title are missing."""
    from graph_wiki_mcp.server import WikiLogInput
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WikiLogInput()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_wiki_log_calls_run_log() -> None:
    """wiki_log MCP tool calls run_log with the args from WikiLogInput."""
    from graph_wiki_mcp.server import WikiLogInput, wiki_log

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    mock_result = _make_log_result()

    with patch("graph_wiki_mcp.server.run_log", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_result
        result = await wiki_log(WikiLogInput(op="note", title="test"), mock_ctx)

    mock_fn.assert_awaited_once()
    assert result.status == "ok"
