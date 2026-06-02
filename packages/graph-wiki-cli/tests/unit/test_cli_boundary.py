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


def test_cli_module_imports_typer_app_named_gw() -> None:
    """Importing graph_wiki_cli.cli exposes the Typer app used by the gw script."""
    cli_module = importlib.import_module("graph_wiki_cli.cli")

    assert isinstance(cli_module.app, typer.Typer)
    assert cli_module.app.info.name == "gw"


def test_cli_module_imports_core_commands_not_agent_cli_shim() -> None:
    """Wiki commands delegate to graph_wiki_core (in wiki_cli/main.py), not graph_wiki_agent.cli."""
    cli_module = importlib.import_module("graph_wiki_cli.cli")
    wiki_module = importlib.import_module("graph_wiki_cli.wiki_cli.main")
    cli_source = inspect.getsource(cli_module)
    wiki_source = inspect.getsource(wiki_module)

    assert "from graph_wiki_core.commands.query import run_query" in wiki_source
    assert "from graph_wiki_core.commands" in wiki_source
    for source in (cli_source, wiki_source):
        assert "graph_wiki_agent.cli" not in source
        assert "from graph_wiki_agent" not in source


def test_graph_io_no_longer_exposes_cg_console_script() -> None:
    distribution = importlib.metadata.distribution("graph-io")
    console_scripts = {
        entry_point.name: entry_point.value
        for entry_point in distribution.entry_points
        if entry_point.group == "console_scripts"
    }

    assert "cg" not in console_scripts


def test_graph_package_exposes_moved_cli_module_for_gw_graph_namespace() -> None:
    cli_module = importlib.import_module("graph_wiki_cli.graph_cli.main")
    assert hasattr(cli_module, "main")
    assert "gw graph" in inspect.getsource(cli_module)


def test_migrate_vault_command_removed() -> None:
    """`gw migrate-vault` is fully removed — no command, no source reference."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "migrate-vault" not in root_command.commands

    cli_module = importlib.import_module("graph_wiki_cli.cli")
    assert "migrate_vault" not in inspect.getsource(cli_module)


def test_wiki_package_exposes_moved_cli_module_for_gw_wiki_namespace() -> None:
    wiki_module = importlib.import_module("graph_wiki_cli.wiki_cli.main")
    assert hasattr(wiki_module, "main")
    assert "gw wiki" in inspect.getsource(wiki_module)
