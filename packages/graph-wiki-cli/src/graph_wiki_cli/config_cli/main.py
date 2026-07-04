"""Native Typer command surface for `gw config`.

Thin shell over graph_wiki_core.commands.config — the sole programmatic writer
for graph-wiki configuration. `gw config list` output is the canonical config
documentation.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path

import typer
from graph_wiki_core.commands.config import (
    InitAnswers,
    run_config_get,
    run_config_hooks,
    run_config_init,
    run_config_list,
    run_config_set,
    run_config_sync,
    run_config_unset,
)
from workspace_io.registry import RegistryError

config_app = typer.Typer(
    name="config",
    help="Read and write graph-wiki configuration (the sole config writer).",
    no_args_is_help=True,
)

_WS_OPT = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")

_REPO_OPT = typer.Option(
    "", "--repo", help="Repo whose .claude/settings.local.json is written (default: workspace_io discovery)"
)


def _ws(workspace: str) -> Path | None:
    return Path(workspace) if workspace else None


def _echo_value(cv, json_output: bool) -> None:
    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(cv), indent=2, default=str))
        return
    typer.echo(f"{cv.key} = {cv.value!r}  (origin: {cv.origin})")
    if cv.shadows is not None:
        typer.echo(f"  note: manifest value {cv.shadows!r} is shadowed by ${cv.env_var}")


@config_app.command()
def get(
    key: str = typer.Argument(..., help="Config key (see `gw config list`)"),
    workspace: str = _WS_OPT,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show a key's effective value and origin (env / manifest / default)."""
    try:
        cv = asyncio.run(run_config_get(key, _ws(workspace)))
    except (RegistryError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
    _echo_value(cv, json_output)


@config_app.command(name="set")
def set_cmd(
    key: str = typer.Argument(...),
    value: str = typer.Argument(...),
    workspace: str = _WS_OPT,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Set a manifest key (registry-validated; refreshes the projection)."""
    try:
        cv = asyncio.run(run_config_set(key, value, _ws(workspace)))
    except (RegistryError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
    _echo_value(cv, json_output)


@config_app.command()
def unset(
    key: str = typer.Argument(...),
    workspace: str = _WS_OPT,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Remove a manifest key (falls back to the built-in default)."""
    try:
        cv = asyncio.run(run_config_unset(key, _ws(workspace)))
    except (RegistryError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
    _echo_value(cv, json_output)


@config_app.command(name="list")
def list_cmd(
    workspace: str = _WS_OPT,
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Every config knob: value (secrets masked), origin, default, description."""
    try:
        rows = asyncio.run(run_config_list(_ws(workspace)))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(json.dumps([dataclasses.asdict(r) for r in rows], indent=2, default=str))
        return
    for r in rows:
        marker = {"env": "*", "manifest": "+", "default": " "}[r.origin]
        typer.echo(f"{marker} {r.key} = {r.value!r}  [{r.origin}; default {r.default!r}]")
        typer.echo(f"    {r.description}")


@config_app.command()
def sync(workspace: str = _WS_OPT) -> None:
    """Regenerate <workspace>/.graph-wiki/config.json from the manifest."""
    try:
        out = asyncio.run(run_config_sync(_ws(workspace)))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"[ok] projection: {out}")


hooks_app = typer.Typer(name="hooks", help="Register/unregister opt-in hooks in .claude/settings.local.json.")
config_app.add_typer(hooks_app, name="hooks")


def _run_hooks(action: str, feature: str, repo: str) -> None:
    try:
        result = asyncio.run(run_config_hooks(action, feature, repo_root=_ws(repo)))
    except (ValueError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
    typer.echo(f"[ok] {result.settings_path}")
    for s in result.added:
        typer.echo(f"  added: {s}")
    for s in result.removed:
        typer.echo(f"  removed: {s}")
    for s in result.skipped:
        typer.echo(f"  already registered: {s}")


@hooks_app.command()
def enable(
    feature: str = typer.Argument(..., help="gates | transcript"),
    repo: str = _REPO_OPT,
) -> None:
    """Merge the feature's hook registrations (gates also denies EnterPlanMode)."""
    _run_hooks("enable", feature, repo)


@hooks_app.command()
def disable(
    feature: str = typer.Argument(..., help="gates | transcript"),
    repo: str = _REPO_OPT,
) -> None:
    """Remove the feature's hook registrations (gates also un-denies EnterPlanMode)."""
    _run_hooks("disable", feature, repo)


@config_app.command()
def init(
    workspace: str = _WS_OPT,
    repo: str = _REPO_OPT,
    model_routing: str = typer.Option("", "--model-routing", help="guided | fixed:<model> | off (blank = ask)"),
    commit_strategy: str = typer.Option("", "--commit-strategy", help="per-task | at-end (blank = ask)"),
    gates: bool = typer.Option(None, "--gates/--no-gates", help="Gate enforcement hooks (blank = ask)"),
    transcript: bool = typer.Option(
        None, "--transcript/--no-transcript", help="Session transcript capture (blank = ask)"
    ),
    write_env: bool = typer.Option(
        None, "--write-env/--no-write-env", help="Write GRAPH_WIKI_WORKSPACE env block (blank = ask)"
    ),
) -> None:
    """Interactive terminal onboarding — the same write paths as gw config set/hooks.

    --repo pins which repo's .claude/settings.local.json receives hook and env
    writes (default: workspace_io discovery).

    First run against an external workspace needs --workspace: the repo-side
    pointer no longer exists and the env block it would come from is what this
    command is about to write. The flag's value seeds the env block.
    """
    ws = _ws(workspace)
    answers = InitAnswers(
        model_routing=model_routing or None,
        commit_strategy=commit_strategy or None,
        gates=gates,
        transcript=transcript,
        write_env=write_env,
    )
    interactive = any(
        v is None
        for v in (answers.model_routing, answers.commit_strategy, answers.gates, answers.transcript, answers.write_env)
    )
    if interactive:
        current = {r.key: r for r in asyncio.run(run_config_list(ws))}
        if answers.model_routing is None:
            mech = current["workflow.model_routing.mechanical"].value
            typer.echo(f"Model routing (current mechanical tier: {mech!r})")
            choice = typer.prompt("  guided / fixed:<model> / off / skip", default="skip")
            answers.model_routing = None if choice == "skip" else choice
        if answers.commit_strategy is None:
            cur = current["workflow.commit_strategy"].value
            choice = typer.prompt(f"Commit strategy [per-task/at-end/skip] (current: {cur})", default="skip")
            answers.commit_strategy = None if choice == "skip" else choice
        if answers.gates is None:
            answers.gates = typer.confirm("Enable user-gate enforcement hooks?", default=False) or None
        if answers.transcript is None:
            answers.transcript = typer.confirm("Enable session transcript capture?", default=False) or None
        if answers.write_env is None:
            answers.write_env = (
                typer.confirm("Write GRAPH_WIKI_WORKSPACE into .claude/settings.local.json?", default=False) or None
            )
    try:
        result = asyncio.run(run_config_init(answers, ws, repo_root=_ws(repo)))
    except (RegistryError, ValueError, RuntimeError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)
    if result.actions:
        typer.echo("[ok] applied:")
        for a in result.actions:
            typer.echo(f"  - {a}")
    else:
        typer.echo("[ok] nothing to change.")
