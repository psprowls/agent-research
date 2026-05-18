---
phase: 08-host-reliability
plan: "01"
subsystem: testing
tags: [asyncio, cancellation, pool, trace, subagent-runtime, pytest]

requires:
  - phase: 07-cost-frontier-sweep
    provides: model_adapter.loader.make_llm as the single LLM injection point
  - phase: 03-query-pipeline
    provides: SubagentPool.run_all fan-out primitive and _write_trace contract

provides:
  - SubagentPool._run_one CancelledError branch writing per-item status:cancelled trace records
  - SubagentPool.run_all outer gather wrapped in try/except CancelledError with _write_batch_terminal
  - SubagentPool._write_batch_terminal helper emitting event:batch_cancelled JSONL summary records
  - test_mcp_cancel.py covering MCP-10 and MCP-11 with zero Bedrock cost

affects:
  - 08-02-e2e-test (shares pool.py; cancel branch is live during E2E fan-out)
  - 08-03-cancellation-docs (documents the trace shapes emitted here)
  - phase-09-trace-renderer (Phase 9 will collapse cancelled records; shapes are now stable)

tech-stack:
  added: []
  patterns:
    - "CancelledError branch in _run_one must be placed BEFORE except Exception (BaseException inheritance)"
    - "_write_batch_terminal: never-raises OSError contract copied from _write_trace (AI-SPEC Failure Mode #2)"
    - "direct-asyncio cancel test with 50ms yield for deterministic in-flight gate"
    - "monkeypatch model_adapter.loader.make_llm (not factory.make_chat_model — D-09 stale path confirmed)"

key-files:
  created:
    - agents/code-wiki-agent/tests/integration/test_mcp_cancel.py
  modified:
    - cores/subagent-runtime/src/subagent_runtime/pool.py

key-decisions:
  - "Placed except asyncio.CancelledError BEFORE except Exception in _run_one to correctly intercept BaseException subclass"
  - "Used conservative items_cancelled=len(items) in batch terminal record since gather raw result is unavailable on outer cancel"
  - "Used 50ms yield (asyncio.sleep(0.05)) instead of single asyncio.sleep(0) — event loop needs multiple turns for coroutines to reach ainvoke await point"
  - "_write_batch_terminal reachable ONLY from run_all except asyncio.CancelledError branch (no other call sites)"

patterns-established:
  - "Direct-asyncio cancel test pattern: monkeypatch make_llm, seed vault, ensure_future + 50ms sleep + task.cancel()"
  - "Trace ordering invariant: _write_batch_terminal call in run_all catch block is always last write"

requirements-completed:
  - MCP-10
  - MCP-11

duration: 4min
completed: 2026-05-17
---

# Phase 8 Plan 01: Cancel Machinery Summary

**CancelledError branch in SubagentPool._run_one + _write_batch_terminal helper + direct-asyncio cancel test asserting per-item cancelled and batch_cancelled trace records with zero Bedrock cost**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-17T16:47:00Z (approx)
- **Completed:** 2026-05-17T16:50:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `_run_one` now catches `asyncio.CancelledError` before `except Exception`, writes per-item `status: cancelled` trace record via existing `_write_trace` (no change to `_write_trace` needed — its `None` guard already handles `response=None`), then re-raises.
- `run_all` wraps `asyncio.gather` in `try/except asyncio.CancelledError`, calls new `_write_batch_terminal`, re-raises so FastMCP anyio CancelScope sees the propagated error.
- `_write_batch_terminal` emits a single JSONL line with `event: batch_cancelled` fields per CONTEXT.md D-06 spec; uses the same never-raises OSError contract as `_write_trace`.
- `test_mcp_cancel.py` passes in <3s, runs without `CODE_WIKI_RUN_INTEGRATION=1`, and asserts all four trace invariants (per-item cancelled, single batch_cancelled, ordering, discriminator).

## pool.py diff summary

**Lines before (existing `_run_one` except block):** lines 141-146 — only `except Exception as exc` block.

