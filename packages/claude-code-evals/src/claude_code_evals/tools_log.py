"""Render a Transcript's tool calls as the tools.json artifact (truncated copy)."""

from __future__ import annotations

import json

from claude_code_evals.transcript import Transcript

TRUNCATE_CHARS = 500


def _truncate(s: str) -> str:
    if len(s) <= TRUNCATE_CHARS:
        return s
    return s[:TRUNCATE_CHARS] + f"…[truncated, {len(s)} chars total]"


def _serialize_value(value: object) -> object:
    if isinstance(value, str):
        return _truncate(value)
    rendered = json.dumps(value, default=str)
    if len(rendered) <= TRUNCATE_CHARS:
        return value
    return _truncate(rendered)


def render_tools_json(t: Transcript) -> dict:
    """Build the tools.json document. Truncation applies here only —
    assertions run against the in-memory Transcript with full values."""
    return {
        "total_calls": len(t.tool_calls),
        "warnings": list(t.warnings),
        "calls": [
            {
                "seq": c.seq,
                "tool": c.tool,
                "source": c.source,
                "parent_tool_use_id": c.parent_tool_use_id,
                "input": {k: _serialize_value(v) for k, v in c.input.items()},
            }
            for c in t.tool_calls
        ],
    }
