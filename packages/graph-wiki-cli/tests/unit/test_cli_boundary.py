from __future__ import annotations

import importlib
import importlib.metadata
import inspect

import typer


def test_graph_wiki_cli_distribution_exposes_only_gw_console_script() -> None:
    """The graph-wiki-cli package owns gw; graph commands live under `gw graph`."""
    distribution = importlib.metadata.distribution("graph-wiki-cli")
    console_scripts = {
        entry_point.name: entry_point.value
        for entry_point in distribution.entry_points
        if entry_point.group == "console_scripts"
    }

    assert console_scripts["gw"] == "graph_wiki_cli.cli:app"
    assert "gwgraph" not in console_scripts
    assert "gw graph" not in console_scripts
    assert "graph-wiki-agent" not in console_scripts


def test_graph_io_no_longer_exposes_cg_console_script() -> None:
    distribution = importlib.metadata.distribution("graph-io")
    console_scripts = {
        entry_point.name: entry_point.value
        for entry_point in distribution.entry_points
        if entry_point.group == "console_scripts"
    }

    assert "cg" not in console_scripts


def test_migrate_vault_command_removed() -> None:
    """`gw migrate-vault` is fully removed — no command, no source reference."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "migrate-vault" not in root_command.commands

    cli_module = importlib.import_module("graph_wiki_cli.cli")
    assert "migrate_vault" not in inspect.getsource(cli_module)


def test_util_namespace_lists_relocated_commands() -> None:
    """`gw util` is a subapp exposing trace, tokens, and log."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "util" in root_command.commands
    util_group = root_command.commands["util"]
    assert set(util_group.commands) >= {"trace", "tokens", "log"}


def test_top_level_invocation_of_relocated_commands_exits_2() -> None:
    """Invoking a moved command at the top level errors with Click's exit code 2."""
    from graph_wiki_cli.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    for name in ("trace", "tokens", "log"):
        result = runner.invoke(app, [name])
        assert result.exit_code == 2, f"expected exit 2 for top-level `gw {name}`, got {result.exit_code}"
