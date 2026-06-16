from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import typer
from typer.testing import CliRunner

runner = CliRunner()


def test_archive_command_registered() -> None:
    from graph_wiki_cli.cli import app

    root = typer.main.get_command(app)
    assert "archive" in root.commands


def test_archive_json_exit_0_and_shape() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.archive_all import ArchiveAllResult
    from graph_wiki_core.commands.wiki_archive import WikiArchiveResult
    from graph_wiki_core.commands.work import WorkArchiveResult

    mock_result = ArchiveAllResult(
        dry_run=False,
        wiki=WikiArchiveResult(dry_run=False, moved=[], skipped=[]),
        work=WorkArchiveResult(dry_run=False, moved=[], skipped=[], repointed=[]),
        errors=[],
    )
    with patch("graph_wiki_cli.cli.run_archive_all", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["archive", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert set(data) == {"dry_run", "wiki", "work", "errors"}


def test_archive_exit_1_when_error_captured() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.archive_all import ArchiveAllResult
    from graph_wiki_core.commands.work import WorkArchiveResult

    mock_result = ArchiveAllResult(
        dry_run=False,
        wiki=None,
        work=WorkArchiveResult(dry_run=False, moved=[], skipped=[], repointed=[]),
        errors=[{"command": "wiki", "error": "boom"}],
    )
    with patch("graph_wiki_cli.cli.run_archive_all", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["archive"])

    assert result.exit_code == 1
