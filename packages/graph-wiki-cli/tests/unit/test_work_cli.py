from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import typer
from typer.testing import CliRunner

runner = CliRunner()


def test_work_app_registered_under_gw() -> None:
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "work" in root_command.commands


def test_work_subcommands_exist() -> None:
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    work_group = root_command.commands["work"]
    assert {"file", "lint", "archive", "status", "regen-index"} <= set(work_group.commands)


def test_work_lint_json_exit_0_when_clean(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkLintResult

    mock_result = WorkLintResult(total_items=0, findings=[])

    with patch("graph_wiki_cli.work_cli.main.run_work_lint", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "lint", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["findings"] == []


def test_work_lint_exit_1_when_error_severity(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkLintResult

    mock_result = WorkLintResult(
        total_items=1,
        findings=[{"rule_id": "status-not-in-enum", "severity": "error", "slug": "foo", "message": "bad status"}],
    )

    with patch("graph_wiki_cli.work_cli.main.run_work_lint", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "lint", "--json"])

    assert result.exit_code == 1


def test_work_status_exit_4_when_sidecar_missing(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkStatusResult

    mock_result = WorkStatusResult(sidecar_missing=True)

    with patch("graph_wiki_cli.work_cli.main.run_work_status", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "status", "--json"])

    assert result.exit_code == 4


def test_work_regen_index_exit_0(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkRegenResult

    mock_result = WorkRegenResult(item_count=2, sidecar_path=str(tmp_path / "work-index.json"))

    with patch("graph_wiki_cli.work_cli.main.run_work_regen_index", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "regen-index", "--json"])

    assert result.exit_code == 0
