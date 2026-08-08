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


def test_work_file_slug_words_flag_plumbing() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import IngestResult

    mock_result = IngestResult(
        status="ok",
        page_path="work/2026-07-11-feature-shorten-slugs.md",
        slug="2026-07-11-feature-shorten-slugs",
        title="Shorten slugs",
        page_type="work",
        source_path="",
        cross_refs_updated=0,
        warnings=[],
    )

    with patch("graph_wiki_cli.work_cli.main.run_work_file", new=AsyncMock(return_value=mock_result)) as mock_file:
        result = runner.invoke(
            app,
            [
                "work",
                "file",
                "--title",
                "Shorten slugs",
                "--kind",
                "feature",
                "--summary",
                "shorten em",
                "--slug-words",
                "shorten work item slugs",
            ],
        )

    assert result.exit_code == 0, result.output
    assert mock_file.call_args.kwargs["slug_words"] == "shorten work item slugs"


def test_work_file_prints_warn_lines_for_slug_word_warnings() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import IngestResult

    mock_result = IngestResult(
        status="ok",
        page_path="work/2026-07-11-feature-one-two-three-four-five-six.md",
        slug="2026-07-11-feature-one-two-three-four-five-six",
        title="Many words",
        page_type="work",
        source_path="",
        cross_refs_updated=0,
        warnings=["--slug-words: 7 words truncated to 6 (one-two-three-four-five-six)"],
    )

    with patch("graph_wiki_cli.work_cli.main.run_work_file", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(
            app,
            [
                "work",
                "file",
                "--title",
                "Many words",
                "--kind",
                "feature",
                "--summary",
                "x",
                "--slug-words",
                "one two three four five six seven",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "[warn] --slug-words: 7 words truncated to 6" in result.output


def test_work_file_json_output_includes_warnings() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import IngestResult

    mock_result = IngestResult(
        status="ok",
        page_path="work/2026-07-11-feature-x.md",
        slug="2026-07-11-feature-x",
        title="X",
        page_type="work",
        source_path="",
        cross_refs_updated=0,
        warnings=["some warning"],
    )

    with patch("graph_wiki_cli.work_cli.main.run_work_file", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(
            app,
            ["work", "file", "--title", "X", "--kind", "feature", "--summary", "x", "--json"],
        )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["warnings"] == ["some warning"]


def test_work_next_descend_passthrough() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkNextResult

    wn = WorkNextResult(slug="leaf", status="open", kind="bug", phase="design")
    with patch("graph_wiki_cli.work_cli.main.run_work_next", new=AsyncMock(return_value=wn)) as next_mock:
        res = runner.invoke(app, ["work", "next", "some-epic", "--descend", "--json"])
    assert res.exit_code == 0
    assert next_mock.call_args.kwargs["descend"] is True


def test_work_next_human_output_shows_descent_path() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkNextResult

    wn = WorkNextResult(
        slug="leaf-child",
        status="open",
        kind="bug",
        phase="plan",
        descent={"from": "big-epic", "path": ["big-epic", "mid-feat", "leaf-child"]},
    )
    with patch("graph_wiki_cli.work_cli.main.run_work_next", new=AsyncMock(return_value=wn)):
        res = runner.invoke(app, ["work", "next", "big-epic", "--descend"])
    assert res.exit_code == 0
    assert "descent: " in res.stdout
    assert "big-epic -> mid-feat -> leaf-child" in res.stdout


def test_work_regen_index_exit_0(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.work import WorkRegenResult

    mock_result = WorkRegenResult(item_count=2, sidecar_path=str(tmp_path / "work-index.json"))

    with patch("graph_wiki_cli.work_cli.main.run_work_regen_index", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "regen-index", "--json"])

    assert result.exit_code == 0


def test_work_subcommands_include_orchestrate() -> None:
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    work_group = root_command.commands["work"]
    assert "orchestrate" in work_group.commands


def test_work_orchestrate_json_exit_0_with_blocked_items() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.orchestrate import WorkOrchestrateResult

    mock_result = WorkOrchestrateResult(
        slug="epic-x",
        terminal=False,
        max_parallel=2,
        permission_mode="bypassPermissions",
        blocked=[{"slug": "epic-x-b", "kind": "capacity", "reason": "ready, but no worker slot free"}],
    )

    with patch("graph_wiki_cli.work_cli.main.run_work_orchestrate", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "orchestrate", "epic-x", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["blocked"][0]["kind"] == "capacity"


def test_work_orchestrate_passes_live_csv() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.orchestrate import WorkOrchestrateResult

    mock_result = WorkOrchestrateResult(slug="epic-x")
    mock_run = AsyncMock(return_value=mock_result)

    with patch("graph_wiki_cli.work_cli.main.run_work_orchestrate", new=mock_run):
        result = runner.invoke(app, ["work", "orchestrate", "epic-x", "--live", "a#execute,b#plan", "--json"])

    assert result.exit_code == 0
    assert mock_run.call_args.kwargs["live"] == ("a#execute", "b#plan")


def test_work_orchestrate_exit_3_on_invalid_config() -> None:
    from graph_wiki_cli.cli import app

    with patch(
        "graph_wiki_cli.work_cli.main.run_work_orchestrate",
        new=AsyncMock(side_effect=RuntimeError("workflow.auto_drive: bad")),
    ):
        result = runner.invoke(app, ["work", "orchestrate", "epic-x", "--json"])

    assert result.exit_code == 3


def test_work_orchestrate_human_output_shows_dispatches_and_blocked() -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.orchestrate import WorkOrchestrateResult

    mock_result = WorkOrchestrateResult(
        slug="epic-x",
        terminal=False,
        max_parallel=2,
        permission_mode="bypassPermissions",
        slots_free=1,
        dispatches=[
            {
                "key": "epic-x-a#execute",
                "slug": "epic-x-a",
                "phase": "execute",
                "kind": "bug",
                "effort": None,
                "skill": "test-driven-development",
                "mode": "autonomous",
                "model": "claude-sonnet-5",
                "reasoning_effort": None,
                "worktree": {
                    "action": "create-top-level",
                    "path": None,
                    "branch": "epic/x",
                    "base_branch": "develop",
                    "exists": None,
                },
                "merge_target": "develop",
                "prompt": "Run /graph-wiki:next epic-x-a.",
            }
        ],
        advances=[{"slug": "epic-x", "reason": "epic children complete"}],
        blocked=[{"slug": "epic-x-b", "kind": "capacity", "reason": "ready, but no worker slot free"}],
        warnings=["--live key 'ghost#plan' matches no known item"],
    )

    with patch("graph_wiki_cli.work_cli.main.run_work_orchestrate", new=AsyncMock(return_value=mock_result)):
        result = runner.invoke(app, ["work", "orchestrate", "epic-x"])

    assert result.exit_code == 0
    assert "epic-x-a#execute" in result.output
    assert "test-driven-development" in result.output
    assert "epic-x" in result.output
    assert "epic-x-b" in result.output
    assert "capacity" in result.output
    assert "ghost#plan" in result.output
