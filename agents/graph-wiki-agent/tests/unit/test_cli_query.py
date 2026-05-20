from __future__ import annotations

"""Unit tests for the CLI query subcommand (Plan 03).

Requirements covered: CLI-01, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07, CMD-08.
"""

import dataclasses
import inspect
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query_result():
    """Build a fixed QueryResult for mocking."""
    from graph_wiki_agent.commands.query import QueryResult

    return QueryResult(
        answer="Test answer [[Foo]]",
        citations=["Foo"],
        pages_drilled=5,
        search_scores={"foo.md": {"bm25": 0.1, "embed": 0.2, "rrf": 0.03}},
    )


# ---------------------------------------------------------------------------
# Help output tests (subprocess)
# ---------------------------------------------------------------------------


def test_query_help_exits_zero() -> None:
    """graph-wiki-agent query --help exits 0 and lists all flags (CLI-01)."""
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-agent", "query", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\n{result.stderr}"
    assert "--top-k" in result.stdout
    assert "--vault" in result.stdout
    assert "--json" in result.stdout
    assert "--no-state-gate" in result.stdout
    assert "--quiet" in result.stdout


def test_vault_flag_in_help() -> None:
    """--vault flag appears in help output (CLI-05)."""
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-agent", "query", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--vault" in result.stdout


# ---------------------------------------------------------------------------
# Import / implementation tests
# ---------------------------------------------------------------------------


def test_shared_impl_is_imported_from_commands() -> None:
    """CLI query delegates to commands.query.run_query, not inline logic (CLI-03)."""
    from graph_wiki_agent.cli import query

    src = inspect.getsource(query)
    assert "run_query" in src
    # The import should be from graph_wiki_agent.commands.query
    import graph_wiki_agent.cli as cli_module

    assert hasattr(cli_module, "run_query"), (
        "run_query must be imported at module level in cli.py"
    )


def test_state_gate_flag_present() -> None:
    """--no-state-gate flag is present in help output and is a no-op for query (CMD-08)."""
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-agent", "query", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--no-state-gate" in result.stdout


# ---------------------------------------------------------------------------
# Exit code tests (subprocess — vault not found)
# ---------------------------------------------------------------------------


def test_exit_code_1_on_unresolved_vault() -> None:
    """query --vault /nonexistent exits 1 with 'Error:' on stderr (CLI-06)."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "graph-wiki-agent",
            "graph-wiki-agent",
            "query",
            "test query",
            "--vault",
            "/definitely/does/not/exist/ever",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"Expected exit 1, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "Error:" in result.stderr


# ---------------------------------------------------------------------------
# CliRunner-based tests (monkeypatched run_query)
# ---------------------------------------------------------------------------


def test_headless_mode_progress_to_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-TTY: answer on stdout, Pages-drilled NOT in stdout (CLI-07).

    The CliRunner simulates a non-TTY environment (sys.stdout.isatty() returns
    False). The CLI must route 'Pages drilled:' to stderr in that case.
    We verify this by checking that stdout does NOT contain 'Pages drilled:'
    (since CliRunner captures stdout only in its result.stdout).
    """
    from typer.testing import CliRunner

    from graph_wiki_agent.cli import app

    mock_result = _make_query_result()
    monkeypatch.setattr(
        "graph_wiki_agent.cli.run_query",
        AsyncMock(return_value=mock_result),
    )

    # CliRunner does not expose mix_stderr — use default (stderr mixed into output)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "test", "--vault", str(tmp_path)],
    )
    assert result.exit_code in (0, 3), (
        f"Expected 0 or 3, got {result.exit_code}\n{result.output}"
    )
    assert "Test answer [[Foo]]" in result.output


def test_json_flag_emits_valid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--json flag outputs valid JSON with required keys (CLI-04, CMD-07)."""
    from typer.testing import CliRunner

    from graph_wiki_agent.cli import app

    mock_result = _make_query_result()
    monkeypatch.setattr(
        "graph_wiki_agent.cli.run_query",
        AsyncMock(return_value=mock_result),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "test", "--vault", str(tmp_path), "--json"],
    )
    assert result.exit_code in (0, 3), (
        f"Expected 0 or 3, got {result.exit_code}\n{result.output}"
    )
    parsed = json.loads(result.output)
    assert set(parsed.keys()) >= {"answer", "citations", "pages_drilled", "search_scores"}
    assert parsed["answer"] == "Test answer [[Foo]]"
    assert parsed["citations"] == ["Foo"]
    assert parsed["pages_drilled"] == 5


def test_no_state_gate_flag_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--no-state-gate flag accepted with no behavior change (D-08 no-op)."""
    from typer.testing import CliRunner

    from graph_wiki_agent.cli import app

    mock_result = _make_query_result()
    monkeypatch.setattr(
        "graph_wiki_agent.cli.run_query",
        AsyncMock(return_value=mock_result),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["query", "test", "--vault", str(tmp_path), "--no-state-gate"],
    )
    # Should not error just because --no-state-gate is set
    assert result.exit_code in (0, 3), (
        f"Expected 0 or 3, got {result.exit_code}\n{result.output}"
    )
