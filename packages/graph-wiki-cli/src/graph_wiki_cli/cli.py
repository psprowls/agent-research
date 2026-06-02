from __future__ import annotations

import asyncio
import dataclasses
import importlib.metadata
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import click
import typer


def _ensure_uv_workspace() -> None:
    """Self-healing uv re-exec for `gw` bootstrap (HYGIENE-09).

    When the user invokes ``gw`` (e.g. via a stale shebang or a
    bare ``python -m graph_wiki_cli.cli`` outside the uv workspace), the
    `wiki_io` import can fail with ModuleNotFoundError. To recover automatically,
    walk up from this file's own location (Path(__file__).resolve(), NOT
    sys.argv[0]) looking for `<ancestor>/packages/wiki-io/pyproject.toml`, then
    re-exec the current process under
    ``uv run --project <ancestor>/packages/wiki-io python <sys.argv[0]> <args...>``.

    Loop prevention: GRAPH_WIKI_BOOTSTRAP_REEXEC=1 short-circuits the helper so
    a second re-exec cannot fire (if wiki_io still fails to import after the
    first re-exec, the original ImportError must surface naturally).
    """
    if os.environ.get("GRAPH_WIKI_BOOTSTRAP_REEXEC"):
        return
    try:
        import wiki_io  # noqa: F401  — probe only
        return
    except (ImportError, ModuleNotFoundError):
        pass

    here = Path(__file__).resolve().parent
    workspace_pkg: Path | None = None
    candidate = here
    while True:
        marker = candidate / "packages" / "wiki-io" / "pyproject.toml"
        if marker.is_file():
            workspace_pkg = marker.parent
            break
        if candidate == candidate.parent:
            break
        candidate = candidate.parent

    if workspace_pkg is None:
        return  # let the natural ImportError surface from the import that follows

    new_env = {**os.environ, "GRAPH_WIKI_BOOTSTRAP_REEXEC": "1"}
    os.execvpe(
        "uv",
        ["uv", "run", "--project", str(workspace_pkg), "python", sys.argv[0], *sys.argv[1:]],
        new_env,
    )


_ensure_uv_workspace()

from graph_wiki_cli.graph_cli.main import graph_app
from graph_wiki_cli.wiki_cli.main import wiki_app
from graph_wiki_core.commands.init import run_init
from graph_wiki_core.commands.scan import run_scan

app = typer.Typer(
    name="gw",
    help="gw: AWS Bedrock-powered wiki maintenance CLI.",
    no_args_is_help=True,
)

# Highest trace `schema_version` this renderer was authored against (OBS-04 D-03).
# Records with a higher version still render (lenient consumer) but trigger a
# one-shot per-file stderr warning. Bump when the renderer is taught about a
# newer schema; producers in packages/subagent-runtime and commands/query.py stamp
# the integer at write time.
KNOWN_SCHEMA_VERSION = 1


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
                    "default": param.default,
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


def _render_trace_record(record: dict) -> str:
    """Return a single-line human-readable representation of a trace record.

    Fields: timestamp role model_id(last 30 chars) item_id(first 40 chars)
            status latency_ms tokens_in -> tokens_out
    Error records append: ERROR: <error message>
    Missing fields are substituted with '-' so .get() never raises KeyError.
    """
    timestamp = record.get("timestamp", "-")
    role = record.get("role", "-")
    model_id = record.get("model_id", "-")
    model_short = model_id[-30:] if model_id != "-" else "-"
    item_id = record.get("item_id", "-")
    item_short = item_id[:40] if item_id != "-" else "-"
    status = record.get("status", "-")
    latency_ms = record.get("latency_ms", "-")
    tokens_in = record.get("tokens_in", "-")
    tokens_out = record.get("tokens_out", "-")

    line = (
        f"[{timestamp}] {role} {model_short} {item_short} "
        f"{status} {latency_ms}ms {tokens_in}->{tokens_out}"
    )
    if record.get("status") == "error":
        line += f"  ERROR: {record.get('error', '')}"
    return line


