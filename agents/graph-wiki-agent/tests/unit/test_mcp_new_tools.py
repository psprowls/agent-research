from __future__ import annotations

"""MCP tool registration tests for wiki_scan (Plan 05-04), wiki_ingest (Plan 05-05), and wiki_bootstrap (Phase 18-02).

Requirements: MCP-01, MCP-03, CMD-02.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# wiki_scan tool registration
# ---------------------------------------------------------------------------


def test_wiki_scan_tool_registered() -> None:
    """wiki_scan tool is importable and callable (MCP-01)."""
    from graph_wiki_agent.mcp.server import wiki_scan

    assert callable(wiki_scan)
    assert wiki_scan.__name__ == "wiki_scan"


# ---------------------------------------------------------------------------
# WikiScanInput schema validation
# ---------------------------------------------------------------------------


def test_wiki_scan_input_default_workspace_path_is_empty() -> None:
    """WikiScanInput defaults to workspace_path='' (resolves from env)."""
    from graph_wiki_agent.mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.workspace_path == ""


def test_wiki_scan_input_default_no_file_map_is_false() -> None:
    """WikiScanInput defaults to no_file_map=False."""
    from graph_wiki_agent.mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.no_file_map is False


def test_wiki_scan_input_default_max_depth_is_3() -> None:
    """WikiScanInput defaults to max_depth=3."""
    from graph_wiki_agent.mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.max_depth == 3


def test_wiki_scan_input_accepts_custom_workspace_path() -> None:
    """WikiScanInput accepts a workspace_path string."""
    from graph_wiki_agent.mcp.server import WikiScanInput

    inp = WikiScanInput(workspace_path="/some/path", no_file_map=True, max_depth=5)
    assert inp.workspace_path == "/some/path"
    assert inp.no_file_map is True
    assert inp.max_depth == 5


# ---------------------------------------------------------------------------
# wiki_scan emits progress notifications
# ---------------------------------------------------------------------------


async def test_wiki_scan_emits_progress_notifications() -> None:
    """wiki_scan calls ctx.report_progress at least 2 times (MCP-03)."""
    from graph_wiki_agent.commands.scan import ScanResult
    from graph_wiki_agent.mcp.server import WikiScanInput, wiki_scan

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

    with patch("graph_wiki_agent.mcp.server.run_scan", new_callable=AsyncMock) as mock_run_scan:
        mock_run_scan.return_value = mock_result
        await wiki_scan(WikiScanInput(), mock_ctx)

    assert mock_ctx.report_progress.await_count >= 2, (
        f"Expected at least 2 progress notifications, got {mock_ctx.report_progress.await_count}"
    )


async def test_wiki_scan_calls_run_scan_and_returns_output() -> None:
    """wiki_scan calls run_scan and returns WikiScanOutput (MCP-01)."""
    from graph_wiki_agent.commands.scan import ScanResult
    from graph_wiki_agent.mcp.server import WikiScanInput, WikiScanOutput, wiki_scan

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

    with patch("graph_wiki_agent.mcp.server.run_scan", new_callable=AsyncMock) as mock_run_scan:
        mock_run_scan.return_value = mock_result
        result = await wiki_scan(WikiScanInput(), mock_ctx)

    assert isinstance(result, WikiScanOutput)
    assert result.added == ["alpha", "beta"]
    assert result.updated == ["gamma"]
    assert result.deleted == ["old"]
    assert result.renamed == [["x", "y"]]
    assert result.errors == []
    assert result.state_gate["allowed"] is True


# ---------------------------------------------------------------------------
# wiki_ingest tool registration (Plan 05-05)
# ---------------------------------------------------------------------------


def test_wiki_ingest_tool_registered() -> None:
    """wiki_ingest tool is importable and callable (MCP-01)."""
    from graph_wiki_agent.mcp.server import wiki_ingest

    assert callable(wiki_ingest)
    assert wiki_ingest.__name__ == "wiki_ingest"


def test_wiki_ingest_input_type_discriminator() -> None:
    """WikiIngestInput has a type field with Literal['source','work-item'] (D-04)."""
    from graph_wiki_agent.mcp.server import WikiIngestInput
    import typing

    inp_source = WikiIngestInput(type="source", source_path="/some/file.md")
    assert inp_source.type == "source"

    inp_work = WikiIngestInput(type="work-item", frontmatter="title: X", body="Body.")
    assert inp_work.type == "work-item"


async def test_wiki_ingest_dispatches_to_source() -> None:
    """wiki_ingest with type='source' calls run_ingest_source, not run_ingest_work_item."""
    from graph_wiki_agent.commands.ingest import IngestResult
    from graph_wiki_agent.mcp.server import WikiIngestInput, wiki_ingest

    mock_result = IngestResult(
        status="ok",
        page_path="concepts/foo.md",
        slug="foo",
        title="Foo",
        page_type="concept",
        source_path="/some/file.md",
        cross_refs_updated=1,
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with (
        patch("graph_wiki_agent.mcp.server.run_ingest_source", new_callable=AsyncMock) as mock_source,
        patch("graph_wiki_agent.mcp.server.run_ingest_work_item", new_callable=AsyncMock) as mock_work_item,
    ):
        mock_source.return_value = mock_result
        await wiki_ingest(WikiIngestInput(type="source", source_path="/some/file.md"), mock_ctx)

    mock_source.assert_called_once()
    mock_work_item.assert_not_called()


async def test_wiki_ingest_dispatches_to_work_item() -> None:
    """wiki_ingest with type='work-item' calls run_ingest_work_item, not run_ingest_source."""
    from graph_wiki_agent.commands.ingest import IngestResult
    from graph_wiki_agent.mcp.server import WikiIngestInput, wiki_ingest

    mock_result = IngestResult(
        status="ok",
        page_path="work/2026-05-14-fix-bug.md",
        slug="fix-bug",
        title="Fix Bug",
        page_type="work",
        source_path="",
        cross_refs_updated=1,
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with (
        patch("graph_wiki_agent.mcp.server.run_ingest_source", new_callable=AsyncMock) as mock_source,
        patch("graph_wiki_agent.mcp.server.run_ingest_work_item", new_callable=AsyncMock) as mock_work_item,
    ):
        mock_work_item.return_value = mock_result
        await wiki_ingest(
            WikiIngestInput(type="work-item", frontmatter="title: Fix Bug", body="Body."),
            mock_ctx,
        )

    mock_work_item.assert_called_once()
    mock_source.assert_not_called()


async def test_wiki_ingest_emits_progress() -> None:
    """wiki_ingest calls ctx.report_progress at least 2 times (MCP-03)."""
    from graph_wiki_agent.commands.ingest import IngestResult
    from graph_wiki_agent.mcp.server import WikiIngestInput, wiki_ingest

    mock_result = IngestResult(
        status="ok",
        page_path="concepts/bar.md",
        slug="bar",
        title="Bar",
        page_type="concept",
        source_path="/path/bar.md",
        cross_refs_updated=1,
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("graph_wiki_agent.mcp.server.run_ingest_source", new_callable=AsyncMock) as mock_source:
        mock_source.return_value = mock_result
        await wiki_ingest(WikiIngestInput(type="source", source_path="/path/bar.md"), mock_ctx)

    assert mock_ctx.report_progress.await_count >= 2, (
        f"Expected >= 2 progress notifications, got {mock_ctx.report_progress.await_count}"
    )


# ---------------------------------------------------------------------------
# wiki_bootstrap tool registration (Phase 18-02, CMD-02)
# ---------------------------------------------------------------------------


def test_wiki_bootstrap_tool_registered() -> None:
    """wiki_bootstrap tool is importable and callable (CMD-02)."""
    from graph_wiki_agent.mcp.server import wiki_bootstrap

    assert callable(wiki_bootstrap)
    assert wiki_bootstrap.__name__ == "wiki_bootstrap"


def test_wiki_bootstrap_input_rejects_missing_required_fields() -> None:
    """WikiBootstrapInput raises ValidationError when topic or tool are missing."""
    from pydantic import ValidationError

    from graph_wiki_agent.mcp.server import WikiBootstrapInput

    with pytest.raises(ValidationError):
        WikiBootstrapInput()  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_wiki_bootstrap_calls_run_init() -> None:
    """wiki_bootstrap MCP tool calls run_init with passed args."""
    from pathlib import Path as _Path

    from graph_wiki_agent.commands.init import InitResult
    from graph_wiki_agent.mcp.server import WikiBootstrapInput, wiki_bootstrap

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    workspace = _Path("/tmp/workspace")
    wiki = workspace / "wiki"
    mock_result = InitResult(
        status="ok",
        wiki_path=str(wiki),
        repo_path=str(workspace),
        topic="test-topic",
        tool="claude-code",
        date="2026-05-14",
        installed_files=["CLAUDE.md", "index.md", "log.md"],
        page_templates_copied=3,
        layers={},
        raw_path=str(workspace / "raw"),
        work_path=str(workspace / "work"),
    )

    with patch("graph_wiki_agent.mcp.server.run_init", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_result
        result = await wiki_bootstrap(
            WikiBootstrapInput(topic="test", tool="claude-code"), mock_ctx
        )

    mock_fn.assert_awaited_once()
    assert result.status == "ok"


# ---------------------------------------------------------------------------
# wiki_lint tool registration (Plan 05-06)
# ---------------------------------------------------------------------------


def test_wiki_lint_tool_registered() -> None:
    """wiki_lint tool is importable and callable (MCP-01)."""
    from graph_wiki_agent.mcp.server import wiki_lint

    assert callable(wiki_lint)
    assert wiki_lint.__name__ == "wiki_lint"


def test_wiki_lint_input_schema() -> None:
    """WikiLintInput has workspace_path, stale_days, log_gap_days with correct defaults."""
    from graph_wiki_agent.mcp.server import WikiLintInput

    inp = WikiLintInput()
    assert inp.workspace_path == ""
    assert inp.stale_days == 90
    assert inp.log_gap_days == 14


async def test_wiki_lint_emits_progress() -> None:
    """wiki_lint calls ctx.report_progress at least 2 times (MCP-03)."""
    from graph_wiki_agent.commands.lint import LintResult
    from graph_wiki_agent.mcp.server import WikiLintInput, wiki_lint

    mock_result = LintResult(
        wiki="/fake/wiki",
        total_pages=5,
        orphans=[],
        broken_links=[],
        stale=[],
        missing_frontmatter=[],
        duplicate_titles={},
        log_gap=None,
        code_drift={"skipped": True},
        container_drift=[],
        source_sync_drift=[],
        file_map_drift=[],
        package_sync_drift=[],
        domain_placement=[],
        workflow_hints=[],
        dependency_layer=None,
        semantic_findings={"page_quality": [], "adr_chain": [], "stale_claims": []},
        errors=[],
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("graph_wiki_agent.mcp.server.run_lint", new_callable=AsyncMock) as mock_run_lint:
        mock_run_lint.return_value = mock_result
        await wiki_lint(WikiLintInput(), mock_ctx)

    assert mock_ctx.report_progress.await_count >= 2, (
        f"Expected >= 2 progress notifications, got {mock_ctx.report_progress.await_count}"
    )
