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


def test_lint_command_registered() -> None:
    from graph_wiki_cli.cli import app

    root = typer.main.get_command(app)
    assert "lint" in root.commands


def test_lint_json_exit_0_when_clean() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.lint import LintResult
    from graph_wiki_core.commands.lint_all import LintAllResult
    from graph_wiki_core.commands.work import WorkLintResult

    mock_result = LintAllResult(
        wiki=LintResult(wiki="w", total_pages=1),
        work=WorkLintResult(total_items=0, findings=[]),
        errors=[],
    )
    with patch("graph_wiki_cli.cli.run_lint_all", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["lint", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert set(data) == {"wiki", "work", "errors"}


def test_lint_exit_1_on_work_error_finding() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.lint import LintResult
    from graph_wiki_core.commands.lint_all import LintAllResult
    from graph_wiki_core.commands.work import WorkLintResult

    mock_result = LintAllResult(
        wiki=LintResult(wiki="w", total_pages=1),
        work=WorkLintResult(
            total_items=1,
            findings=[{"rule_id": "r", "severity": "error", "slug": "s", "message": "m"}],
        ),
        errors=[],
    )
    with patch("graph_wiki_cli.cli.run_lint_all", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["lint"])

    assert result.exit_code == 1


def test_lint_exit_1_on_wiki_errors() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.lint import LintResult
    from graph_wiki_core.commands.lint_all import LintAllResult
    from graph_wiki_core.commands.work import WorkLintResult

    mock_result = LintAllResult(
        wiki=LintResult(wiki="w", total_pages=1, errors=["bad"]),
        work=WorkLintResult(total_items=0, findings=[]),
        errors=[],
    )
    with patch("graph_wiki_cli.cli.run_lint_all", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["lint"])

    assert result.exit_code == 1
