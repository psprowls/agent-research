"""Generic subagent invocation: stream a model call, aggregate usage, parse."""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from graph_wiki_core.roles import load_role_config, make_llm
from langchain_core.messages import HumanMessage, SystemMessage
from subagent_runtime.pool import SubagentPool, TaskResult
from subagent_runtime.pricing import cost_for_usage
from workspace_io import paths as ws_paths

from .adapters.base import Adapter, LoopAdapter, LoopOutcome, RunContext


@dataclass
class RunOutcome:
    item_id: str
    role: str
    model_id: str
    region: str
    system: str
    human: str
    raw: str
    parsed: Any | None
    parse_error: str | None
    tokens_in: int | None
    tokens_out: int | None
    latency_s: float
    cost_usd: float | None
    interrupted: bool = False
    note: str | None = None


def _coerce_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # langchain content-block lists
        out = []
        for block in content:
            if isinstance(block, str):
                out.append(block)
            elif isinstance(block, dict):
                out.append(str(block.get("text", "")))
        return "".join(out)
    return str(content or "")


def _usage(agg: Any) -> tuple[int | None, int | None]:
    meta = getattr(agg, "usage_metadata", None)
    if isinstance(meta, dict):
        return meta.get("input_tokens"), meta.get("output_tokens")
    return None, None


def _cost(model_id: str, tin: int | None, tout: int | None) -> float | None:
    if tin is None or tout is None:
        return None
    try:
        # UnknownModelError is a subclass of KeyError.
        return cost_for_usage(model_id, {"input": tin, "output": tout})
    except KeyError:
        return None


async def stream_and_parse(
    llm: Any,
    *,
    system: str,
    human: str,
    parse: Callable[[str], Any] | None,
    do_parse: bool,
    on_chunk: Callable[[str], None],
):
    """Stream the model, accumulate chunks/usage, then parse. Never raises on parse."""
    agg: Any = None
    raw_parts: list[str] = []
    interrupted = False
    start = time.monotonic()
    try:
        async for chunk in llm.astream([SystemMessage(content=system), HumanMessage(content=human)]):
            text = _coerce_content(getattr(chunk, "content", ""))
            raw_parts.append(text)
            on_chunk(text)
            agg = chunk if agg is None else agg + chunk
    except KeyboardInterrupt:
        interrupted = True
    latency = time.monotonic() - start
    raw = "".join(raw_parts)
    tin, tout = _usage(agg)
    parsed: Any | None = None
    parse_error: str | None = None
    if do_parse and parse is not None and not interrupted:
        try:
            parsed = parse(raw)
        except Exception as exc:  # parser failures are surfaced, never fatal
            parse_error = f"{type(exc).__name__}: {exc}"
    return raw, parsed, parse_error, tin, tout, latency, interrupted


async def run_single(
    adapter: Adapter,
    ctx: RunContext,
    item: str,
    *,
    do_parse: bool,
    on_chunk: Callable[[str], None],
) -> RunOutcome:
    cfg = load_role_config(adapter.role)
    model_id = cfg["model_id"]
    region = cfg.get("region", "us-east-1")
    prepared = await adapter.prepare(ctx, item)
    llm = make_llm(adapter.role)
    raw, parsed, perr, tin, tout, latency, interrupted = await stream_and_parse(
        llm,
        system=prepared.system,
        human=prepared.human,
        parse=prepared.parse,
        do_parse=do_parse,
        on_chunk=on_chunk,
    )
    return RunOutcome(
        item_id=prepared.item_id,
        role=adapter.role,
        model_id=model_id,
        region=region,
        system=prepared.system,
        human=prepared.human,
        raw=raw,
        parsed=parsed,
        parse_error=perr,
        tokens_in=tin,
        tokens_out=tout,
        latency_s=latency,
        cost_usd=_cost(model_id, tin, tout),
        interrupted=interrupted,
        note=prepared.note,
    )


async def run_all(adapter: Adapter, ctx: RunContext, *, trace_dir: Path):
    """Fan out over the adapter's real worklist via SubagentPool (worklist adapters only)."""
    cfg = load_role_config(adapter.role)
    items = adapter.items(ctx)  # raises ValueError for single-query adapters

    async def task(item: str) -> TaskResult:
        prepared = await adapter.prepare(ctx, item)
        llm = make_llm(adapter.role)
        resp = await llm.ainvoke([SystemMessage(content=prepared.system), HumanMessage(content=prepared.human)])
        return TaskResult(value=getattr(resp, "content", ""), response=resp)

    pool = SubagentPool(trace_dir=trace_dir)
    return await pool.run_all(
        items=items,
        task=task,
        role=adapter.role,
        model_id=cfg["model_id"],
        max_concurrency=int(cfg.get("max_concurrency", 3)),
    )


def _newest_trace(trace_dir: Path) -> str | None:
    if not trace_dir.exists():
        return None
    traces = sorted(trace_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return str(traces[-1]) if traces else None


async def run_loop(adapter: LoopAdapter, ctx: RunContext, item: str) -> LoopOutcome:
    """Run a tool-loop adapter; overlay model/region/latency/trace onto its outcome."""
    cfg = load_role_config(adapter.role)
    model_id = cfg["model_id"]
    region = cfg.get("region", "us-east-1")
    trace_dir = ws_paths.graph_dir(ctx.workspace) / "traces"
    start = time.monotonic()
    partial = await adapter.run(ctx, item)
    latency = time.monotonic() - start
    return dataclasses.replace(
        partial,
        model_id=model_id,
        region=region,
        latency_s=latency,
        trace_path=_newest_trace(trace_dir),
    )