def _aggregate_trace(records: list[dict]) -> dict:
    """Aggregate trace records into per-role and per-(role, model_id) breakdowns.

    Returns:
        {
            "by_role": {role: {"count": N, "tokens_in": X, "tokens_out": Y}},
            "by_role_model": {
                "<role>|<model_id>": {
                    "role": str, "model_id": str,
                    "count": N, "tokens_in": X, "tokens_out": Y,
                    "cost_usd_sum": float,  # sum of non-null cost_usd
                    "unknown_cost_count": N,  # records whose cost_usd is None
                }
            },
            "total_records": N,
            "total_tokens_in": X,
            "total_tokens_out": Y,
        }

    Treats None token values as 0. Does not mutate input records.

    Per-item discriminator (D-11): a record contributes to ``by_role_model``
    only when it has NO ``event`` key AND no ``kind`` key. Per-role / total
    counters preserve their original behavior (every record counted) to keep
    the Summary block's "Total records" line backward-compatible.
    """
    by_role: dict = defaultdict(lambda: {"count": 0, "tokens_in": 0, "tokens_out": 0})
    by_role_model: dict = defaultdict(
        lambda: {
            "role": "",
            "model_id": "",
            "count": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd_sum": 0.0,
            "unknown_cost_count": 0,
        }
    )
    total_tokens_in = 0
    total_tokens_out = 0

    for record in records:
        tin = record.get("tokens_in") or 0
        tout = record.get("tokens_out") or 0
        total_tokens_in += tin
        total_tokens_out += tout

        # Per-item-only rollup: exclude event/kind discriminator records from
        # BOTH by_role and by_role_model passes (D-11; WR-02 fix). Without this
        # guard on the by_role pass, kind:query_summary records (which lack a
        # `role` field) synthesized a phantom 'unknown:' bucket in the Per-role
        # breakdown — visible in pre-fix snapshots as
        # `unknown: count=1 tokens_in=0 tokens_out=0`.
        if not _is_groupable(record):
            continue

        role = record.get("role", "unknown")
        by_role[role]["count"] += 1
        by_role[role]["tokens_in"] += tin
        by_role[role]["tokens_out"] += tout

        model_id = record.get("model_id", "unknown")
        key = f"{role}|{model_id}"
        bucket = by_role_model[key]
        bucket["role"] = role
        bucket["model_id"] = model_id
        bucket["count"] += 1
        bucket["tokens_in"] += tin
        bucket["tokens_out"] += tout
        cost = record.get("cost_usd")
        if cost is None:
            bucket["unknown_cost_count"] += 1
        else:
            # Guard against non-numeric cost_usd values (T-09-06): raise loudly
            # rather than silently mis-sum. Production writers always emit
            # float or None; a string here indicates a malformed producer.
            bucket["cost_usd_sum"] += float(cost)

    return {
        "by_role": dict(by_role),
        "by_role_model": dict(by_role_model),
        "total_records": len(records),
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
    }


