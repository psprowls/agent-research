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


def test_work_file_parent_and_depends_on(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app

    workspace = tmp_path / "ws"
    work_dir = workspace / "wiki" / "work"
    work_dir.mkdir(parents=True)
    # Pre-create the parent epic with filename == stem.
    (work_dir / "2026-06-26-epic-x.md").write_text(
        "---\ntitle: epic-x\nkind: epic\nstatus: accepted\nopened: 2026-06-26\nupdated: 2026-06-26\n---\nbody\n",
        encoding="utf-8",
    )
    # Pre-create the sibling items --depends-on references.
    for slug in ("2026-06-26-sib-a", "2026-06-26-sib-b"):
        (work_dir / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\nkind: feature\nstatus: open\nopened: 2026-06-26\nupdated: 2026-06-26\n---\nbody\n",
            encoding="utf-8",
        )

    result = runner.invoke(
        app,
        [
            "work",
            "file",
            "--title",
            "Child A",
            "--kind",
            "feature",
            "--summary",
            "do a thing",
            "--parent",
            "2026-06-26-epic-x",
            "--depends-on",
            "2026-06-26-sib-a,2026-06-26-sib-b",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0, result.output
    page = next(work_dir.glob("*child-a.md"))
    text = page.read_text(encoding="utf-8")
    assert "parent: 2026-06-26-epic-x" in text
    assert "2026-06-26-sib-a" in text
    assert "2026-06-26-sib-b" in text
    assert "Designed as part of epic" in text


def test_work_regen_index_exit_0(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkRegenResult

    mock_result = WorkRegenResult(item_count=2, sidecar_path=str(tmp_path / "work-index.json"))

    with patch("graph_wiki_cli.work_cli.main.run_work_regen_index", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "regen-index", "--json"])

    assert result.exit_code == 0
