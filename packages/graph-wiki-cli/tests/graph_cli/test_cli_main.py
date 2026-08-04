"""Belt-and-suspenders CLI registry assertions."""

from __future__ import annotations

import typer
from graph_wiki_cli.graph_cli.main import graph_app


def _command_names() -> set[str]:
    return {info.name for info in graph_app.registered_commands if isinstance(info.name, str)}


def test_no_package_family_subcommand() -> None:
    commands = _command_names()
    assert "describe-package-family" not in commands
    assert "list-package-families" not in commands


def test_graph_app_is_native_typer_surface() -> None:
    assert isinstance(graph_app, typer.Typer)
    assert "find" in _command_names()
    assert "update" in _command_names()


def test_describe_list_consolidation_registry() -> None:
    commands = _command_names()
    # New consolidated commands exist.
    assert "describe" in commands
    assert "list" in commands
    # Old per-kind commands are gone.
    for gone in (
        "describe-package",
        "describe-app",
        "describe-builtin",
        "describe-dependency",
        "describe-path",
        "describe-repo",
        "describe-suite",
        "describe-domain",
        "describe-entry-point",
        "describe-agent-plugin",
        "list-apps",
        "list-builtins",
        "list-packages",
        "list-scripts",
        "list-suites",
        "list-domains",
    ):
        assert gone not in commands, f"{gone} should have been removed"
    # Deliberate carve-out: entry-point listing stays its own command.
    assert "list-entry-points" in commands
