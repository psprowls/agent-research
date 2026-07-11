"""Trace-record aggregation for `gw util trace`.

Relocated from graph-wiki-cli's util_cli/main.py (the CLI presentation layer
kept the file-reading/warning logic; this is the reusable aggregation logic).
"""

from __future__ import annotations

from collections import defaultdict

from subagent_runtime.trace_io import render_trace_record

__all__ = ["aggregate_trace", "render_collapsed_group", "is_groupable", "render_trace_record"]


def aggregate_trace(records: list[dict]) -> dict:
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
        if not is_groupable(record):
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


def render_collapsed_group(records: list[dict]) -> str:
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
    breakdown_parts = [f"{counts[k]} {k}" for k in ("success", "error", "cancelled", "other") if counts[k]]
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
        f"[{ts_first} .. {ts_last}] {role} / {model_short} x{n}: {breakdown}, {sum_tin}->{sum_tout} tokens, {cost_str}"
    )


def is_groupable(record: dict) -> bool:
    """A record is groupable iff it has NO 'event' key and NO 'kind' key (D-11)."""
    return "event" not in record and "kind" not in record