def _render_collapsed_group(records: list[dict]) -> str:
    """Render a collapsed-group summary line (D-13) for a run of ≥2 same-(role, model_id) records.

    Shape:
        [<ts_first> .. <ts_last>] <role> / <model_short> x<N>: <status-breakdown>, <tin>-><tout> tokens, <cost>

    - <model_short> is the last 30 chars of `model_id` (mirroring the
      cost-rollup convention at cli.py:345); `-` when model_id is missing.
    - <status-breakdown> includes only nonzero categories in canonical order:
      success → error → cancelled, joined by ' / '.
    - <cost> is `$<sum:.6f>` with optional ` (+<K> unknown)` when some records
      have null cost_usd; `$n/a (<N> unknown)` when ALL records are null.
    - Timestamps are the literal `timestamp` field of the first and last
      records in the run (ISO-8601 as written).
    """
    n = len(records)
    ts_first = records[0].get("timestamp", "-")
    ts_last = records[-1].get("timestamp", "-")
    role = records[0].get("role", "-")
    model_id = records[0].get("model_id", "-")
    model_short = model_id[-30:] if model_id and model_id != "-" else "-"

    # Status breakdown — only nonzero categories, canonical order. WR-03 fix:
    # statuses outside {success, error, cancelled} land in an `other` bucket
    # (rather than silently dropping) so future producer-added statuses surface
    # loudly. The `{n} unknown` fallback replaces the previously misleading
    # zero-success fallback; with the `other` bucket in place it is unreachable
    # for any N>=1 run and acts only as a defensive guard.
    counts = {"success": 0, "error": 0, "cancelled": 0, "other": 0}
    for r in records:
        status = r.get("status")
        if status in ("success", "error", "cancelled"):
            counts[status] += 1
        else:
            counts["other"] += 1
    breakdown_parts = [
        f"{counts[k]} {k}"
        for k in ("success", "error", "cancelled", "other")
        if counts[k]
    ]
    breakdown = " / ".join(breakdown_parts) if breakdown_parts else f"{n} unknown"

    # Token sums (defensive defaults).
    sum_tin = sum((r.get("tokens_in") or 0) for r in records)
    sum_tout = sum((r.get("tokens_out") or 0) for r in records)

    # Cost sum + null tracking.
    cost_sum = 0.0
    unknown = 0
    for r in records:
        c = r.get("cost_usd")
        if c is None:
            unknown += 1
        else:
            cost_sum += float(c)

    if unknown == n:
        cost_str = f"$n/a ({n} unknown)"
    elif unknown > 0:
        cost_str = f"${cost_sum:.6f} (+{unknown} unknown)"
    else:
        cost_str = f"${cost_sum:.6f}"

    return (
        f"[{ts_first} .. {ts_last}] {role} / {model_short} x{n}: {breakdown}, "
        f"{sum_tin}->{sum_tout} tokens, {cost_str}"
    )


def _is_groupable(record: dict) -> bool:
    """A record is groupable iff it has NO 'event' key and NO 'kind' key (D-11)."""
    return "event" not in record and "kind" not in record


