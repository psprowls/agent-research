"""Unit tests for graph_wiki_core.commands.trace.

test_aggregate_trace_by_role_model_groups_and_costs relocated from
graph-wiki-cli/tests/unit/test_trace_viewer.py — the only test in that file
that imported the aggregation logic directly rather than exercising it
through the `gw util trace` CLI (subprocess/CliRunner). The rest of that
file's ~25 tests stay in graph-wiki-cli as CLI-boundary black-box tests.
"""

from __future__ import annotations

from graph_wiki_core.commands.trace import aggregate_trace


def test_aggregate_trace_by_role_model_groups_and_costs() -> None:
    """aggregate_trace returns a by_role_model breakdown that:
    - groups records by (role, model_id)
    - sums tokens_in/tokens_out per group
    - sums cost_usd per group, tracking unknown_cost_count for null costs
    """
    records = [
        {"role": "scanner", "model_id": "model-a", "tokens_in": 100, "tokens_out": 50, "cost_usd": 0.01},
        {"role": "scanner", "model_id": "model-a", "tokens_in": 200, "tokens_out": 75, "cost_usd": 0.02},
        {"role": "scanner", "model_id": "model-b", "tokens_in": 10, "tokens_out": 5, "cost_usd": None},
        {"role": "librarian", "model_id": "model-a", "tokens_in": 1, "tokens_out": 1, "cost_usd": 0.001},
    ]
    agg = aggregate_trace(records)

    assert agg["total_records"] == 4
    assert agg["total_tokens_in"] == 311
    assert agg["total_tokens_out"] == 131

    by_role_model = agg["by_role_model"]
    scanner_a = by_role_model["scanner|model-a"]
    assert scanner_a["count"] == 2
    assert scanner_a["tokens_in"] == 300
    assert scanner_a["tokens_out"] == 125
    assert scanner_a["cost_usd_sum"] == 0.03
    assert scanner_a["unknown_cost_count"] == 0

    scanner_b = by_role_model["scanner|model-b"]
    assert scanner_b["count"] == 1
    assert scanner_b["unknown_cost_count"] == 1

    assert agg["by_role"]["scanner"]["count"] == 3
    assert agg["by_role"]["librarian"]["count"] == 1
