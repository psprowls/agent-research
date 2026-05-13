---
phase: 02-subagent-fan-out-runtime
plan: "02"
subsystem: subagent-runtime
tags: [asyncio, fan-out, subagent-pool, jsonl-trace, partial-failure, semaphore, tdd]
dependency_graph:
  requires:
    - 02-01 (subagent-runtime workspace member skeleton, conftest fixtures)
  provides:
    - SubagentPool.run_all() with asyncio.gather(return_exceptions=True) fan-out
    - FanOutResult dataclass with partial-failure isolation
    - PerItemError dataclass
    - JSONL trace writer (_write_trace) with 9-field schema
    - subagent_runtime package public API via __init__.py
  affects:
    - cores/subagent-runtime/src/subagent_runtime/pool.py
    - cores/subagent-runtime/src/subagent_runtime/__init__.py
    - cores/subagent-runtime/tests/test_pool.py
tech_stack:
  added: []
  patterns:
    - asyncio.gather(return_exceptions=True) for sibling-safe fan-out (deepagents #694 mitigation)
    - asyncio.Semaphore created INSIDE run_all() (never __init__) for correct event-loop binding
    - _write_trace catches OSError internally — never raises to caller
    - usage_metadata None guard before meta.get(input_tokens/output_tokens)
    - RunnableConfig(recursion_limit=N) injected at top-level (not under configurable)
key_files:
  created:
    - cores/subagent-runtime/src/subagent_runtime/pool.py
    - cores/subagent-runtime/tests/test_pool.py
  modified:
    - cores/subagent-runtime/src/subagent_runtime/__init__.py
decisions:
  - "SUB-03 path chosen: asyncio.gather pool over deepagents SubAgentMiddleware — #694 cancellation cascade fix merged but not released in 0.6.1; raw asyncio is correct and stable until a clean release ships"
  - "Semaphore created inside run_all() per AI-SPEC Pitfall 5 / RESEARCH Pitfall 1 — binding semaphore in __init__ causes RuntimeError in pytest-asyncio envs that spin their own loops"
  - "RunnableConfig(recursion_limit=N) at top-level key (not under configurable) per LangGraph docs and AI-SPEC Pitfall 4"
metrics:
  duration_mins: 3
  completed: "2026-05-13"
  tasks_completed: 2
  files_changed: 3
---

# Phase 02 Plan 02: SubagentPool Fan-Out Runtime Summary

asyncio.gather pool (SUB-03 path) with partial-failure isolation, per-role semaphore, JSONL trace writer, and usage_metadata None guard — 12 unit tests all green.

## What Was Built

### SubagentPool API

**`cores/subagent-runtime/src/subagent_runtime/pool.py`** (198 lines)

```python
@dataclass
class PerItemError:
    item: Any
    exception: Exception

@dataclass
class FanOutResult:
    successes: list[tuple[Any, Any]] = field(default_factory=list)
    errors: list[PerItemError] = field(default_factory=list)

class SubagentPool:
    def __init__(
        self,
        trace_dir: Path,
        *,
        default_recursion_limit: int = 100,
    ) -> None: ...

    async def run_all(
        self,
        items: list[Any],
        task: Callable[[Any], Awaitable[Any]],
        role: str,
        *,
        model_id: str,
        max_concurrency: int,
        recursion_limit: int | None = None,
    ) -> FanOutResult: ...

    def _write_trace(
        self,
        path: Path,
        role: str,
        model_id: str,
        item: Any,
        status: str,
        latency_ms: int,
        response: Any,
        *,
        error: str | None = None,
    ) -> None: ...
```

### JSONL Trace Schema

One record per dispatched item. Written on both success and error paths.

```json
{
  "role": "scanner",
  "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "prompt_hash": null,
  "item_id": "page-42",
  "status": "success",
  "latency_ms": 347,
  "tokens_in": 128,
  "tokens_out": 64,
  "cost_usd": null,
  "timestamp": "2026-05-13T20:31:00Z"
}
```

On error path: `status="error"`, `tokens_in=null`, `tokens_out=null`, `error="<str(exc)>"` key added.

Trace file path: `<trace_dir>/<unix_timestamp>.jsonl` — one file per `run_all()` call.

### Public API Export

**`cores/subagent-runtime/src/subagent_runtime/__init__.py`**

```python
from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError
__all__ = ["SubagentPool", "FanOutResult", "PerItemError"]
```

## Task Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 (RED) | 3ad14e5 | test(02-02): add 12 failing unit tests for SubagentPool |
| 2 (GREEN) | 07a67a4 | feat(02-02): implement SubagentPool with partial-failure isolation and JSONL trace |

## 12 Unit Tests — Coverage Map

| Test Name | Dimension / Critical Failure Mode |
|-----------|-----------------------------------|
| `test_fanout_returns_fanout_result_dataclass` | FanOutResult type contract; empty batch edge case |
| `test_partial_failure_isolation` | SUB-07, AI-SPEC CFM #1 — 1 of 4 fails; 3 successes, 1 error |
| `test_first_task_failure_does_not_cancel_siblings` | AI-SPEC CFM #1 (edge: failing item is first) — no sibling cancellation |
| `test_all_tasks_fail` | SUB-07 (edge: total failure) — 0 successes, N errors |
| `test_semaphore_caps_concurrency` | SUB-05 — peak in-flight never exceeds max_concurrency=2 |
| `test_max_concurrency_one_serializes_tasks` | SUB-05 (serial edge) — max_concurrency=1 yields peak==1 |
| `test_trace_record_completeness_success_path` | OBS-01, SUB-06, BED-05 — 9 required fields present; tokens_in/out from usage_metadata |
| `test_trace_record_error_path` | OBS-01, AI-SPEC CFM #2 — error record written with status=error and error field |
| `test_token_metadata_none_guard` | AI-SPEC CFM #5, BED-05 — usage_metadata=None does not raise AttributeError; fields are null |
| `test_write_trace_oserror_logged_not_raised` | AI-SPEC CFM #2 — OSError logged as WARNING; task success not masked as PerItemError |
| `test_separate_trace_files_per_run_all` | OBS-01, AI-SPEC "Observability lineage" — two run_all() calls → two distinct files |
| `test_recursion_limit_propagated_to_runnableconfig` | SUB-04, AI-SPEC CFM #4 — RunnableConfig(recursion_limit=N) called per item; default falls back to default_recursion_limit |

## Key Decision: SUB-03 — asyncio.gather Path Chosen

**Decision:** Build SubagentPool directly on `asyncio.gather(return_exceptions=True)` with a role-bound `asyncio.Semaphore` rather than deepagents `SubAgentMiddleware`.

**Rationale:**
- deepagents bug #694 (cancellation cascade on partial failure) was merged but NOT released in 0.6.1. The fix touches multiple SubAgentMiddleware internal points — subclassing is risky until a clean release ships.
- Raw asyncio is the same substrate that deepagents itself uses internally. Using it directly gives full control over the partial-failure contract with zero coupling to deepagents internals in flux.
- Upgrade path: once deepagents ships a release with #694 included, the asyncio pool can optionally be replaced with the vendor subclass — `run_all()` signature is unchanged.

**Outcome:** SUB-03 is the canonical path for Phase 2. Record in PROJECT.md Key Decisions table.

## Requirements Satisfied

| Requirement | Status | Verified By |
|-------------|--------|-------------|
| SUB-01 (SubagentPool primitive) | SATISFIED | test_fanout_returns_fanout_result_dataclass, test_partial_failure_isolation |
| SUB-02 (SubAgentMiddleware evaluated) | SATISFIED | Decision: SUB-03 chosen; documented in AI-SPEC Section 2 |
| SUB-03 (asyncio.gather path) | SATISFIED | run_all() implementation + 12 passing tests |
| SUB-04 (recursion_limit propagation) | SATISFIED | test_recursion_limit_propagated_to_runnableconfig |
| SUB-05 (semaphore throttle) | SATISFIED | test_semaphore_caps_concurrency, test_max_concurrency_one_serializes_tasks |
| SUB-06 (JSONL trace per call) | SATISFIED | test_trace_record_completeness_success_path, test_trace_record_error_path |
| SUB-07 (FanOutResult split) | SATISFIED | test_partial_failure_isolation, test_first_task_failure_does_not_cancel_siblings, test_all_tasks_fail |
| OBS-01 (trace under configurable dir) | SATISFIED | trace_dir param; test_separate_trace_files_per_run_all |
| BED-05 (tokens_in/tokens_out in trace) | SATISFIED | test_trace_record_completeness_success_path, test_token_metadata_none_guard |

## Deviations from Plan

None — plan executed exactly as written.

Both forbidden anti-patterns are absent:
- `asyncio.TaskGroup`: 0 occurrences in pool.py (`grep -c "asyncio.TaskGroup"` = 0)
- `configurable.*recursion_limit`: 0 occurrences in pool.py

## Known Stubs

None — all fields in the trace record are wired correctly. `prompt_hash` and `cost_usd` are `null` by design (Phase 4 adds cost accounting; prompt hash computation is the caller's responsibility).

## Threat Flags

No new threat surfaces beyond what the plan's threat model covers. All changes are internal to the subagent-runtime package — no new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

Files exist on disk:
- cores/subagent-runtime/src/subagent_runtime/pool.py: FOUND
- cores/subagent-runtime/src/subagent_runtime/__init__.py: FOUND
- cores/subagent-runtime/tests/test_pool.py: FOUND

Commits exist in git log:
- 3ad14e5: FOUND
- 07a67a4: FOUND

All 12 tests pass: uv run --package subagent-runtime pytest cores/subagent-runtime/tests/test_pool.py -x -q → 12 passed.
