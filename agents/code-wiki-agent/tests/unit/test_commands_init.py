from __future__ import annotations

"""Unit tests for the init command (Plan 05-01).

Requirements covered: CMD-01.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_init_result(wiki: Path, workspace: Path):
    from code_wiki_agent.commands.init import InitResult

    return InitResult(
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


# ---------------------------------------------------------------------------
# init_wiki creates raw/ and work/
# ---------------------------------------------------------------------------


def test_init_wiki_creates_raw_and_work_dirs(tmp_path: Path) -> None:
    """init_wiki() creates raw/ and work/ as siblings of the wiki dir."""
    from vault_io.init_vault import init_wiki

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"

    init_wiki(
        wiki_path=wiki,
        repo_path=workspace,
        topic="test",
        tool="claude-code",
        force=True,
        non_interactive=True,
    )

    assert (workspace / "raw").is_dir(), "raw/ directory must be created"
    assert (workspace / "work").is_dir(), "work/ directory must be created"


# ---------------------------------------------------------------------------
# run_init returns InitResult with raw_path and work_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_init_returns_init_result_with_raw_work(tmp_path: Path) -> None:
    """run_init() returns an InitResult whose raw_path and work_path point at created dirs."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"

    with patch(
        "code_wiki_agent.commands.init.resolve_wiki_and_repo",
        return_value=(wiki, workspace),
    ):
        from code_wiki_agent.commands.init import run_init

        result = await run_init(
            topic="my-topic", tool="claude-code", force=True, vault_path=None
        )

    assert result.status == "ok"
    assert Path(result.raw_path).name == "raw"
    assert Path(result.work_path).name == "work"
    assert Path(result.raw_path).is_dir()
    assert Path(result.work_path).is_dir()


# ---------------------------------------------------------------------------
# CLI --json output
# ---------------------------------------------------------------------------


def test_cli_init_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI init --json emits valid JSON with required keys."""
    from typer.testing import CliRunner

    from code_wiki_agent.cli import app

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    mock_result = _make_init_result(wiki, workspace)
    monkeypatch.setattr(
        "code_wiki_agent.cli.run_init",
        AsyncMock(return_value=mock_result),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["init", "--topic", "foo", "--tool", "claude-code", "--json"],
    )
    assert result.exit_code == 0, f"Unexpected exit: {result.output}"
    parsed = json.loads(result.output)
    assert parsed["status"] == "ok"
    assert parsed["topic"] == "test-topic"
    assert "raw_path" in parsed
    assert "work_path" in parsed


# ---------------------------------------------------------------------------
# MCP WikiInitInput validation
# ---------------------------------------------------------------------------


def test_wiki_init_input_rejects_missing_required_fields() -> None:
    """WikiInitInput raises ValidationError when topic or tool are missing."""
    from pydantic import ValidationError

    from code_wiki_mcp.server import WikiInitInput

    with pytest.raises(ValidationError):
        WikiInitInput()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# MCP wiki_init calls run_init
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wiki_init_calls_run_init() -> None:
    """wiki_init MCP tool calls run_init with passed args."""
    from code_wiki_mcp.server import WikiInitInput, wiki_init
    from pathlib import Path as _Path

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    workspace = _Path("/tmp/workspace")
    wiki = workspace / "wiki"
    mock_result = _make_init_result(wiki, workspace)

    with patch("code_wiki_mcp.server.run_init", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = mock_result
        result = await wiki_init(
            WikiInitInput(topic="test", tool="claude-code"), mock_ctx
        )

    mock_fn.assert_awaited_once()
    assert result.status == "ok"
