"""Unit tests for the native `gw graph` Typer namespace."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from graph_wiki_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_graph_help_lists_native_code_graph_subcommands() -> None:
    result = runner.invoke(app, ["graph", "--help"])

    assert result.exit_code == 0, result.output
    assert "Code graph operations" in result.output
    assert "update" in result.output
    assert "find" in result.output
    assert "describe" in result.output
    assert "domain-clusters" in result.output


def test_graph_find_help_is_typer_help() -> None:
    result = runner.invoke(app, ["graph", "find", "--help"])

    assert result.exit_code == 0, result.output
    assert "Find graph nodes" in result.output
    assert "--name" in result.output
    assert "--kind" in result.output
    assert "--in-package" in result.output


def test_graph_status_invokes_relocated_command_module() -> None:
    with patch("graph_wiki_cli.graph_cli.main.ops_status.run", return_value=0) as status_run:
        result = runner.invoke(app, ["graph", "--repo", ".", "--mode", "test", "status"])

    assert result.exit_code == 0, result.output
    args = status_run.call_args.args[0]
    assert args.repo == Path(".")
    assert args.mode == "test"
    assert args.fmt == "human"


def test_graph_find_no_filters_fails_in_typer_layer() -> None:
    result = runner.invoke(app, ["graph", "find"])

    assert result.exit_code == 2
    assert "at least one of --name, --kind, --in-package is required" in result.stderr


def test_graph_actual_find_missing_db_uses_gw_graph_guidance(tmp_path: Path) -> None:
    result = runner.invoke(app, ["graph", "--repo", str(tmp_path), "--mode", "test", "find", "--name", "x"])

    assert result.exit_code == 3
    assert "graph DB not found" in result.stderr
    assert "gw graph update --full" in result.stderr
