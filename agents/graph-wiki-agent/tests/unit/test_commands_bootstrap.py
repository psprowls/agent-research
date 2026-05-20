from __future__ import annotations

"""Unit tests for the bootstrap command (Plan 05-01; renamed in Phase 18 / CMD-02).

The Typer subcommand was renamed `init` → `bootstrap` in Phase 18 so Claude Code's
native `/init` slash command is reachable again. The underlying Python module
`code_wiki_agent.commands.init` and its `run_init` function intentionally remain
unchanged per Phase 18 D-02 (internal, machine-facing, not user-typed).

Requirements covered: CMD-01, CMD-02.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

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


def test_bootstrap_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI `bootstrap --json` emits valid JSON with required keys."""
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
        ["bootstrap", "--topic", "foo", "--tool", "claude-code", "--json"],
    )
    assert result.exit_code == 0, f"Unexpected exit: {result.output}"
    parsed = json.loads(result.output)
    assert parsed["status"] == "ok"
    assert parsed["topic"] == "test-topic"
    assert "raw_path" in parsed
    assert "work_path" in parsed


# ---------------------------------------------------------------------------
# CLI: old `init` subcommand is gone (D-04 hard cut, no alias)
# ---------------------------------------------------------------------------


def test_bootstrap_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """The old `init` Typer subcommand is unreachable (no backwards-compat alias).

    Asserts that invoking `code-wiki-agent init ...` via Typer raises a "no such
    command" error after Phase 18's hard cut (D-04). The new `bootstrap` subcommand
    is the only entry point.
    """
    from typer.testing import CliRunner

    from code_wiki_agent.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["init", "--topic", "foo", "--tool", "claude-code"],
    )
    # Typer returns exit code 2 for "no such command".
    assert result.exit_code != 0, (
        f"`code-wiki-agent init ...` must NOT be a valid subcommand "
        f"after Phase 18 rename; got exit_code={result.exit_code}"
    )
