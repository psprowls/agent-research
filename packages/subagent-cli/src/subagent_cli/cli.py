"""Typer CLI surface for invoking Bedrock subagents."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="subagent",
    help="Invoke Bedrock subagents live with colored prompt/response/model output.",
    no_args_is_help=True,
)


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Prompt to send to the subagent."),
) -> None:
    """Run a subagent with the given prompt."""
    raise NotImplementedError("subagent run not yet implemented")
