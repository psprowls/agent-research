"""Trace I/O helper extracted from SubagentPool (Phase 16 D-04).

Houses the shared JSONL trace-record writer (`write_trace_record`) and the
per-model USD cost computation (`_compute_cost_usd`). Both moved verbatim from
`pool.py` so every production call site (pool.py, ingest.py, query.py) can
emit identically-shaped records without duplicating the construction logic.

Key invariants preserved from pool.py (TRACE-FU-01 / SC#1):
- schema_version: 1 on every record (Phase 9 OBS-04 D-01/D-02)
- usage_metadata is None-guarded — ChatBedrockConverse returns None on
  throttling / content-filter responses (deepagents #1698)
- OSError on write is caught + logged WARNING — never raises (Failure Mode #2)
- cost_usd computed from (model_id, tokens_in, tokens_out) via the
  in-package subagent_runtime.pricing module
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from subagent_runtime.pricing import cost_for_usage

logger = logging.getLogger(__name__)


def write_trace_record(
    path: Path,
    role: str,
    model_id: str,
    item: Any,
    status: str,
    latency_ms: int,
    response: Any,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Write one JSONL trace record. Never raises.

    Args:
        path: Per-run JSONL trace file (caller chooses the filename).
        role: Logical role name (e.g. "scanner", "ingestor", "synthesizer").
        model_id: Bedrock model ID resolved at call time.
        item: Per-item input — id-bearing object preferred, else str(item).
        status: "success" | "cancelled" | "error".
        latency_ms: Wall-clock latency for this invocation.
        response: ChatBedrockConverse response object, or None on error/cancel.
        error: Exception string when status == "error".

    Token fields come from ChatBedrockConverse usage_metadata dict:
    {"input_tokens": N, "output_tokens": N, "total_tokens": N}. usage_metadata
    is None on Bedrock error responses — guarded explicitly.
    """
    tokens_in: int | None = None
    tokens_out: int | None = None
    if response is not None and hasattr(response, "usage_metadata"):
        meta = response.usage_metadata  # None on ThrottlingException / content filter
        # Defensive isinstance(dict) check — guards against bare-MagicMock test
        # responses where usage_metadata auto-resolves to a MagicMock object that
        # is neither None nor dict-like. Real ChatBedrockConverse responses are
        # always dict or None.
        if isinstance(meta, dict):
            tokens_in = meta.get("input_tokens")
            tokens_out = meta.get("output_tokens")

    record: dict[str, Any] = {
        "schema_version": 1,  # Phase 9 OBS-04 D-01/D-02 — every record self-describing
        "role": role,
        "model_id": model_id,
        "prompt_hash": None,  # caller may set; None until computed upstream
        "item_id": getattr(item, "id", None) or str(item),
        "status": status,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": _compute_cost_usd(model_id, tokens_in, tokens_out),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if error:
        record["error"] = error

    try:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Trace write failed (data loss): %s", exc)

    return record


def render_trace_record(record: dict) -> str:
    """Return a single-line human-readable representation of a trace record.

    Single source of truth for the per-record line format, shared by the live
    fan-out log (subagent_runtime.pool) and the post-hoc `gw trace` viewer.

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

    line = f"[{timestamp}] {role} {model_short} {item_short} {status} {latency_ms}ms {tokens_in}->{tokens_out}"
    if record.get("status") == "error":
        line += f"  ERROR: {record.get('error', '')}"
    return line


def _compute_cost_usd(
    model_id: str,
    tokens_in: int | None,
    tokens_out: int | None,
) -> float | None:
    """Compute USD cost from token counts using subagent_runtime.pricing.

    Returns None if tokens are unavailable or the model is not in the pricing
    table (UnknownModelError).
    """
    if tokens_in is None or tokens_out is None:
        return None
    try:
        # UnknownModelError is a subclass of KeyError; catching KeyError covers it.
        return cost_for_usage(model_id, {"input": tokens_in, "output": tokens_out})
    except KeyError:
        return None
