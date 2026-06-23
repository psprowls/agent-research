import typer
from subagent_cli.cli import app


def test_app_exists():
    assert isinstance(app, typer.Typer)
