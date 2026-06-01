"""Unit tests for the `gw graph` command namespace."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from graph_wiki_cli.cli import app


runner = CliRunner()


def test_graph_help_lists_relocated_code_graph_subcommands() -> None:
    result = runner.invoke(app, ["graph", "--help"])

    assert result.exit_code == 0, result.output
    assert "usage: gw graph" in result.output
    assert "update" in result.output
    assert "find" in result.output
    assert "describe-package" in result.output
    assert "domain-clusters" in result.output


def test_graph_find_help_routes_to_relocated_parser() -> None:
    result = runner.invoke(app, ["graph", "find", "--help"])

    assert result.exit_code == 0, result.output
    assert "usage: gw graph find" in result.output
    assert "--name" in result.output
    assert "--kind" in result.output
    assert "--in-package" in result.output


def test_graph_dispatch_calls_relocated_main() -> None:
    with patch("graph_wiki_cli.cli.graph_cli_main", return_value=0) as graph_main:
        result = runner.invoke(app, ["graph", "--repo", ".", "--mode", "test", "status"])

    assert result.exit_code == 0, result.output
    graph_main.assert_called_once_with(["--repo", ".", "--mode", "test", "status"])


def test_graph_dispatch_maps_argparse_system_exit() -> None:
    with patch("graph_wiki_cli.cli.graph_cli_main", side_effect=SystemExit(2)):
        result = runner.invoke(app, ["graph", "find"])

    assert result.exit_code == 2


def test_graph_actual_find_missing_db_uses_gw_graph_guidance(tmp_path: Path) -> None:
    result = runner.invoke(app, ["graph", "--repo", str(tmp_path), "--mode", "test", "find", "--name", "x"])

    assert result.exit_code == 3
    assert "graph DB not found" in result.stderr
    assert "gw graph update --full" in result.stderr
