from __future__ import annotations

from typer.testing import CliRunner


def test_cli_app_is_named_gw() -> None:
    from graph_wiki_cli.cli import app

    assert app.info.name == "gw"


def test_version_uses_graph_wiki_cli_distribution() -> None:
    from graph_wiki_cli.cli import app

    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.startswith("gw ")
