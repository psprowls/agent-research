from __future__ import annotations

import asyncio
import dataclasses
import importlib.metadata
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import typer

from code_wiki_agent.commands.log import run_log
from code_wiki_agent.commands.query import run_query

app = typer.Typer(
    name="code-wiki-agent",
    help="code-wiki-agent: AWS Bedrock-powered wiki maintenance CLI.",
    no_args_is_help=True,
)


@app.callback()
def main_callback(
    config: Optional[Path] = typer.Option(None, "--config", help="Path to TOML config file"),
) -> None:
    """code-wiki-agent: AWS Bedrock-powered wiki maintenance."""
    if config is not None:
        import code_wiki_agent.config as _cfg_module

        _cfg_module._active_config = _cfg_module.load_config(config)


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


@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)", min=3, max=10),
    vault: str = typer.Option("", "--vault", help="Vault path (default: env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
    no_state_gate: bool = typer.Option(False, "--no-state-gate", help="No-op; query is read-only"),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress progress output (headless mode)"),
) -> None:
    """Query the wiki using hybrid BM25+embedding search with librarian fan-out."""
    # state gate is a no-op for query (read-only) — D-08
    vault_path = Path(vault) if vault else None
    try:
        result = asyncio.run(run_query(query_text, vault_path, top_k=top_k))
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


@app.command()
def log(
    op: str = typer.Option(..., "--op", help="Log operation type (scan/ingest/lint/create/update/delete/note/query)"),
    title: str = typer.Option(..., "--title", help="Short title for the log entry"),
    detail: Optional[str] = typer.Option(None, "--detail", help="Optional extended detail text"),
    vault: str = typer.Option("", "--vault", help="Vault path (default: CODE_WIKI_REAL_VAULT_PATH env var)"),
    json_output: bool = typer.Option(False, "--json", help="Emit LogResult as JSON"),
) -> None:
    """Append a timestamped event to the wiki log.md."""
    vault_path = Path(vault) if vault else None
    try:
        result = asyncio.run(run_log(op=op, title=title, detail=detail, vault_path=vault_path))
    except (RuntimeError, FileNotFoundError, SystemExit) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[{result.date}] {result.op}: {result.title}")


if __name__ == "__main__":
    app()
