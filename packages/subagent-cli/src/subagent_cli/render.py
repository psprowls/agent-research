"""All colored/plain output for subagent-cli. The only module that prints."""

from __future__ import annotations

import json
from typing import IO, Any

from rich.console import Console
from rich.table import Table

# Module-level console; reconfigured by configure() at command start.
_console = Console()


def configure(no_color: bool = False, file: IO[str] | None = None) -> None:
    """(Re)build the module console. Honors --no-color; rich honors NO_COLOR itself."""
    global _console
    _console = Console(no_color=no_color, file=file, highlight=False, width=200)


def header(o: Any) -> None:
    _console.print(
        f"[cyan]●[/cyan] [bold cyan]{o.role}[/bold cyan]  →  [cyan]{o.model_id}[/cyan]  [dim](region {o.region})[/dim]"
    )
    _console.print(f"  [dim]item:[/dim] {o.item_id}")
    if o.note:
        _console.print(f"  [yellow]note:[/yellow] [dim]{o.note}[/dim]")


def _rule(label: str) -> None:
    _console.print(f"[dim]─── {label} ───[/dim]")


def prompt(o: Any, *, mode: str = "full") -> None:
    _rule("SYSTEM")
    _emit_block(o.system, mode)
    _rule("HUMAN")
    _emit_block(o.human, mode)


def _emit_block(text: str, mode: str) -> None:
    if mode == "short":
        lines = text.splitlines()
        head = "\n".join(lines[:8])
        _console.print(head)
        _console.print(f"[dim]… {len(lines)} lines total[/dim]")
    else:
        _console.print(text)


def response_start() -> None:
    _rule("RESPONSE  (streaming)")


def response_chunk(text: str) -> None:
    _console.print(text, end="", soft_wrap=True)


def response_end() -> None:
    _console.print("")


def parsed(o: Any) -> None:
    if o.parse_error is not None:
        _rule("PARSED ✗")
        _console.print(f"[red]{o.parse_error}[/red]")
        return
    if o.parsed is None:
        return
    _rule("PARSED ✓")
    try:
        body = json.dumps(o.parsed, indent=2, default=str)
    except (TypeError, ValueError):
        body = str(o.parsed)
    _console.print(f"[green]{body}[/green]")


def footer(o: Any) -> None:
    tin = "—" if o.tokens_in is None else o.tokens_in
    tout = "—" if o.tokens_out is None else o.tokens_out
    cost = "" if o.cost_usd is None else f" · ${o.cost_usd:.4f}"
    tail = " (interrupted)" if o.interrupted else ""
    _console.print(f"[dim]──── {tin} → {tout} tok · {o.latency_s:.2f}s{cost}{tail} ────[/dim]")


def error(message: str) -> None:
    _console.print(f"[bold red]error:[/bold red] {message}")


def info(message: str) -> None:
    _console.print(f"[dim]{message}[/dim]")


def list_table(rows: list[dict]) -> None:
    table = Table(show_header=True, header_style="bold cyan")
    for col in ("name", "kind", "role", "model_id", "region", "selector", "status"):
        table.add_column(col)
    for r in rows:
        table.add_row(
            r["name"],
            r.get("kind", ""),
            r["role"],
            r["model_id"],
            r["region"],
            r["selector"],
            r["status"],
        )
    _console.print(table)


def trace_line(line: str) -> None:
    """One compact line for --all fan-out (text from subagent_runtime.render_trace_record)."""
    _console.print(f"[dim]{line}[/dim]")


def json_record(o: Any) -> dict:
    try:
        parsed_val: Any = json.loads(json.dumps(o.parsed))
    except (TypeError, ValueError):
        parsed_val = None if o.parsed is None else str(o.parsed)
    return {
        "name": o.role,
        "role": o.role,
        "model_id": o.model_id,
        "region": o.region,
        "item_id": o.item_id,
        "system": o.system,
        "human": o.human,
        "raw": o.raw,
        "parsed": parsed_val,
        "parse_error": o.parse_error,
        "tokens_in": o.tokens_in,
        "tokens_out": o.tokens_out,
        "latency_s": o.latency_s,
        "cost_usd": o.cost_usd,
        "interrupted": o.interrupted,
        "note": o.note,
    }


def loop_result(o: Any) -> None:
    """Render a tool-loop outcome: header, summary line, answer, trace pointer."""
    _console.print(
        f"[cyan]●[/cyan] [bold cyan]{o.role}[/bold cyan]  →  [cyan]{o.model_id}[/cyan]  [dim](region {o.region})[/dim]"
    )
    _console.print(f"  [dim]item:[/dim] {o.item_id}")
    if o.note:
        _console.print(f"  [yellow]note:[/yellow] [dim]{o.note}[/dim]")

    structured = o.structured or {}
    status = o.trace_metadata.get("status", "—")
    batches = o.trace_metadata.get("worker_batches", "—")
    confidence = structured.get("confidence", "—")
    n_cites = len(structured.get("citations") or [])
    n_gaps = len(structured.get("gaps") or [])
    _console.print(
        f"  [dim]status[/dim] {status} · [dim]worker_batches[/dim] {batches} · "
        f"[dim]confidence[/dim] {confidence} · [dim]citations[/dim] {n_cites} · [dim]gaps[/dim] {n_gaps}"
    )

    _rule("ANSWER")
    _console.print(o.answer)

    where = o.trace_path if o.trace_path else "—"
    _console.print(f"[dim]──── trace: {where} · {o.latency_s:.2f}s ────[/dim]")


def loop_json_record(o: Any) -> dict:
    try:
        structured_val: Any = json.loads(json.dumps(o.structured, default=str))
    except (TypeError, ValueError):
        structured_val = None
    return {
        "name": o.role,
        "role": o.role,
        "model_id": o.model_id,
        "region": o.region,
        "item_id": o.item_id,
        "answer": o.answer,
        "structured": structured_val,
        "trace_metadata": dict(o.trace_metadata),
        "latency_s": o.latency_s,
        "trace_path": o.trace_path,
        "note": o.note,
    }
