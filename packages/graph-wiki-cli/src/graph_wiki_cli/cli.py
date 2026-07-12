from __future__ import annotations

import asyncio
import dataclasses
import importlib.metadata
import json
import os
import sys
from pathlib import Path

import click
import typer


def _ensure_uv_workspace() -> None:
    """Self-healing uv re-exec for `gw` bootstrap (HYGIENE-09).

    When the user invokes ``gw`` (e.g. via a stale shebang or a
    bare ``python -m graph_wiki_cli.cli`` outside the uv workspace), required
    dependencies like `graph_wiki_core` may fail to import with ModuleNotFoundError.
    To recover automatically, walk up from this file's own location
    (Path(__file__).resolve(), NOT sys.argv[0]) looking for a uv workspace root
    (indicated by `packages/wiki-io/pyproject.toml`), then re-exec the current
    process under ``uv run --project <workspace_root> python <sys.argv[0]> <args...>``.

    Loop prevention: GRAPH_WIKI_BOOTSTRAP_REEXEC=1 short-circuits the helper so
    a second re-exec cannot fire (if dependencies still fail to import after the
    first re-exec, the original ImportError must surface naturally).
    """
    if os.environ.get("GRAPH_WIKI_BOOTSTRAP_REEXEC"):
        return
    try:
        import graph_wiki_core  # noqa: F401  — probe only

        return
    except (ImportError, ModuleNotFoundError):
        pass

    here = Path(__file__).resolve().parent
    workspace_root: Path | None = None
    candidate = here
    while True:
        marker = candidate / "packages" / "wiki-io" / "pyproject.toml"
        if marker.is_file():
            workspace_root = candidate
            break
        if candidate == candidate.parent:
            break
        candidate = candidate.parent

    if workspace_root is None:
        return  # let the natural ImportError surface from the import that follows

    new_env = {**os.environ, "GRAPH_WIKI_BOOTSTRAP_REEXEC": "1"}
    os.execvpe(
        "uv",
        ["uv", "run", "--project", str(workspace_root), "python", sys.argv[0], *sys.argv[1:]],
        new_env,
    )


_ensure_uv_workspace()

# Imports below run after the uv re-exec bootstrap above, so they cannot move to
# the top of the module.
from graph_wiki_core.commands.archive_all import run_archive_all  # noqa: E402
from graph_wiki_core.commands.graph_query import exit_codes as _gio_exit_codes  # noqa: E402
from graph_wiki_core.commands.ingest import (  # noqa: E402
    IngestorGraphNotInitializedError,
    run_ingest_source,
)
from graph_wiki_core.commands.init import run_init  # noqa: E402
from graph_wiki_core.commands.lint_all import run_lint_all  # noqa: E402
from graph_wiki_core.commands.next_guidance import guidance_eligible, run_next_guidance  # noqa: E402
from graph_wiki_core.commands.query import run_query  # noqa: E402
from graph_wiki_core.commands.scan import run_scan  # noqa: E402
from graph_wiki_core.commands.work import run_work_advance, run_work_next  # noqa: E402

from graph_wiki_cli.config_cli.main import config_app  # noqa: E402
from graph_wiki_cli.graph_cli.main import graph_app  # noqa: E402
from graph_wiki_cli.guidance_cli.main import guidance_app  # noqa: E402
from graph_wiki_cli.lint_format import format_wiki_lint, format_work_lint  # noqa: E402
from graph_wiki_cli.logging_config import configure_verbose_logging  # noqa: E402
from graph_wiki_cli.util_cli.main import util_app  # noqa: E402
from graph_wiki_cli.wiki_cli.main import wiki_app  # noqa: E402
from graph_wiki_cli.work_cli.main import work_app  # noqa: E402

app = typer.Typer(
    name="gw",
    help="gw: AWS Bedrock-powered wiki maintenance CLI.",
    no_args_is_help=True,
)


