"""Native Typer command surface for `gw wiki`.

Wiki-maintenance commands (query, log, lint, ingest) relocated from cli.py so
the `gw wiki` group mirrors the `gw graph` group structurally. Command bodies
delegate to graph_wiki_core.commands.*; this module owns only presentation.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from graph_io import exit_codes as _gio_exit_codes
from graph_io.store import read_only_connect
from graph_wiki_core.commands.ack_drift import run_ack_drift
from graph_wiki_core.commands.ingest import (
    IngestorGraphNotInitializedError,
    run_ingest_source,
    run_ingest_work_item,
)
from graph_wiki_core.commands.lint import run_lint
from graph_wiki_core.commands.log import run_log
from graph_wiki_core.commands.propagate_drift import run_propagate_drift
from graph_wiki_core.commands.proposals import run_list_proposals, run_set_proposal_status
from graph_wiki_core.commands.query import run_query
from wiki_io._workspace import resolve_wiki_and_repo
from workspace_io.paths import graph_dir

wiki_app = typer.Typer(
    name="wiki",
    help="Wiki maintenance operations.",
    no_args_is_help=True,
)


@wiki_app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)", min=3, max=10),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
    no_state_gate: bool = typer.Option(False, "--no-state-gate", help="No-op; query is read-only"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output (headless mode)"),
) -> None:
    """Query the wiki using hybrid BM25+embedding search with librarian fan-out."""
    # state gate is a no-op for query (read-only) — D-08
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_query(query_text, workspace_path, top_k=top_k))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    partial = result.pages_drilled < top_k

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(result.answer)
        if result.citations:
            typer.echo(f"\nCitations: {', '.join(result.citations)}")
        if not quiet:
            # Non-TTY mode: route meta line to stderr so stdout is clean for piping
            typer.echo(
                f"Pages drilled: {result.pages_drilled}",
                err=not sys.stdout.isatty(),
            )

    if partial:
        raise typer.Exit(code=3)


@wiki_app.command()
def log(
    op: str = typer.Option(..., "--op", help="Log operation type (scan/ingest/lint/create/update/delete/note/query)"),
    title: str = typer.Option(..., "--title", help="Short title for the log entry"),
    detail: Optional[str] = typer.Option(None, "--detail", help="Optional extended detail text"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit LogResult as JSON"),
) -> None:
    """Append a timestamped event to the wiki log.md."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_log(op=op, title=title, detail=detail, workspace_path=workspace_path))
    except (RuntimeError, FileNotFoundError, SystemExit) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[{result.date}] {result.op}: {result.title}")


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
        # Human-readable multi-section report
        typer.echo(f"Code Wiki lint — {result.wiki}")
        typer.echo(f"Total pages: {result.total_pages}")
        typer.echo(f"Open proposals: {result.open_proposals}")
        typer.echo("")

        def _section(label: str, items: list) -> None:
            sym = "OK" if not items else "WARN"
            typer.echo(f"[{sym}] {label}: {len(items)}")
            for item in items[:20]:
                typer.echo(f"   - {item}")
            typer.echo("")

        _section("Orphans", result.orphans)
        broken = [f"{src} -> [[{tgt}]]" for src, tgt in result.broken_links]
        _section("Broken wikilinks", broken)
        stale_items = [f"{p} (updated {d})" for p, d in result.stale]
        _section("Stale pages", stale_items)
        _section("Missing frontmatter", result.missing_frontmatter)

        if result.duplicate_titles:
            typer.echo(f"[WARN] Duplicate titles: {len(result.duplicate_titles)}")
            for title, keys in list(result.duplicate_titles.items())[:10]:
                typer.echo(f"   - '{title}': {keys}")
            typer.echo("")
        else:
            typer.echo("[OK] Duplicate titles: 0\n")

        if result.log_gap:
            typer.echo(
                f"[WARN] Log gap: last entry {result.log_gap.get('last_entry')} "
                f"({result.log_gap.get('days_ago')} days ago)\n"
            )
        else:
            typer.echo("[OK] Log gap: recent\n")

        _section("File map drift", result.file_map_drift)
        _section("Package sync drift", result.package_sync_drift)
        _section("Domain placement", result.domain_placement)
        _section("Workflow hints", result.workflow_hints)
        _section("Scanner heading drift", result.scanner_heading_drift)

        for group, findings in result.semantic_findings.items():
            _section(f"Semantic: {group}", findings)

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
    conn = read_only_connect(graph_dir(wiki.parent) / "code.db")
    try:
        result = asyncio.run(run_propagate_drift(wiki=wiki, repo=repo, conn=conn, dry_run=dry_run, only=only))
    finally:
        conn.close()

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


# ---------------------------------------------------------------------------
# ingest sub-app
# ---------------------------------------------------------------------------

ingest_app = typer.Typer(help="Ingest a source file or work item into the wiki.")
wiki_app.add_typer(ingest_app, name="ingest")


@ingest_app.command(name="source")
def ingest_source(
    path: Path = typer.Argument(..., help="Path to the source file to ingest"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit IngestResult as JSON"),
) -> None:
    """Ingest a source file into the wiki via the ingestor LLM."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_ingest_source(path, workspace_path))
    except IngestorGraphNotInitializedError as e:
        # Phase 40 / INGESTOR-02 / D-01: NOT_INITIALIZED has its own exit code
        # so script consumers can branch on it (3 vs generic 1).
        typer.echo(str(e), err=True)
        raise typer.Exit(code=_gio_exit_codes.NOT_INITIALIZED)
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Ingested: {result.page_path}")
        typer.echo(f"     source_type: {result.source_type}, slug: {result.slug}")
        if not result.frontmatter_parsed:
            typer.echo(
                "⚠ frontmatter did not parse — wrote Source page using the path-guess source_type",
                err=True,
            )
        if result.stripped_wikilinks:
            typer.echo(
                f"⚠ stripped {len(result.stripped_wikilinks)} unresolved wikilink(s): {result.stripped_wikilinks}",
                err=True,
            )
        if result.suggested_pages:
            typer.echo(f"     suggested {len(result.suggested_pages)} page(s):")
            for s in result.suggested_pages:
                mode = "update" if s.get("mode") == "update_existing" else "new"
                typer.echo(
                    f'       - {s.get("kind")} "{s.get("title")}" ({mode}, {s.get("status")}) -> {s.get("slug")}'
                )
        if not result.suggestions_parsed:
            typer.echo("⚠ suggestion pass degraded — wrote 0 suggestions", err=True)


@ingest_app.command(name="work-item")
def ingest_work_item(
    frontmatter: str = typer.Option(..., "--frontmatter", help="YAML frontmatter string for the work item"),
    body: str = typer.Option(..., "--body", help="Markdown body text for the work item"),
    slug: Optional[str] = typer.Option(None, "--slug", help="Page slug (derived from title if omitted)"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing page"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit IngestResult as JSON"),
) -> None:
    """File a structured work item into the wiki workspace."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_ingest_work_item(
                frontmatter_text=frontmatter,
                body=body,
                slug=slug,
                force=force,
                workspace_path=workspace_path,
            )
        )
    except (RuntimeError, ValueError, FileExistsError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Filed work item: {result.page_path}")
        typer.echo(f"     slug: {result.slug}")


def main() -> None:
    wiki_app()


if __name__ == "__main__":
    main()
