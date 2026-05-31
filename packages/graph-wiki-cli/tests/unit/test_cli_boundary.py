from __future__ import annotations

import importlib
import importlib.metadata
import inspect

import typer


def test_graph_wiki_cli_distribution_exposes_gw_and_gwgraph_console_scripts() -> None:
    """The graph-wiki-cli package owns the gw and gwgraph executables."""
    distribution = importlib.metadata.distribution("graph-wiki-cli")
    console_scripts = {
        entry_point.name: entry_point.value
        for entry_point in distribution.entry_points
        if entry_point.group == "console_scripts"
    }

    assert console_scripts["gw"] == "graph_wiki_cli.cli:app"
    assert console_scripts["gwgraph"] == "graph_wiki_cli.graph_cli.main:main"
    assert "graph-wiki-agent" not in console_scripts


def test_cli_module_imports_typer_app_named_gw() -> None:
    """Importing graph_wiki_cli.cli exposes the Typer app used by the gw script."""
    cli_module = importlib.import_module("graph_wiki_cli.cli")

    assert isinstance(cli_module.app, typer.Typer)
    assert cli_module.app.info.name == "gw"


def test_cli_module_imports_core_commands_not_agent_cli_shim() -> None:
    """The CLI presentation package delegates to graph_wiki_core, not graph_wiki_agent.cli."""
    cli_module = importlib.import_module("graph_wiki_cli.cli")
    source = inspect.getsource(cli_module)

    assert "from graph_wiki_core.commands.query import run_query" in source
    assert "from graph_wiki_core.commands" in source
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


def test_gwgraph_package_exposes_moved_cli_module() -> None:
    cli_module = importlib.import_module("graph_wiki_cli.graph_cli.main")
    assert hasattr(cli_module, "main")
    assert "gwgraph" in inspect.getsource(cli_module)
