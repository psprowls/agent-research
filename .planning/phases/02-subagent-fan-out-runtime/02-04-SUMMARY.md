---
phase: 02-subagent-fan-out-runtime
plan: "04"
subsystem: subagent-runtime, code-wiki-agent, model-adapter
tags: [gap-closure, recursion-limit, trace-uniqueness, cli-robustness, public-api]
dependency_graph:
  requires: ["02-01", "02-02", "02-03"]
  provides: ["SUB-04", "OBS-01", "OBS-02", "BED-02"]
  affects: ["03-query-vertical-slice"]
tech_stack:
  added: []
  patterns:
    - "inspect.signature dispatch for backward-compatible config injection"
    - "uuid.uuid4().hex[:8] suffix for per-second filename uniqueness"
    - "try/except json.JSONDecodeError with continue for resilient JSONL parsing"
key_files:
  modified:
    - cores/subagent-runtime/src/subagent_runtime/pool.py
    - cores/subagent-runtime/tests/test_pool.py
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py
    - agents/code-wiki-agent/tests/unit/test_trace_viewer.py
    - cores/model-adapter/src/model_adapter/__init__.py
decisions:
  - "inspect.signature two-arg dispatch chosen over always-passing config or Runnable.with_config() to preserve backward compat with all 12 unit tests and Plan 03 closures"
  - "uuid.uuid4().hex[:8] suffix (8 hex chars) chosen: ~4B combinations/second, sufficient for realistic fan-out; full UUID unnecessary"
  - "exc.msg used (not str(exc)) to avoid redundant line/col offset appended by JSONDecodeError str representation"
metrics:
  duration: "169s"
  completed_date: "2026-05-13"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 5
---

# Phase 02 Plan 04: Gap Closure (CR-01, CR-02, CR-03, BED-02) Summary

Closed all three BLOCKER gaps from 02-VERIFICATION.md and one WARNING. Surgical edits to 5 existing files; no new files created.

## What Was Built

**One-liner:** Closed Phase 2 blockers: RunnableConfig delivered via signature dispatch (SUB-04), UUID-suffixed trace filenames (OBS-01), malformed-JSONL resilience in trace CLI (OBS-02), and load_role_config public API export (BED-02).

## Gap Closures

### CR-01: RunnableConfig delivery to task callable (SUB-04 / ROADMAP SC#2)

- **File:line of fix:** `cores/subagent-runtime/src/subagent_runtime/pool.py` — `_run_one` dispatch site (after `_config = RunnableConfig(...)`)
- **Before:** `result = await task(item)` — `_config` was constructed but immediately discarded
- **After:** `sig = inspect.signature(task); result = await task(item, _config) if len(sig.parameters) >= 2 else await task(item)`
- **Test proving fix:** `test_recursion_limit_propagated_to_runnableconfig` — now uses explicit `(item, config)` task signature; asserts `len(received_configs_a) == 2` and each config has `recursion_limit == 42`
- **Dispatch strategy rationale:** Phase 3+ subagents wrapping LangGraph-compiled graphs should declare `(item, config)` to opt into config delivery. All existing single-arg test fixtures and Plan 03 closures remain unchanged. The `task.with_config(_config).ainvoke(item)` approach was rejected because task callables are plain async functions, not Runnables.

### CR-02: Unique trace filenames per run_all() call (OBS-01)

- **File:line of fix:** `cores/subagent-runtime/src/subagent_runtime/pool.py` line with `trace_file = ...`
- **Before:** `f"{int(time.time())}.jsonl"` — 1-second resolution, collides on back-to-back calls
- **After:** `f"{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"` — unix timestamp (sort order) + 8-hex UUID (uniqueness)
- **Test proving fix:** `test_separate_trace_files_per_run_all` — `asyncio.sleep(1.1)` workaround removed; two consecutive `run_all()` calls in same wall-clock second still produce 2 distinct files (0.05s total test time, down from >1.1s)

### CR-03: Malformed JSONL resilience in trace CLI (OBS-02)

