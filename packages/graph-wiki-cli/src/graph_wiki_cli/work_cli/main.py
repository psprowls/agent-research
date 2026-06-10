"""gw work — work item management commands."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Optional

import typer
from graph_wiki_core.commands.work import (
    run_work_archive,
    run_work_file,
    run_work_lint,
    run_work_regen_index,
    run_work_status,
)

work_app = typer.Typer(name="work", help="Work item management.", no_args_is_help=True)


def _split_csv(value: str) -> list[str]:
    """Split a comma-separated option value into a trimmed, non-empty list."""
    return [part.strip() for part in value.split(",") if part.strip()]


@work_app.command()
def file(
    title: str = typer.Option(..., "--title", help="Work item title"),
    kind: str = typer.Option(..., "--kind", help="bug|tech-debt|test-gap|security|perf|feature|initiative|spike"),
    summary: str = typer.Option(..., "--summary", help="One-line summary (<=100 chars)"),
    status: str = typer.Option("open", "--status", help="open|accepted|in-progress|done|wont-fix|deferred"),
    affects: str = typer.Option("", "--affects", help="Comma-separated paths or package names"),
    severity: str = typer.Option("", "--severity", help="bug|security|perf — blank for feature/initiative/spike"),
    effort: str = typer.Option("", "--effort", help="xs|s|m|l|xl"),
    blast_radius: str = typer.Option("", "--blast-radius", help="file|package|domain|system"),
    target: str = typer.Option("", "--target", help="YYYY-QN or YYYY-MM"),
    owner: str = typer.Option("", "--owner", help="Owner handle"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """File a new work item into the wiki."""
    workspace_path = Path(workspace) if workspace else None

    try:
        result = asyncio.run(
            run_work_file(
                workspace_path=workspace_path,
                title=title,
                kind=kind,
                summary=summary,
                status=status,
                affects=_split_csv(affects),
                severity=severity or None,
                effort=effort or None,
                blast_radius=blast_radius or None,
                target=target or None,
                owner=owner or None,
                tags=_split_csv(tags),
            )
        )
    except (RuntimeError, ValueError, FileExistsError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Filed: {result.page_path}")


@work_app.command()
def lint(
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Run lifecycle lint over all work items."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_lint(workspace_path=workspace_path))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"Items checked: {result.total_items}")
        for f in result.findings:
            typer.echo(f"  [{f['severity']}] {f['slug']}: {f['rule_id']} — {f['message']}")
        if not result.findings:
            typer.echo("  [ok] No findings.")

    if any(f["severity"] == "error" for f in result.findings):
        raise typer.Exit(code=1)


@work_app.command()
def archive(
    slugs: Optional[list[str]] = typer.Argument(None, help="Specific slugs to archive"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without moving files"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Archive terminal work items (sweep or targeted)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_work_archive(
                workspace_path=workspace_path,
                slugs=slugs or None,
                dry_run=dry_run,
            )
        )
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        label = "[dry-run]" if dry_run else "[ok]"
        typer.echo(f"{label} Archived {len(result.moved)} item(s).")
        for item in result.moved:
            typer.echo(f"  moved: {item['src']} -> {item['dst']}")
        for skipped in result.skipped:
            typer.echo(f"  skipped: {skipped['slug']} — {skipped['reason']}")


@work_app.command()
def status(
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show work item status rollup."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_status(workspace_path=workspace_path))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        if result.sidecar_missing:
            typer.echo("[warn] work-index.json is missing. Run `gw work regen-index` first.", err=True)
            raise typer.Exit(code=4)
        for category, counts in result.counts.items():
            typer.echo(f"  {category}: {counts}")
        typer.echo(f"In-flight ({len(result.in_flight)}):")
        for item in result.in_flight:
            typer.echo(f"  - {item['slug']}: {item.get('title', '')}")
        typer.echo(f"Stuck ({len(result.stuck)}):")
        for item in result.stuck:
            typer.echo(f"  - {item['slug']}: {item.get('_age_days', '?')}d old")

    if result.sidecar_missing:
        raise typer.Exit(code=4)


@work_app.command(name="regen-index")
def regen_index(
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Rebuild work-index.json from wiki/work/*.md."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_regen_index(workspace_path=workspace_path))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Rebuilt sidecar: {result.sidecar_path} ({result.item_count} items)")
