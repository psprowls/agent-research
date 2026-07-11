"""Re-exports of subagent_runtime's fan-out primitives for delivery surfaces.

subagent-cli's runner.py (SubagentPool/TaskResult fan-out, pricing) and cli.py
(trace rendering for --all runs) previously imported subagent_runtime
directly — a layering violation. graph-wiki-core's commands/query.py,
ingest.py, and lint.py also import subagent_runtime.pool directly; they are
core-internal and already permitted to (this module does not change them —
see 02-plan-plan.md's "Out of scope" note for
2026-07-05-thin-the-delivery-surfaces-route-graph-wiki-cli-and-subagent-cli-through-graph-wiki-core).
"""

from __future__ import annotations

from subagent_runtime.pool import SubagentPool, TaskResult
from subagent_runtime.pricing import cost_for_usage
from subagent_runtime.trace_io import render_trace_record

__all__ = ["SubagentPool", "TaskResult", "cost_for_usage", "render_trace_record"]
