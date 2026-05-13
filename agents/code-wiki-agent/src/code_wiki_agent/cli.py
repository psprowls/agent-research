from __future__ import annotations

import importlib.metadata
import json
from collections import defaultdict
from pathlib import Path

import typer

app = typer.Typer(
    name="code-wiki-agent",
    help="code-wiki-agent: AWS Bedrock-powered wiki maintenance CLI.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print version and exit."""
    v = importlib.metadata.version("code-wiki-agent")
    typer.echo(f"code-wiki-agent {v}")


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
    """Aggregate trace records into per-role token counts.

    Returns:
        {
            "by_role": {role: {"count": N, "tokens_in": X, "tokens_out": Y}},
            "total_records": N,
            "total_tokens_in": X,
            "total_tokens_out": Y,
        }
    Treats None token values as 0. Does not mutate input records.
    """
    by_role: dict = defaultdict(lambda: {"count": 0, "tokens_in": 0, "tokens_out": 0})
    total_tokens_in = 0
    total_tokens_out = 0

    for record in records:
        role = record.get("role", "unknown")
        tin = record.get("tokens_in") or 0
        tout = record.get("tokens_out") or 0
        by_role[role]["count"] += 1
        by_role[role]["tokens_in"] += tin
        by_role[role]["tokens_out"] += tout
        total_tokens_in += tin
        total_tokens_out += tout

    return {
        "by_role": dict(by_role),
        "total_records": len(records),
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
    }


@app.command()
def trace(file: Path) -> None:
    """Render a JSONL trace file as a human-readable timeline."""
    if not file.exists():
        typer.echo(f"trace file not found: {file}", err=True)
        raise typer.Exit(code=1)

    records: list[dict] = []
    for line_number, raw_line in enumerate(file.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            typer.echo(f"warning: skipping malformed JSONL line {line_number}: {exc.msg}", err=True)
            continue
        records.append(record)
        typer.echo(_render_trace_record(record))

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
    typer.echo("")
    typer.echo("Cost USD: (Phase 4)")


if __name__ == "__main__":
    app()