@app.command()
def trace(
    file: Path,
    expand: bool = typer.Option(
        False,
        "--expand",
        help="Disable consecutive-same-role collapsing; render every record full-line.",
    ),
) -> None:
    """Render a JSONL trace file as a human-readable timeline."""
    if not file.exists():
        typer.echo(f"trace file not found: {file}", err=True)
        raise typer.Exit(code=1)

    records: list[dict] = []
    # Per-file one-shot flags for schema_version-aware warnings (OBS-04 D-03/D-04).
    # Both warnings are stderr-only, never alter the exit code, and emit at most
    # once per file regardless of how many qualifying records appear.
    warned_v0 = False
    warned_newer = False
    for line_number, raw_line in enumerate(file.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            typer.echo(f"warning: skipping malformed JSONL line {line_number}: {exc.msg}", err=True)
            continue
        # D-04: v0 inference for records missing `schema_version` (pre-Phase-9 shape).
        # D-03: lenient consumer for records with `schema_version` > KNOWN_SCHEMA_VERSION.
        # Non-integer `schema_version` values are silently rendered best-effort
        # (T-09-15: lenient policy).
        if "schema_version" not in record:
            if not warned_v0:
                typer.echo(
                    f"warning: trace file {file} contains unversioned records; "
                    f"treating as schema_version=0 (pre-Phase-9 shape); "
                    f"rendering best-effort",
                    err=True,
                )
                warned_v0 = True
        else:
            sv = record["schema_version"]
            if isinstance(sv, int) and sv > KNOWN_SCHEMA_VERSION and not warned_newer:
                typer.echo(
                    f"warning: trace schema_version {sv} is newer than supported "
                    f"({KNOWN_SCHEMA_VERSION}); rendering best-effort",
                    err=True,
                )
                warned_newer = True
        records.append(record)

    # Emit timeline AFTER all records are parsed.
    # Mode A: --expand — one line per record (D-14 / D-08 invariant).
    # Mode B: default — collapse maximal runs (N>=2) of consecutive groupable
    #         records sharing the same `role` (D-11/D-12); emit one summary
    #         line per group; isolated records and non-groupable records
    #         (event/kind) render full-line via _render_trace_record.
    if expand:
        for record in records:
            typer.echo(_render_trace_record(record))
    else:
        current_run: list[dict] = []

        def _flush() -> None:
            if not current_run:
                return
            if len(current_run) >= 2:
                typer.echo(_render_collapsed_group(current_run))
            else:
                typer.echo(_render_trace_record(current_run[0]))
            current_run.clear()

        for record in records:
            if not _is_groupable(record):
                _flush()
                typer.echo(_render_trace_record(record))
                continue
            # Groupable: extend or start a run. CR-01 fix — key by
            # (role, model_id) so mixed-model fan-outs render as distinct
            # lines and parity with the cost rollup at cli.py:329-345 is
            # preserved.
            if (
                current_run
                and current_run[-1].get("role") == record.get("role")
                and current_run[-1].get("model_id") == record.get("model_id")
            ):
                current_run.append(record)
            else:
                _flush()
                current_run.append(record)
        _flush()

    agg = _aggregate_trace(records)
    typer.echo("")
    typer.echo("=== Summary ===")
    typer.echo(f"Total records : {agg['total_records']}")
    typer.echo(f"Total tokens_in  : {agg['total_tokens_in']}")
    typer.echo(f"Total tokens_out : {agg['total_tokens_out']}")
    typer.echo("")
    typer.echo("Per-role breakdown:")
    for role, stats in agg["by_role"].items():
        typer.echo(
            f"  {role}: count={stats['count']} "
            f"tokens_in={stats['tokens_in']} tokens_out={stats['tokens_out']}"
        )

    # Per-(role, model_id) cost rollup (OBS-05; D-07/D-08/D-09/D-15).
    # Sort:
    #   1. Groups with at least one known cost first, by descending cost_usd_sum
    #   2. Fully-null (n/a) groups last
    #   3. Tie-break: ascending (role, model_id)
    by_role_model = agg.get("by_role_model", {})
    known: list[dict] = []
    unknown: list[dict] = []
    for stats in by_role_model.values():
        if stats["count"] > stats["unknown_cost_count"]:
            known.append(stats)
        else:
            unknown.append(stats)
    known.sort(key=lambda s: (-s["cost_usd_sum"], s["role"], s["model_id"]))
    unknown.sort(key=lambda s: (s["role"], s["model_id"]))

    typer.echo("")
    typer.echo("Cost rollup (per role/model):")
    for stats in known + unknown:
        role = stats["role"]
        model_id = stats["model_id"]
        model_short = model_id[-30:] if model_id and model_id != "-" else "-"
        count = stats["count"]
        tin = stats["tokens_in"]
        tout = stats["tokens_out"]
        unk = stats["unknown_cost_count"]
        if count == unk:
            # Fully-null group: $n/a with explicit count
            cost_str = f"$n/a ({unk} unknown)"
        else:
            cost_str = f"${stats['cost_usd_sum']:.6f}"
            if unk:
                cost_str += f" (+{unk} unknown)"
        typer.echo(
            f"  {role} / {model_short}: {count} items, "
            f"{tin}->{tout} tokens, {cost_str}"
        )




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
        help="Prompt for ambiguous container classifications (default: silent-skip).",
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
    json_output: bool = typer.Option(False, "--json", help="Emit ScanResult as JSON"),
) -> None:
    """Walk repo, diff packages vs vault, create/update stubs via scanner fan-out."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_scan(workspace_path=workspace_path, no_file_map=no_file_map, max_depth=max_depth))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        added = len(result.added)
        updated = len(result.updated)
        deleted = len(result.deleted)
        typer.echo(f"Scan complete: +{added} ~{updated} -{deleted}")
        for err in result.errors:
            typer.echo(f"  error: {err}", err=True)

    if result.errors:
        raise typer.Exit(code=3)



# graph command namespace: native Typer subapp for code-graph operations.
app.add_typer(graph_app, name="graph")

# wiki command namespace: native Typer subapp for wiki-maintenance operations.
app.add_typer(wiki_app, name="wiki")


if __name__ == "__main__":
    app()