@app.callback()
def _root(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help=(
            "Stream a live execution log to stderr (-v = INFO, -vv = DEBUG). "
            "stderr only — stdout stays clean, so `gw -v query ... --json | jq` "
            "still works. Independent of a command's own --quiet."
        ),
    ),
) -> None:
    """gw: AWS Bedrock-powered wiki maintenance CLI."""
    configure_verbose_logging(verbose)


def _json_safe_default(value: object) -> object:
    """Coerce an option default into a JSON-serializable value.

    Click/Typer option defaults can be non-JSON-native objects — most notably a
    ``Path`` (e.g. ``--repo`` defaults to ``Path.cwd()``), which crashed
    ``help <ns> --json`` with ``TypeError: Object of type PosixPath is not JSON
    serializable``. Keep JSON-native scalars and containers as-is; stringify
    everything else so every command's help can render.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe_default(item) for item in value]
    return str(value)


def _command_to_help_entry(command: click.Command, *, name: str) -> dict:
    """Return a stable, JSON-serializable help entry for a Click command."""
    options: list[dict] = []
    arguments: list[dict] = []
    for param in command.params:
        if isinstance(param, click.Option):
            options.append(
                {
                    "name": param.name,
                    "opts": list(param.opts),
                    "secondary_opts": list(param.secondary_opts),
                    "help": param.help or "",
                    "required": param.required,
                    "default": _json_safe_default(param.default),
                    "is_flag": param.is_flag,
                }
            )
        elif isinstance(param, click.Argument):
            arguments.append(
                {
                    "name": param.name,
                    "required": param.required,
                    "nargs": param.nargs,
                }
            )

    subcommands: list[dict] = []
    if isinstance(command, click.Group):
        for sub_name, sub_command in command.commands.items():
            if sub_command.hidden:
                continue
            subcommands.append(
                {
                    "name": sub_name,
                    "help": sub_command.get_short_help_str(limit=10_000),
                }
            )

    return {
        "name": name,
        "help": command.help or "",
        "short_help": command.get_short_help_str(limit=10_000),
        "usage": command.collect_usage_pieces(click.Context(command)),
        "arguments": arguments,
        "options": options,
        "commands": subcommands,
    }


def _json_help_payload(command_path: tuple[str, ...] = ()) -> dict:
    """Build machine-readable CLI help for the root app or a nested command."""
    root_command = typer.main.get_command(app)
    current = root_command
    resolved_path: list[str] = []

    for part in command_path:
        if not isinstance(current, click.Group) or part not in current.commands:
            available = sorted(current.commands) if isinstance(current, click.Group) else []
            raise click.ClickException(
                f"unknown command path: {' '.join(command_path)}"
                + (f" (available: {', '.join(available)})" if available else "")
            )
        current = current.commands[part]
        resolved_path.append(part)

    command_name = " ".join([root_command.name or "gw", *resolved_path])
    payload = _command_to_help_entry(current, name=command_name)
    payload["schema_version"] = 1
    payload["path"] = resolved_path
    return payload


@app.command(name="help")
def help_command(
    command: list[str] = typer.Argument(
        None,
        help="Optional command path to describe, for example: graph describe package.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable help as JSON."),
) -> None:
    """Show gw help, optionally as machine-readable JSON."""
    command_path = tuple(command or ())
    if json_output:
        try:
            typer.echo(json.dumps(_json_help_payload(command_path), indent=2))
        except click.ClickException as exc:
            typer.echo(json.dumps({"status": "error", "message": exc.message}, indent=2), err=True)
            raise typer.Exit(code=2)
        return

    ctx = click.Context(typer.main.get_command(app), info_name="gw")
    if not command_path:
        typer.echo(ctx.get_help())
        return

    try:
        payload = _json_help_payload(command_path)
    except click.ClickException as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"Usage: {payload['name']} {' '.join(payload['usage'])}".rstrip())
    if payload["help"]:
        typer.echo("")
        typer.echo(payload["help"])


@app.command()
def version() -> None:
    """Print version and exit."""
    v = importlib.metadata.version("graph-wiki-cli")
    typer.echo(f"gw {v}")


@app.command()
def bootstrap(
    topic: str = typer.Option(..., "--topic", help="Short description of the repository"),
    tool: str = typer.Option(..., "--tool", help="Schema file(s) to install (claude-code, codex, cursor, all, ...)"),
    force: bool = typer.Option(False, "--force", help="Overwrite non-empty target directory"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    repo: str = typer.Option("", "--repo", help="Override repo root (default: CWD walk-up)"),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Accepted for compatibility; has no effect (container detection removed).",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit InitResult as JSON"),
) -> None:
    """Bootstrap a wiki vault structure (creates raw/ and work/ siblings)."""
    workspace_path = Path(workspace) if workspace else None
    repo_path = Path(repo).resolve() if repo else None
    try:
        result = asyncio.run(
            run_init(
                topic=topic,
                tool=tool,
                force=force,
                interactive=interactive,
                workspace_path=workspace_path,
                repo_path=repo_path,
            )
        )
    except (RuntimeError, FileNotFoundError, SystemExit) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] Initialized wiki at: {result.wiki_path}")
        typer.echo(f"     raw/: {result.raw_path}")
        typer.echo(f"     work/: {result.work_path}")


@app.command()
def scan(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    no_file_map: bool = typer.Option(False, "--no-file-map", help="Skip per-package file-map generation"),
    max_depth: int = typer.Option(3, "--max-depth", help="Max directory depth for file map headers"),
    no_narrate: bool = typer.Option(
        False, "--no-narrate", help="Skip narrator/file-describer fan-out (structural-only, no Bedrock)"
    ),
    propagate_drift: bool = typer.Option(
        False, "--propagate-drift", help="After narration, propose curated-page updates for changed entities (M4)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit ScanResult as JSON"),
    emit_worklist: str = typer.Option(
        "", "--emit-worklist", help="Emit the commit-gated worklist JSON to this path and exit"
    ),
    apply_worklist: str = typer.Option("", "--apply-worklist", help="Apply a results JSON from this path"),
    worklist_path: str = typer.Option(
        "", "--worklist-path", help="Worklist JSON for --apply-worklist (default: sibling worklist.json)"
    ),
    short_head: str = typer.Option("", "--short-head", help="Stamp value (short HEAD sha) for --apply-worklist"),
) -> None:
    """Build the code graph and write one page per graph entity into wiki/entities/."""
    ws = Path(workspace) if workspace else None
    if emit_worklist:
        from graph_wiki_core.commands.scan import emit_scan_worklist

        result = asyncio.run(
            emit_scan_worklist(
                workspace_path=ws,
                repo_path=None,
                no_file_map=no_file_map,
                max_depth=max_depth,
                propagate=propagate_drift,
                out_path=Path(emit_worklist),
            )
        )
        typer.echo(json.dumps({"worklist_path": emit_worklist, "scan_result": dataclasses.asdict(result)}, indent=2))
        raise typer.Exit(code=3 if result.entity_errors else 0)
    if apply_worklist:
        from graph_wiki_core.commands.scan import apply_scan_worklist

        wl_path = Path(worklist_path) if worklist_path else Path(apply_worklist).parent / "worklist.json"
        applied = asyncio.run(
            apply_scan_worklist(
                workspace_path=ws,
                repo_path=None,
                results_path=Path(apply_worklist),
                worklist_path=wl_path,
                short_head=(short_head or None),
                propagate=propagate_drift,
            )
        )
        typer.echo(json.dumps(applied.to_dict(), indent=2))
        raise typer.Exit(code=3 if applied.entity_errors else 0)
    workspace_path = ws
    try:
        result = asyncio.run(
            run_scan(
                workspace_path=workspace_path,
                no_file_map=no_file_map,
                max_depth=max_depth,
                narrate=not no_narrate,
                propagate_drift=propagate_drift,
            )
        )
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        created = len(result.entities_created)
        updated = len(result.entities_updated)
        deleted = len(result.entities_deleted)
        typer.echo(f"Scan complete: entities +{created} ~{updated} -{deleted}")
        for err in result.entity_errors:
            typer.echo(f"  error: {err}", err=True)

    if result.entity_errors:
        raise typer.Exit(code=3)


@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)", min=3, max=10),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
    no_state_gate: bool = typer.Option(False, "--no-state-gate", help="No-op; query is read-only"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output (headless mode)"),
) -> None:
    """Query the wiki with agentic retrieval orchestration over wiki and code evidence."""
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


@app.command(name="ingest")
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
        if result.archived_to:
            typer.echo(f"[ok] Archived source → {result.archived_to}")
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
        if result.guidance_pages_written:
            typer.echo(f"     wrote {len(result.guidance_pages_written)} guidance page(s):")
            for g in result.guidance_pages_written:
                typer.echo(f"       - {g}")
        if not result.suggestions_parsed:
            typer.echo("⚠ suggestion pass degraded — wrote 0 suggestions", err=True)


@app.command()
def archive(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan without moving files"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json", help="Emit ArchiveAllResult as JSON"),
) -> None:
    """Sweep-archive curated pages and work items in one pass (wiki + work)."""
    workspace_path = Path(workspace) if workspace else None
    result = asyncio.run(run_archive_all(workspace_path=workspace_path, dry_run=dry_run))

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        label = "[dry-run]" if result.dry_run else "[ok]"
        if result.wiki is not None:
            typer.echo(f"wiki: {label} archived {len(result.wiki.moved)} page(s).")
            for item in result.wiki.moved:
                typer.echo(f"  moved: {item['src']} -> {item['dst']}")
            for skipped in result.wiki.skipped:
                typer.echo(f"  skipped: {skipped['slug']} — {skipped['reason']}")
        if result.work is not None:
            typer.echo(f"work: {label} archived {len(result.work.moved)} item(s).")
            for item in result.work.moved:
                typer.echo(f"  moved: {item['src']} -> {item['dst']}")
            for skipped in result.work.skipped:
                typer.echo(f"  skipped: {skipped['slug']} — {skipped['reason']}")
            for repointed in result.work.repointed:
                typer.echo(f"  repointed: {repointed}")
        for err in result.errors:
            typer.echo(f"  error: {err['command']}: {err['error']}", err=True)

    if result.errors:
        raise typer.Exit(code=1)


def _lint_all_failed(result) -> bool:
    """True if either lint pass surfaced error-severity findings or a run error."""
    if result.errors:
        return True
    if result.wiki is not None and result.wiki.errors:
        return True
    if result.work is not None and any(f["severity"] == "error" for f in result.work.findings):
        return True
    return False


@app.command()
def lint(
    stale_days: int = typer.Option(90, "--stale-days", help="Days before a page is flagged as stale"),
    log_gap_days: int = typer.Option(14, "--log-gap-days", help="Days before a log gap is flagged"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json", help="Emit LintAllResult as JSON"),
) -> None:
    """Run wiki lint and work-lifecycle lint in one pass (aggregated)."""
    workspace_path = Path(workspace) if workspace else None
    result = asyncio.run(run_lint_all(workspace_path=workspace_path, stale_days=stale_days, log_gap_days=log_gap_days))

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2, default=list))
    else:
        if result.wiki is not None:
            for line in format_wiki_lint(result.wiki):
                typer.echo(line)
        if result.work is not None:
            typer.echo("")
            typer.echo("=== Work lifecycle ===")
            for line in format_work_lint(result.work):
                typer.echo(line)
        for err in result.errors:
            typer.echo(f"  error: {err['command']}: {err['error']}", err=True)

    if _lint_all_failed(result):
        raise typer.Exit(code=1)


@app.command(name="next")
def next_cmd(
    slug: str = typer.Argument(..., help="Work item slug (file stem under wiki/work/)"),
    human: bool = typer.Option(False, "--human", help="Human-readable ranked guidance list"),
    json_output: bool = typer.Option(False, "--json", help="Emit the work-next envelope + guidance as JSON"),
    file: str = typer.Option(
        "auto",
        "--file",
        help='Write the assembled guidance bundle to this path ("auto" = canonical '
        'work/<slug>/NN-<phase>-guidance.md; "" = skip writing).',
    ),
    budget: int = typer.Option(0, "--budget", help="Token cap for the --file bundle (0 = unlimited)"),
    top: int = typer.Option(5, "--top", help="How many ranked guidance pages to attach"),
    no_rank: bool = typer.Option(False, "--no-rank", help="Force deterministic recall-only ordering"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
) -> None:
    """Compute the next workflow action AND attach phase-relevant guidance (read-only)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        wn = asyncio.run(run_work_next(workspace_path=workspace_path, slug=slug))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    guidance: list[dict] = []
    guidance_warnings: list[str] = []
    guidance_file: str | None = None
    if guidance_eligible(wn):
        ng = asyncio.run(
            run_next_guidance(
                slug,
                workspace_path=workspace_path,
                top=top,
                assemble=bool(file),
                budget=budget or None,
                no_rank=no_rank,
                phase=wn.phase,
                file=file,
            )
        )
        guidance = [dataclasses.asdict(r) for r in ng.ranked]
        guidance_warnings = list(ng.warnings)
        if ng.target_path is not None and ng.assembled is not None:
            ng.target_path.parent.mkdir(parents=True, exist_ok=True)
            ng.target_path.write_text(ng.assembled, encoding="utf-8")
            guidance_file = str(ng.target_path)

    if json_output:
        payload = dataclasses.asdict(wn)
        payload["guidance"] = guidance
        payload["guidance_warnings"] = guidance_warnings
        payload["guidance_file"] = guidance_file
        typer.echo(json.dumps(payload, indent=2))
    if human or not json_output:
        typer.echo(f"{wn.slug}: kind={wn.kind} status={wn.status} phase={wn.phase}")
        if wn.action:
            typer.echo(f"  dispatch: {wn.action['skill']} — {wn.action['reason']}")
        if wn.artifact:
            typer.echo(f"  artifact: {wn.artifact['path']}")
        for b in wn.blockers:
            typer.echo(f"  blocked: {b}")
        if guidance:
            typer.echo("  guidance:")
            for i, r in enumerate(guidance, start=1):
                signals = ", ".join(r["signals_fired"]) or "-"
                typer.echo(f"   {i:>2} | [[guidance/{r['slug']}]] | {r['relevance']} | {signals} | {r['reason']}")
        if guidance_file:
            typer.echo(f"  guidance bundle: {guidance_file}")
        for w in guidance_warnings:
            typer.echo(f"  note: {w}", err=True)

    if wn.blockers:
        raise typer.Exit(code=1)


@app.command()
def advance(
    slug: str = typer.Argument(..., help="Work item slug (file stem under wiki/work/)"),
    effort: str = typer.Option("", "--effort", help="xtra-small|small|medium|large|xtra-large"),
    owner: str = typer.Option("", "--owner", help="Owner handle"),
    resolved_in: str = typer.Option("", "--resolved-in", help="PR/commit reference"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Apply the routing table's next transition for a work item (passthrough to `gw work advance`)."""
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


# config command namespace: the sole programmatic writer for graph-wiki config.
app.add_typer(config_app, name="config")

# graph command namespace: native Typer subapp for code-graph operations.
app.add_typer(graph_app, name="graph")

# guidance command namespace: native Typer subapp for guidance scan/suggest.
app.add_typer(guidance_app, name="guidance")

# wiki command namespace: native Typer subapp for wiki-maintenance operations.
app.add_typer(wiki_app, name="wiki")

# work command namespace: native Typer subapp for work item management.
app.add_typer(work_app, name="work")

# util command namespace: native Typer subapp for secondary/diagnostic commands.
app.add_typer(util_app, name="util")


if __name__ == "__main__":
    app()