- **File:line of fix:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — `trace` command for-loop
- **Before:** `record = json.loads(line)` — bare call; crashes with unhandled JSONDecodeError on malformed lines
- **After:** `try/except json.JSONDecodeError as exc: typer.echo(f"warning: skipping malformed JSONL line {line_number}: {exc.msg}", err=True); continue`
- **Test proving fix:** `test_trace_command_skips_malformed_lines` (new) — 3-line JSONL with malformed middle line; asserts exit 0, both valid item_ids in stdout, "malformed" or "line 2" in stderr

### BED-02 WARNING: load_role_config public API export

- **File:** `cores/model-adapter/src/model_adapter/__init__.py`
- **Before:** Only `make_llm` and `BedrockAccessDenied` exported; `load_role_config` required non-public `from model_adapter.loader import load_role_config`
- **After:** `from model_adapter.loader import load_role_config, make_llm`; `__all__ = ["BedrockAccessDenied", "load_role_config", "make_llm"]`
- **No callers needed to change:** `from model_adapter.loader import load_role_config` still works (unchanged); the new public path is additive

## Test Results

| Test Suite | Count | Status |
|------------|-------|--------|
| `cores/subagent-runtime/tests/test_pool.py` | 12 | PASS |
| `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` | 5 | PASS (4 original + 1 new) |
| `cores/model-adapter/tests/test_loader.py` | 20 | PASS |
| **Total** | **37** | **All green** |

## Re-verification Status

All three BLOCKER gaps from 02-VERIFICATION.md are now closed:

| Gap ID | Status Before | Status After | Verification Command |
|--------|---------------|--------------|----------------------|
| CR-01 (SUB-04) | FAILED — config constructed but dropped | CLOSED — inspect dispatch delivers to (item,config) tasks | `pytest test_pool.py::test_recursion_limit_propagated_to_runnableconfig` |
| CR-02 (OBS-01) | FAILED — sleep workaround, 1-second resolution | CLOSED — UUID suffix, no sleep needed | `pytest test_pool.py::test_separate_trace_files_per_run_all` |
| CR-03 (OBS-02) | FAILED — bare json.loads crashes on bad lines | CLOSED — try/except with warning + continue | `pytest test_trace_viewer.py::test_trace_command_skips_malformed_lines` |
| BED-02 (WARNING) | load_role_config not in __init__.py | CLOSED — exported from package root | `python -c "from model_adapter import load_role_config"` |

To re-verify Phase 2 completion: `/gsd-verify-work 02`

## Phase 2 Close-Out

The only remaining criterion before Phase 2 is fully complete is the **manual Bedrock integration test gate** from 02-03-PLAN: invoke `pool.run_all()` with a real Bedrock model and confirm traces are written and tokens counted. This is the human-gated criterion requiring AWS credentials.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_12 task signature adapted from *args to explicit (item, config)**

- **Found during:** Task 1 RED phase
- **Issue:** Plan specified `async def simple_task_x(*args)` for the config-delivery test tasks. `inspect.signature` returns 1 parameter for `*args` (the single VAR_POSITIONAL parameter), so the two-arg dispatch branch would never fire — the test would have passed vacuously with 0 configs delivered.
- **Fix:** Used explicit `async def simple_task_a(item, config)` signature, which correctly produces `len(sig.parameters) == 2` and opts into two-arg dispatch.
- **Files modified:** `cores/subagent-runtime/tests/test_pool.py`
- **Commit:** 02823f2

## Threat Flags

None. All fixes are surgical reactions to identified BLOCKERS. No new attack surface introduced. T-02-04-03 (malformed JSONL as DoS via CR-03) is mitigated by the new try/except block as planned.

## Self-Check: PASSED

Files exist:
- cores/subagent-runtime/src/subagent_runtime/pool.py — FOUND
- cores/subagent-runtime/tests/test_pool.py — FOUND
- agents/code-wiki-agent/src/code_wiki_agent/cli.py — FOUND
- agents/code-wiki-agent/tests/unit/test_trace_viewer.py — FOUND
- cores/model-adapter/src/model_adapter/__init__.py — FOUND

Commits exist:
- 02823f2 — fix(02-04): deliver RunnableConfig to task + unique trace filenames (CR-01, CR-02)
- 0f25453 — fix(02-04): handle malformed JSONL in trace viewer + unit test (CR-03)
- 2f1d80e — fix(02-04): export load_role_config from model_adapter public API (BED-02)
