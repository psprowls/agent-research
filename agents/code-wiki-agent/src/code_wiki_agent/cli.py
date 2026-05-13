from __future__ import annotations

import typer

app = typer.Typer(
    name="code-wiki-agent",
    help="code-wiki-agent: AWS Bedrock-powered wiki maintenance CLI.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print version and exit."""
    typer.echo("code-wiki-agent 0.1.0")


if __name__ == "__main__":
    app()
