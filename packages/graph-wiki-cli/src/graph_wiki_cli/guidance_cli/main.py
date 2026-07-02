"""Native Typer command surface for `gw guidance`.

Thin presentation over graph_wiki_core.commands.guidance_scan /
guidance_suggest. Mirrors the gw graph group-callback (--repo/--mode/--fmt);
bridges to the async core via asyncio.run.
"""

from __future__ import annotations

import asyncio
import dataclasses
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import typer
from graph_wiki_core.commands.guidance_archive import run_guidance_archive
from graph_wiki_core.commands.guidance_scan import run_guidance_scan
from graph_wiki_core.commands.guidance_suggest import run_guidance_suggest
from graph_wiki_core.commands.next_guidance import resolve_suggest_target
from workspace_io.config import resolve

OUTPUT_FORMATS = ["human", "json"]
RUN_MODES = ["workspace", "test"]

guidance_app = typer.Typer(
    name="guidance",
    help="Guidance suggestion operations (scan the corpus, suggest relevant pages).",
    no_args_is_help=True,
)


def _run(maybe_coro):
    if inspect.iscoroutine(maybe_coro):
        return asyncio.run(maybe_coro)
    return maybe_coro


def _ctx_args(ctx: typer.Context) -> SimpleNamespace:
    params = ctx.obj or {}
    repo = params.get("repo") or Path.cwd()
    mode = params.get("mode") or "workspace"
    workspace = resolve(repo, mode == "workspace").workspace
    return SimpleNamespace(repo=repo, fmt=params.get("fmt") or "human", mode=mode, workspace=workspace)


@guidance_app.callback()
def guidance_options(
    ctx: typer.Context,
    repo: Path = typer.Option(Path.cwd(), "--repo", help="Repo root (defaults to current dir)."),
    fmt: str = typer.Option("human", "--fmt", help="Output format (human|json)."),
    mode: str = typer.Option("workspace", "--mode", help="Workspace resolution mode."),
) -> None:
    """Guidance suggestion operations."""
    if fmt not in OUTPUT_FORMATS:
        raise typer.BadParameter(f"fmt must be one of: {', '.join(OUTPUT_FORMATS)}")
    if mode not in RUN_MODES:
        raise typer.BadParameter(f"mode must be one of: {', '.join(RUN_MODES)}")
    ctx.obj = {"repo": repo, "fmt": fmt, "mode": mode}


@guidance_app.command(name="scan")
def scan_cmd(
    ctx: typer.Context,
    package: Optional[str] = typer.Option(None, "--package", help="Restrict to one package's files."),
    path: Optional[List[str]] = typer.Option(None, "--path", help="Restrict to specific files (repeatable)."),
    limit: Optional[int] = typer.Option(None, "--limit", help="Cap the number of files classified."),
    full: bool = typer.Option(False, "--full", help="Re-classify all in-scope files."),
    seed_tags: bool = typer.Option(False, "--seed-tags", help="Seed tags.yaml from the corpus and exit."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Per-file detail."),
) -> None:
    """Build the file->vocabulary index via a Bedrock fan-out."""
    args = _ctx_args(ctx)
    result = _run(
        run_guidance_scan(
            workspace_path=args.workspace,
            repo_path=args.repo,
            package=package,
            paths=path,
            limit=limit,
            full=full,
            seed_tags=seed_tags,
        )
    )
    if args.fmt == "json":
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    elif seed_tags:
        typer.echo(f"Seeded {len(result.seeded_tags)} tags to wiki/guidance/tags.yaml")
    else:
        typer.echo(f"scanned {len(result.scanned)} / skipped {len(result.skipped)} / total {result.total}")
        if verbose:
            for rel in result.scanned:
                typer.echo(f"  scanned {rel}")
    for err in result.errors:
        typer.echo(f"  error: {err}", err=True)
    if result.errors:
        raise typer.Exit(code=3)


@guidance_app.command(name="suggest")
def suggest_cmd(
    ctx: typer.Context,
    message: str = typer.Argument(..., help="What you are about to do."),
    path: Optional[List[str]] = typer.Option(None, "--path", help="Working-set files (repeatable)."),
    role: Optional[str] = typer.Option(None, "--role", help="Filter guidance to a role: implement | review."),
    top: int = typer.Option(5, "--top", help="How many ranked pages to return."),
    candidates: int = typer.Option(12, "--candidates", help="Recall slate size before ranking."),
    assemble: bool = typer.Option(False, "--assemble", help="Also emit the concatenated top-N bodies."),
    budget: Optional[int] = typer.Option(None, "--budget", help="Token cap for --assemble."),
    file: str = typer.Option(
        "", "--file", help='Write assembled top-N guidance bodies to this path ("auto" resolves via --slug/--phase).'
    ),
    slug: Optional[str] = typer.Option(None, "--slug", help="Work item slug — enables --file auto."),
    phase: Optional[str] = typer.Option(None, "--phase", help="Work item phase — used with --slug for --file auto."),
    fmt: Optional[str] = typer.Option(None, "--fmt", help="Output format override (human|json)."),
) -> None:
    """Rank the guidance pages relevant to a coding task."""
    args = _ctx_args(ctx)
    if fmt is not None:
        if fmt not in OUTPUT_FORMATS:
            raise typer.BadParameter(f"fmt must be one of: {', '.join(OUTPUT_FORMATS)}")
        args.fmt = fmt
    if role is not None and role not in ("implement", "review"):
        raise typer.BadParameter("role must be one of: implement, review")
    target = resolve_suggest_target(file, args.workspace, slug, phase, role)
    result = _run(
        run_guidance_suggest(
            message,
            workspace_path=args.workspace,
            repo_path=args.repo,
            paths=path,
            role=role,
            top=top,
            candidates=candidates,
            assemble=assemble or target is not None,
            budget=budget,
        )
    )
    guidance_file: Optional[str] = None
    if target is not None and result.assembled is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.assembled, encoding="utf-8")
        guidance_file = str(target)
    if args.fmt == "json":
        payload = dataclasses.asdict(result)
        payload["guidance_file"] = guidance_file
        typer.echo(json.dumps(payload, indent=2))
        return
    for w in result.warnings:
        typer.echo(f"note: {w}", err=True)
    if not result.ranked:
        typer.echo("No relevant guidance found.")
        return
    for i, r in enumerate(result.ranked, start=1):
        signals = ", ".join(r.signals_fired) or "-"
        typer.echo(f"{i:>2} | [[guidance/{r.slug}]] | {r.relevance} | {signals} | {r.reason}")
    if result.assembled is not None:
        typer.echo("\n--- assembled guidance ---")
        typer.echo(result.assembled)


@guidance_app.command(name="archive")
def archive_cmd(
    ctx: typer.Context,
    slugs: List[str] = typer.Argument(..., help="Path-qualified <topic>/<slug> tokens to archive."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan without moving."),
) -> None:
    """Archive guidance pages into guidance/<topic>/_archive/ (targeted-only)."""
    args = _ctx_args(ctx)
    result = _run(
        run_guidance_archive(
            workspace_path=args.workspace,
            slugs=list(slugs),
            dry_run=dry_run,
        )
    )
    if args.fmt == "json":
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
        return
    prefix = "would archive" if result.dry_run else "archived"
    for m in result.moved:
        typer.echo(f"{prefix} {m['slug']}")
    for s in result.skipped:
        typer.echo(f"  skipped {s['slug']}: {s['reason']}", err=True)
    if not result.moved and not result.skipped:
        typer.echo("Nothing to archive.")
