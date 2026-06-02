from __future__ import annotations

import typer


def test_wiki_cli_module_exposes_wiki_app_and_main() -> None:
    """The relocated module exposes a `wiki` Typer app and a `main()` entry."""
    from graph_wiki_cli.wiki_cli import main as wiki_main

    assert isinstance(wiki_main.wiki_app, typer.Typer)
    assert wiki_main.wiki_app.info.name == "wiki"
    assert hasattr(wiki_main, "main")


def test_root_app_mounts_wiki_group_with_subcommands() -> None:
    """`gw wiki` is registered and exposes query/log/lint/ingest."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "wiki" in root_command.commands

    wiki_group = root_command.commands["wiki"]
    assert {"query", "log", "lint", "ingest"} <= set(wiki_group.commands)

    ingest_group = wiki_group.commands["ingest"]
    assert {"source", "work-item"} <= set(ingest_group.commands)


def test_moved_commands_no_longer_top_level() -> None:
    """query/log/lint/ingest are no longer registered at the root."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    for name in ("query", "log", "lint", "ingest"):
        assert name not in root_command.commands
