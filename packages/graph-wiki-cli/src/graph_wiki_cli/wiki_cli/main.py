"""Native Typer command surface for `gw wiki`.

Wiki-maintenance commands (lint, ack-drift, proposals, archive, propagate-drift)
delegate to graph_wiki_core.commands.*; this module owns only presentation.
query, log, ingest, and tokens were promoted to top-level `gw` commands
(see cli.py).
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Optional

import typer
from graph_wiki_core.commands._paths import resolve_wiki_and_repo
from graph_wiki_core.commands.ack_drift import run_ack_drift
from graph_wiki_core.commands.graph_query import open_reader
from graph_wiki_core.commands.lint import run_lint
from graph_wiki_core.commands.propagate_drift import run_propagate_drift
from graph_wiki_core.commands.proposals import run_list_proposals, run_set_proposal_status
from graph_wiki_core.commands.wiki_archive import run_wiki_archive

from graph_wiki_cli.lint_format import format_wiki_lint

wiki_app = typer.Typer(
    name="wiki",
    help="Wiki maintenance operations.",
    no_args_is_help=True,
)


@wiki_app.command()
def lint(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    stale_days: int = typer.Option(90, "--stale-days", help="Days before a page is flagged as stale"),
    log_gap_days: int = typer.Option(14, "--log-gap-days", help="Days before a log gap is flagged"),
    json_output: bool = typer.Option(False, "--json", help="Emit LintResult as JSON"),
) -> None:
    """Run mechanical + semantic lint pass over the wiki and report findings."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_lint(workspace_path=workspace_path, stale_days=stale_days, log_gap_days=log_gap_days))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        import dataclasses as _dc

        typer.echo(json.dumps(_dc.asdict(result), indent=2, default=list))
    else:
        for line in format_wiki_lint(result):
            typer.echo(line)

    if result.errors:
        for err in result.errors:
            typer.echo(f"  error: {err}", err=True)
        raise typer.Exit(code=3)


@wiki_app.command(name="ack-drift")
def ack_drift(
    entity: str = typer.Argument(..., help="Entity URI or page slug to clear drift flags for"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit the result as JSON"),
) -> None:
    """Acknowledge (clear) human-section drift flags on an entity page without editing its prose."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = run_ack_drift(entity, workspace_path=workspace_path)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2, default=str))
    else:
        typer.echo(f"[ok] Cleared {result.cleared} drift flag(s): {result.page_path}")


@wiki_app.command(name="proposals")
def proposals(
    status: str = typer.Option(
        "proposed",
        "--status",
        help="proposed|approved|rejected|created|all (default: proposed)",
    ),
    kind: Optional[str] = typer.Option(None, "--kind", help="concept|adr|architecture (default: all kinds)"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit records as JSON"),
) -> None:
    """List curated-page proposals from the ledger (defaults to open ones)."""
    workspace_path = Path(workspace) if workspace else None
    status_filter = None if status == "all" else status
    try:
        records = run_list_proposals(workspace_path=workspace_path, status=status_filter, kind=kind)
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(records, indent=2))
        return
    if not records:
        typer.echo("No proposals.")
        return
    for r in records:
        proposal_id = f"{r['kind']}-{r['target_slug']}"
        typer.echo(f"{proposal_id}  [{r['status']}]  mode={r['mode']}  origins={len(r['origins'])}  — {r['title']}")


proposal_app = typer.Typer(help="Approve or reject a curated-page proposal.")
wiki_app.add_typer(proposal_app, name="proposal")


def _decide(proposal_id: str, status: str, workspace: str, json_output: bool) -> None:
    workspace_path = Path(workspace) if workspace else None
    try:
        decision = run_set_proposal_status(proposal_id, status, workspace_path=workspace_path)
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(decision), indent=2))
    else:
        typer.echo(f"[ok] {decision.proposal_id} -> {decision.status}")


@proposal_app.command(name="approve")
def proposal_approve(
    proposal_id: str = typer.Argument(..., help="<kind>-<target_slug>, e.g. adr-0007-md"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json", help="Emit the decision as JSON"),
) -> None:
    """Approve a proposal (flip its status to `approved`)."""
    _decide(proposal_id, "approved", workspace, json_output)


@proposal_app.command(name="reject")
def proposal_reject(
    proposal_id: str = typer.Argument(..., help="<kind>-<target_slug>, e.g. adr-0007-md"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json", help="Emit the decision as JSON"),
) -> None:
    """Reject a proposal (flip its status to `rejected`, preserved so it is not re-proposed)."""
    _decide(proposal_id, "rejected", workspace, json_output)


@wiki_app.command()
def archive(
    slugs: Optional[list[str]] = typer.Argument(
        None, help="Path-qualified pages to archive, e.g. adrs/0003-foo concepts/x (omit to sweep all)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without moving files"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Archive terminal adrs/concepts/proposals pages into <dir>/_archive/ (sweep or targeted)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_wiki_archive(
                workspace_path=workspace_path,
                slugs=slugs or None,
                dry_run=dry_run,
            )
        )
    except (RuntimeError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        label = "[dry-run]" if dry_run else "[ok]"
        typer.echo(f"{label} Archived {len(result.moved)} page(s).")
        for item in result.moved:
            typer.echo(f"  moved: {item['src']} -> {item['dst']}")
        for skipped in result.skipped:
            typer.echo(f"  skipped: {skipped['slug']} — {skipped['reason']}")


@wiki_app.command(name="propagate-drift")
def propagate_drift(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Judge + report without writing notes or stamping anchors"),
    only: Optional[str] = typer.Option(None, "--only", help="Restrict to one entity (uri/stem) or curated page (slug)"),
    json_output: bool = typer.Option(False, "--json", help="Emit PropagateDriftResult as JSON"),
) -> None:
    """Propose curated-page updates for entities whose code changed (M4 drift producer)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        wiki, repo = resolve_wiki_and_repo(workspace_path)
    except (RuntimeError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    if repo is None:
        typer.echo("Error: repo path is required to propagate drift", err=True)
        raise typer.Exit(code=1)
    reader = open_reader(wiki.parent)
    try:
        result = asyncio.run(run_propagate_drift(wiki=wiki, repo=repo, reader=reader, dry_run=dry_run, only=only))
    finally:
        reader.close()

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        prefix = "[dry-run] " if result.dry_run else ""
        typer.echo(
            f"{prefix}propagate-drift: judged {result.pages_judged} page(s), "
            f"{result.entities_considered} entit(ies) considered, "
            f"{result.pages_stale} stale, {result.notes_written} note(s) "
            f"{'would be ' if result.dry_run else ''}written, "
            f"{result.pages_skipped_settled} skipped (settled)."
        )
        for row in result.proposals:
            refs = ", ".join(o["ref"] for o in row["origins"])
            typer.echo(f"  {row['kind']}-{row['target_slug']}  <- {refs}")


def main() -> None:
    wiki_app()


if __name__ == "__main__":
    main()
