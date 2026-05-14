from __future__ import annotations

"""MCP tool registration tests for wiki_scan (Plan 05-04).

Requirements: MCP-01, MCP-03.
Tests for wiki_ingest and wiki_lint remain as stubs for plan-05-05/06.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# wiki_scan tool registration
# ---------------------------------------------------------------------------


def test_wiki_scan_tool_registered() -> None:
    """wiki_scan tool is importable and callable (MCP-01)."""
    from code_wiki_mcp.server import wiki_scan

    assert callable(wiki_scan)
    assert wiki_scan.__name__ == "wiki_scan"


# ---------------------------------------------------------------------------
# WikiScanInput schema validation
# ---------------------------------------------------------------------------


def test_wiki_scan_input_default_vault_path_is_empty() -> None:
    """WikiScanInput defaults to vault_path='' (resolves from env)."""
    from code_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.vault_path == ""


def test_wiki_scan_input_default_no_file_map_is_false() -> None:
    """WikiScanInput defaults to no_file_map=False."""
    from code_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.no_file_map is False


def test_wiki_scan_input_default_max_depth_is_3() -> None:
    """WikiScanInput defaults to max_depth=3."""
    from code_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.max_depth == 3


def test_wiki_scan_input_accepts_custom_vault_path() -> None:
    """WikiScanInput accepts a vault_path string."""
    from code_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput(vault_path="/some/path", no_file_map=True, max_depth=5)
    assert inp.vault_path == "/some/path"
    assert inp.no_file_map is True
    assert inp.max_depth == 5


# ---------------------------------------------------------------------------
# wiki_scan emits progress notifications
# ---------------------------------------------------------------------------


async def test_wiki_scan_emits_progress_notifications() -> None:
    """wiki_scan calls ctx.report_progress at least 2 times (MCP-03)."""
    from code_wiki_agent.commands.scan import ScanResult
    from code_wiki_mcp.server import WikiScanInput, wiki_scan

    mock_result = ScanResult(
        added=["new-pkg"],
        updated=[],
        deleted=[],
        renamed=[],
        errors=[],
        state_gate={"allowed": True, "reason": "clean", "head_commit": "abc"},
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("code_wiki_mcp.server.run_scan", new_callable=AsyncMock) as mock_run_scan:
        mock_run_scan.return_value = mock_result
        await wiki_scan(WikiScanInput(), mock_ctx)

    assert mock_ctx.report_progress.await_count >= 2, (
        f"Expected at least 2 progress notifications, got {mock_ctx.report_progress.await_count}"
    )


async def test_wiki_scan_calls_run_scan_and_returns_output() -> None:
    """wiki_scan calls run_scan and returns WikiScanOutput (MCP-01)."""
    from code_wiki_agent.commands.scan import ScanResult
    from code_wiki_mcp.server import WikiScanInput, WikiScanOutput, wiki_scan

    mock_result = ScanResult(
        added=["alpha", "beta"],
        updated=["gamma"],
        deleted=["old"],
        renamed=[["x", "y"]],
        errors=[],
        state_gate={"allowed": True, "reason": "clean", "head_commit": "abc123"},
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("code_wiki_mcp.server.run_scan", new_callable=AsyncMock) as mock_run_scan:
        mock_run_scan.return_value = mock_result
        result = await wiki_scan(WikiScanInput(), mock_ctx)

    assert isinstance(result, WikiScanOutput)
    assert result.added == ["alpha", "beta"]
    assert result.updated == ["gamma"]
    assert result.deleted == ["old"]
    assert result.renamed == [["x", "y"]]
    assert result.errors == []
    assert result.state_gate["allowed"] is True
