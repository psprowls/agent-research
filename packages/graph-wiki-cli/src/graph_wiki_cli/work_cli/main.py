"""gw work — work item management commands."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Optional

import typer
from graph_wiki_core.commands.orchestrate import run_work_orchestrate
from graph_wiki_core.commands.work import (
    run_work_advance,
    run_work_archive,
    run_work_file,
    run_work_lint,
    run_work_next,
    run_work_regen_index,
    run_work_status,
)

from graph_wiki_cli.lint_format import format_work_lint

work_app = typer.Typer(name="work", help="Work item management.", no_args_is_help=True)


def _split_csv(value: str) -> list[str]:
    """Split a comma-separated option value into a trimmed, non-empty list."""
    return [part.strip() for part in value.split(",") if part.strip()]


@work_app.command()
def file(
    title: str = typer.Option(..., "--title", help="Work item title"),
    kind: str = typer.Option(..., "--kind", help="bug|tech-debt|test-gap|security|perf|feature|epic|spike"),
    summary: str = typer.Option(..., "--summary", help="One-line summary (<=100 chars)"),
    status: str = typer.Option(
        "open", "--status", help="open|accepted|in-progress|mitigated|resolved|wontfix|superseded"
    ),
    affects: str = typer.Option("", "--affects", help="Comma-separated paths or package names"),
    severity: str = typer.Option("", "--severity", help="bug|security|perf — blank for feature/epic/spike"),
    effort: str = typer.Option("", "--effort", help="xtra-small|small|medium|large|xtra-large"),
    blast_radius: str = typer.Option("", "--blast-radius", help="file|package|domain|system"),
    target: str = typer.Option("", "--target", help="YYYY-QN or YYYY-MM"),
    owner: str = typer.Option("", "--owner", help="Owner handle"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    parent: str = typer.Option("", "--parent", help="Parent slug (epic or feature); this item becomes its child"),
    depends_on: str = typer.Option("", "--depends-on", help="Comma-separated sibling slugs that must finish first"),
    slug_words: str = typer.Option("", "--slug-words", help="1-4 words for the slug (e.g. 'shorten work item slugs')"),
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
                parent=parent or None,
                depends_on=_split_csv(depends_on) or None,
                slug_words=slug_words or None,
            )
        )
    except (RuntimeError, ValueError, FileExistsError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Filed: {result.page_path}")
        for w in result.warnings:
            typer.echo(f"[warn] {w}", err=True)


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
        for line in format_work_lint(result):
            typer.echo(line)

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
        for repointed in result.repointed:
            typer.echo(f"  repointed: {repointed}")


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
        if result.epics:
            typer.echo(f"Epics ({len(result.epics)}):")
            for e in result.epics:
                typer.echo(f"  - {e['slug']}: {e['terminal']}/{e['total']} children terminal, {e['blocking']} blocking")

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


@work_app.command(name="next")
def next_cmd(
    slug: str = typer.Argument(..., help="Work item slug (file stem under wiki/work/)"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
    descend: bool = typer.Option(
        False, "--descend", help="When the item is waiting on children, switch to the next actionable child"
    ),
) -> None:
    """Compute the next workflow action for a work item (read-only)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_next(workspace_path=workspace_path, slug=slug, descend=descend))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"{result.slug}: kind={result.kind} status={result.status} phase={result.phase}")
        if result.descent:
            typer.echo(f"  descent: {' -> '.join(result.descent['path'])}")
        if result.action:
            typer.echo(f"  dispatch: {result.action['skill']} — {result.action['reason']}")
        if result.artifact:
            typer.echo(f"  artifact: {result.artifact['path']}")
        for b in result.blockers:
            typer.echo(f"  blocked: {b}")

    if result.blockers:
        raise typer.Exit(code=1)


@work_app.command()
def advance(
    slug: str = typer.Argument(..., help="Work item slug (file stem under wiki/work/)"),
    effort: str = typer.Option("", "--effort", help="xtra-small|small|medium|large|xtra-large"),
    owner: str = typer.Option("", "--owner", help="Owner handle"),
    resolved_in: str = typer.Option("", "--resolved-in", help="PR/commit reference"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Apply the routing table's next transition for a work item (single mutation point)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_work_advance(
                workspace_path=workspace_path,
                slug=slug,
                effort=effort or None,
                owner=owner or None,
                resolved_in=resolved_in or None,
            )
        )
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] {result.slug}: phase={result.phase} status={result.status}")
        for key, change in result.applied.items():
            typer.echo(f"  {key}: {change[0]} -> {change[1]}")
        for key, value in result.stamped.items():
            typer.echo(f"  stamped {key}: {value}")
        for f in result.findings:
            typer.echo(f"  [{f['severity']}] {f['rule_id']} — {f['message']}")


@work_app.command()
def orchestrate(
    slug: str = typer.Argument(..., help="Root work item slug to plan dispatches for"),
    live: str = typer.Option("", "--live", help="Comma-separated running dispatch keys (<slug>#<phase>)"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Compute the auto-drive dispatch plan for a work item's subtree (read-only)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_work_orchestrate(workspace_path=workspace_path, slug=slug, live=tuple(_split_csv(live)))
        )
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        slots_display = f"{result.slots_free}/{result.max_parallel}"
        typer.echo(f"{result.slug}: terminal={result.terminal} slots_free={slots_display}")
        for d in result.dispatches:
            wt_action = d["worktree"]["action"]
            mode = d["mode"]
            model = d["model"]
            typer.echo(f"  dispatch {d['key']}: {d['skill']} mode={mode} model={model} worktree={wt_action}")
        for a in result.advances:
            typer.echo(f"  advance {a['slug']}: {a['reason']}")
        for b in result.blocked:
            typer.echo(f"  blocked {b['slug']} ({b['kind']}): {b['reason']}")
        for w in result.warnings:
            typer.echo(f"  [warn] {w}", err=True)