**Lines after:** inserted `except asyncio.CancelledError` (4 lines) BEFORE `except Exception`, bringing the block to lines 141-152.

**gather wrap:** replaced single `raw = await asyncio.gather(...)` at line 149 (pre-edit) with `batch_t0 = time.monotonic(); try: raw = await asyncio.gather(...) except asyncio.CancelledError: ... raise` (13 lines).

**New method:** `_write_batch_terminal` added after `_write_trace` (33 lines including docstring).

**Total insertion:** +55 lines, -1 line (net +54).

## Task Commits

1. **Task 1: CancelledError branches and _write_batch_terminal** - `3a9e895` (feat)
2. **Task 2: cancel-mid-fan-out test** - `08e3d44` (feat)
3. **Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `cores/subagent-runtime/src/subagent_runtime/pool.py` - Added CancelledError branch in `_run_one`, wrapped `asyncio.gather` in `run_all`, added `_write_batch_terminal` helper
- `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py` - New: direct-asyncio cancel-mid-fan-out test (MCP-10, MCP-11)

## Decisions Made

**Cancel test timing:** Used `await asyncio.sleep(0.05)` (50ms) instead of `asyncio.sleep(0)`. A single 0-yield is insufficient because the event loop needs multiple turns for `run_query` to enter `pool.run_all`, for `asyncio.gather` to schedule `_run_one` coroutines, and for each coroutine to reach `await ainvoke()` where it suspends. At 50ms / 3s stub ratio (60:1), this is deterministic.

**Patch strategy for cancel test:** Patched `model_adapter.loader.make_llm`, `bm25_query`, `_cosine_search_sqlite`, and `BedrockEmbeddings` all within the test. The real `SubagentPool` runs (not mocked), so the actual cancel machinery is exercised end-to-end through the fan-out layer.

**Conservative items_cancelled count:** Used `items_cancelled=len(items)` (upper bound) in `_write_batch_terminal` since `asyncio.gather`'s raw result is unavailable when the outer task is cancelled. Phase 9 can derive accurate counts from per-item records.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Timing: single asyncio.sleep(0) insufficient for in-flight guarantee**
- **Found during:** Task 2 (cancel test)
- **Issue:** First test run showed only `batch_cancelled` record, no per-item `cancelled` records. The cancel arrived before `_run_one` coroutines had started.
- **Fix:** Changed `await asyncio.sleep(0)` to `await asyncio.sleep(0.05)` with documented rationale.
- **Files modified:** `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py`
- **Verification:** Test passes with ≥1 per-item cancelled records confirmed in trace.
- **Committed in:** `08e3d44` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - timing bug in test)
**Impact on plan:** Required fix for test correctness. No scope creep.

## Trace file path deviation

None — traces land exactly at `wiki / ".code-wiki" / "traces" / "*.jsonl"` as documented in `pool.py` and CONTEXT.md. The cancel test reads from `tmp_path.resolve() / ".code-wiki" / "traces"` which matches.

## _write_batch_terminal call site verification

`_write_batch_terminal` is called in exactly ONE place: the new `except asyncio.CancelledError` block in `run_all` (lines 158-169 of pool.py post-edit). No other call sites exist. Verified by grepping:

```
grep -rn "_write_batch_terminal" cores/subagent-runtime/src/
# Result: pool.py:159 (call) and pool.py:232 (definition)
```

## Issues Encountered

None beyond the timing fix documented above.

## Known Stubs

None — all trace record fields are real runtime values from the cancel path.

## Threat Flags

None — no new trust boundaries. The cancel path only writes to the existing trace file (append mode), using the same OSError-guarded never-raises contract as `_write_trace`.

## Next Phase Readiness

- Plan 02 (E2E test) can now rely on `pool.py`'s cancel handling being present and tested.
- Plan 03 (`docs/cancellation.md`) can document the exact trace shapes now stabilized here.
- The `event: batch_cancelled` discriminator and per-item `status: cancelled` shapes are stable; Phase 9 trace renderer can branch on them.

---
*Phase: 08-host-reliability*
*Completed: 2026-05-17*
