"""Native Typer command surface for `gw util`.

Utility & diagnostic commands (trace, tokens, log) relocated out of the
top-level `gw` surface to keep the primary scan → ingest → query → lint list
focused. `trace` is read-only diagnostics; `tokens` and `log` are maintenance
writes. Bodies are pure relocations from cli.py — same options, exit codes, and
output shapes.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path
from typing import Optional

import typer
from graph_wiki_core.commands.log import run_log
from graph_wiki_core.commands.tokens import run_tokens_update
from graph_wiki_core.commands.trace import aggregate_trace, is_groupable, render_collapsed_group, render_trace_record

util_app = typer.Typer(
    name="util",
    help="Utility & diagnostic commands.",
    no_args_is_help=True,
)


# Highest trace `schema_version` this renderer was authored against (OBS-04 D-03).
# Records with a higher version still render (lenient consumer) but trigger a
# one-shot per-file stderr warning. Bump when the renderer is taught about a
# newer schema; producers in packages/subagent-runtime and commands/query.py stamp
# the integer at write time.
KNOWN_SCHEMA_VERSION = 1


@util_app.command()
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
    #         (event/kind) render full-line via render_trace_record.
    if expand:
        for record in records:
            typer.echo(render_trace_record(record))
    else:
        current_run: list[dict] = []

        def _flush() -> None:
            if not current_run:
                return
            if len(current_run) >= 2:
                typer.echo(render_collapsed_group(current_run))
            else:
                typer.echo(render_trace_record(current_run[0]))
            current_run.clear()

        for record in records:
            if not is_groupable(record):
                _flush()
                typer.echo(render_trace_record(record))
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

    agg = aggregate_trace(records)
    typer.echo("")
    typer.echo("=== Summary ===")
    typer.echo(f"Total records : {agg['total_records']}")
    typer.echo(f"Total tokens_in  : {agg['total_tokens_in']}")
    typer.echo(f"Total tokens_out : {agg['total_tokens_out']}")
    typer.echo("")
    typer.echo("Per-role breakdown:")
    for role, stats in agg["by_role"].items():
        typer.echo(f"  {role}: count={stats['count']} tokens_in={stats['tokens_in']} tokens_out={stats['tokens_out']}")

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
        typer.echo(f"  {role} / {model_short}: {count} items, {tin}->{tout} tokens, {cost_str}")


@util_app.command(name="log")
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


@util_app.command(name="tokens")
def tokens(
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Count without writing the tokens field"),
    json_output: bool = typer.Option(False, "--json", help="Emit the {updated, unchanged, skipped} buckets as JSON"),
) -> None:
    """Stamp `tokens: <count>` frontmatter across the wiki via offline tiktoken counting."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = run_tokens_update(workspace_path, dry_run=dry_run)
    except (RuntimeError, FileNotFoundError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(result, indent=2))
        return

    label = "Would update" if dry_run else "Updated"
    typer.echo(
        f"{label} {len(result['updated'])} • Unchanged {len(result['unchanged'])} • Skipped {len(result['skipped'])}"
    )
    for kind in ("updated", "skipped"):
        for rel in result[kind][:20]:
            typer.echo(f"  [{kind}] {rel}")


def main() -> None:
    util_app()


if __name__ == "__main__":
    main()
