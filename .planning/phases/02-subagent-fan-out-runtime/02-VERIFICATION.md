---
phase: 02-subagent-fan-out-runtime
verified: 2026-05-13T00:00:00Z
status: gaps_found
score: 11/14 must-haves verified
overrides_applied: 0
gaps:
  - truth: "A subagent that requires 30 sequential tool calls completes without GraphRecursionError; every subagent invocation site passes an explicit recursion_limit in config"
    status: failed
    reason: "RunnableConfig(recursion_limit=rlimit) is constructed on pool.py line 122 and immediately discarded. The variable _config is never passed to task(item) on line 123. No LangChain or LangGraph component receives the recursion limit. The unit test (test_12) passes only because it monkeypatches the RunnableConfig constructor call itself — it verifies construction, not delivery. The integration test uses raw ainvoke (not a compiled graph), so GraphRecursionError cannot manifest. The ROADMAP SC#2 states 'every subagent invocation site passes an explicit recursion_limit in config' — that contract is not met."
    artifacts:
      - path: "cores/subagent-runtime/src/subagent_runtime/pool.py"
        issue: "_config = RunnableConfig(recursion_limit=rlimit) at line 122 is never passed to task(item) at line 123. The config object is discarded silently."
    missing:
      - "Pass _config to the task callable, either by changing the task signature to (item, config), using task.with_config(_config).ainvoke(item) if tasks are Runnables, or injecting via contextvars"
      - "Update the type annotation Callable[[Any], Awaitable[Any]] to reflect the config parameter if that approach is chosen"
      - "Update test_12 to also assert the config object reaches the task, not just that RunnableConfig was constructed"

  - truth: "Two sequential run_all() calls produce two separate trace files"
    status: failed
    reason: "The trace file path is f\"{int(time.time())}.jsonl\" (pool.py line 114). Two run_all() calls within the same wall-clock second produce the same filename. The second call opens the same path in append mode and merges records from both runs into one file. This violates the 1-file-per-run-all() assumption that trace lineage tracking depends on. Test 11 (test_separate_trace_files_per_run_all) works around this with asyncio.sleep(1.1) but the production bug remains."
    artifacts:
      - path: "cores/subagent-runtime/src/subagent_runtime/pool.py"
        issue: "Line 114: trace_file = self._trace_dir / f\"{int(time.time())}.jsonl\" — one-second resolution causes collision when two run_all() calls occur within the same second"
      - path: "cores/subagent-runtime/tests/test_pool.py"
        issue: "Line 349: await asyncio.sleep(1.1) — workaround that masks the production bug and slows unit tests by >1 second"
    missing:
      - "Add a uniqueness suffix to the trace file name: UUID (f\"{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl\") or a per-instance run counter"
      - "Remove the asyncio.sleep(1.1) from test_separate_trace_files_per_run_all once the filename is unique"

  - truth: "After running a fan-out workload, an operator can render a trace JSONL file as a human-readable timeline by running 'code-wiki-agent trace <file>' and seeing role, model_id, item_id, status, latency_ms, tokens_in, tokens_out per record"
    status: failed
    reason: "The trace CLI command has no error handling around json.loads(line) at cli.py line 98. A single malformed JSONL line (truncated write, binary content, BOM) produces an unhandled json.JSONDecodeError that exits with a Python stack trace instead of an actionable error message. This means the 'operator can render a trace file' guarantee breaks on any partially-written trace (a common failure mode when a run is interrupted). The unit tests do not cover this path."
    artifacts:
      - path: "agents/code-wiki-agent/src/code_wiki_agent/cli.py"
        issue: "Line 98: record = json.loads(line) — no try/except json.JSONDecodeError; malformed line aborts the entire render with a traceback"
    missing:
      - "Wrap json.loads in try/except json.JSONDecodeError; emit a warning to stderr (typer.echo(err=True)) and continue to the next line"
      - "Add a unit test for the malformed-JSONL path to test_trace_viewer.py"

human_verification:
  - test: "ROADMAP SC#1 + SC#3: Run real-Bedrock integration tests with CODE_WIKI_RUN_INTEGRATION=1"
    expected: "test_partial_failure_real_bedrock: 3 successes + 1 error; test_no_throttling_at_max_concurrency_real_bedrock: 0 errors; test_recursion_limit_propagated_real_bedrock: 1 success"
    why_human: "Requires live AWS Bedrock credentials; tests skip in CI; cannot verify programmatically. These are the Phase 2 ROADMAP success criteria that require real Bedrock invocations."
---

# Phase 2: Subagent Fan-Out Runtime Verification Report

**Phase Goal:** The shared SubagentPool in cores/subagent-runtime is correct, throttle-safe, and observable — with all deepagents bug mitigations in place — before any command uses fan-out. Structured trace output is designed here, not retrofitted.
**Verified:** 2026-05-13
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

Phase 2 has 5 ROADMAP success criteria. Requirements analysis also covers 14 plan must-have truths across 3 plans. Below is the consolidated truth table.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | 4 parallel subagents dispatched, 1 raises intentionally, result has 3 successes + 1 error (no sibling cancellation) | ? HUMAN GATE | Integration test exists and is structurally correct; cannot run without live Bedrock |
| SC2 | 30 sequential tool calls per subagent complete without GraphRecursionError; every invocation site passes explicit recursion_limit in config | FAILED | `_config = RunnableConfig(recursion_limit=rlimit)` at pool.py:122 is constructed but `task(item)` at line 123 receives no config argument — the config object is discarded silently |
| SC3 | 5+ parallel subagents produce no ThrottlingException with role-sized max_tokens | ? HUMAN GATE | Integration test exists; cannot run without live Bedrock |
| SC4 | Every fan-out call produces JSONL trace record with 9 required fields; `code-wiki-agent trace <file>` renders it | PARTIAL | 9-field schema in pool.py confirmed; trace CLI command exists and renders correctly for well-formed files — but json.loads at cli.py:98 has no error handler, so malformed lines abort the render with a Python traceback |
| SC5 | ModelRegistry resolves all logical role names from models.toml | VERIFIED | All 9 roles (haiku, sonnet, librarian, scanner, linter, ingestor, synthesizer, judge_a, judge_b) present in models.toml with model_id + region + max_tokens + max_concurrency |
| T-P1-1 | load_role_config('librarian') returns dict with model_id, region, max_tokens, max_concurrency | VERIFIED | models.toml has all 4 keys for all 9 roles; load_role_config tested with 20 passing tests |
| T-P1-2 | make_llm('librarian') returns ChatBedrockConverse with max_tokens matching models.toml | VERIFIED | loader.py passes max_tokens conditionally via kwargs dict; test_make_llm_librarian_sets_max_tokens passes |
| T-P1-3 | cores/subagent-runtime workspace member exists and is buildable | VERIFIED | pyproject.toml present; uv sync succeeds; import subagent_runtime exits 0 |
| T-P2-1 | Caller can dispatch N items and receive FanOutResult with partial-failure isolation | VERIFIED | asyncio.gather(return_exceptions=True) at pool.py:137; 12 unit tests green including partial-failure, first-item-fails, all-fail cases |
| T-P2-2 | Peak in-flight task count never exceeds max_concurrency | VERIFIED | asyncio.Semaphore created inside run_all() at pool.py:113; test_semaphore_caps_concurrency and test_max_concurrency_one_serializes_tasks pass |
| T-P2-3 | Every dispatched item produces exactly one JSONL trace record with required fields | VERIFIED | _write_trace called in both try and except branches of _run_one; 9-field schema confirmed; test_trace_record_completeness_success_path and test_trace_record_error_path pass |
| T-P2-4 | usage_metadata=None does not cause AttributeError | VERIFIED | Explicit None guard in _write_trace at pool.py:175; test_token_metadata_none_guard passes |
| T-P2-5 | Two sequential run_all() calls produce two separate trace files | FAILED | Trace file named f"{int(time.time())}.jsonl" (1-second resolution); simultaneous calls in same second collide; test workaround: asyncio.sleep(1.1) — not a production fix |
| T-P3-1 | code-wiki-agent trace renders JSONL file as human-readable timeline | PARTIAL | Renders correctly for well-formed files; no error handling for malformed JSONL lines (json.JSONDecodeError unhandled) |

**Score:** 11/14 must-haves verified (SC1 and SC3 deferred to human gate; SC2, T-P2-5, T-P3-1 partially or fully failed)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cores/subagent-runtime/pyproject.toml` | Workspace member with model-adapter dep and asyncio_mode=auto | VERIFIED | name="subagent-runtime", asyncio_mode="auto", model-adapter workspace dep present |
| `cores/subagent-runtime/src/subagent_runtime/__init__.py` | Exports SubagentPool, FanOutResult, PerItemError | VERIFIED | from subagent_runtime.pool import all three; __all__ set |
| `cores/model-adapter/src/model_adapter/models.toml` | 9 roles with model_id + region + max_tokens + max_concurrency | VERIFIED | All 9 roles confirmed: haiku, sonnet, librarian(2048), scanner(500), linter(3000), ingestor, synthesizer, judge_a, judge_b |
| `cores/model-adapter/src/model_adapter/loader.py` | load_role_config() + max_tokens propagation in make_llm() | VERIFIED | Both functions present; kwargs pattern for conditional max_tokens passing confirmed |
| `cores/subagent-runtime/src/subagent_runtime/pool.py` | SubagentPool + FanOutResult + PerItemError + _write_trace (min 80 lines) | VERIFIED (with gaps) | 198 lines; all three classes present; _write_trace present. Gap: RunnableConfig not passed to task. |
| `cores/subagent-runtime/tests/test_pool.py` | 12 unit tests (min 200 lines) | VERIFIED | 415 lines; 12 async test functions; all 12 pass |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | trace subcommand + _render_trace_record + _aggregate_trace | VERIFIED (with gaps) | All three present. Gap: json.loads unhandled in trace command |
| `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` | 4 unit tests (min 40 lines) | VERIFIED | 135 lines; 4 test functions; all 4 pass |
| `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` | 3 integration tests (min 80 lines), CI-safe skip | VERIFIED | 169 lines; 3 async tests; skip without CODE_WIKI_RUN_INTEGRATION=1 confirmed |
| `cores/subagent-runtime/tests/conftest.py` | fake_llm_response, fake_llm_response_error, make_task fixtures | VERIFIED | All 3 fixtures present at expected names |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| pool.py:run_all | asyncio.gather(return_exceptions=True) | gather call inside run_all | VERIFIED | pool.py line 137: `raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)` — 4 occurrences of return_exceptions=True confirmed |
| pool.py:run_all | asyncio.Semaphore(max_concurrency) | semaphore CREATED INSIDE run_all | VERIFIED | pool.py line 113: inside run_all body; awk check confirmed 0 Semaphore constructions in __init__ |
| pool.py:_write_trace | .code-wiki/traces/<timestamp>.jsonl | append-mode write via json.dumps(record) | VERIFIED | pool.py lines 195-196: `with path.open("a") as f: f.write(json.dumps(record) + "\n")` |
| pool.py:_run_one | RunnableConfig(recursion_limit=...) | config constructed in every task invocation | PARTIAL | RunnableConfig IS constructed (line 122) but NOT passed to task(item) at line 123 — construction verified, delivery broken |
| cli.py:trace | JSONL file via json.loads | reads file, parses, echoes via typer.echo | VERIFIED (partial) | json.loads wiring exists; output via typer.echo confirmed; gap: no error handler |
| test_pool_bedrock.py | model_adapter.loader.make_llm + load_role_config | inline imports in each test | VERIFIED | grep confirms `from model_adapter.loader import load_role_config, make_llm` in all 3 tests; make_llm used 6+ times |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| pool.py | 122-123 | `_config = RunnableConfig(...)` constructed, `task(item)` called with no config arg | BLOCKER | Recursion limit propagation is non-functional; ROADMAP SC#2 not met; tasks wrapping compiled LangGraph graphs will hit the default 25-step cap |
| pool.py | 114 | `f"{int(time.time())}.jsonl"` — 1-second trace file name resolution | BLOCKER | Two run_all() calls within the same second produce the same filename; records from separate logical runs are merged into one file silently |
| cli.py | 98 | `json.loads(line)` with no try/except | BLOCKER | Any malformed JSONL line aborts the trace viewer with an unhandled exception traceback |
| test_pool.py | 349 | `await asyncio.sleep(1.1)` in unit test | WARNING | Adds >1 second to every unit test run; a symptom of the trace filename collision bug |
| model_adapter/__init__.py | 13 | `load_role_config` not in public API | WARNING | `from model_adapter import load_role_config` raises ImportError; callers must use the non-public `model_adapter.loader` import path |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 12 SubagentPool unit tests pass | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/test_pool.py -x -q` | 12 passed in 1.24s | PASS |
| 20 model-adapter loader tests pass | `uv run --package model-adapter pytest cores/model-adapter/tests/test_loader.py -x -q` | 20 passed in 0.30s | PASS |
| 4 trace viewer unit tests pass | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/test_trace_viewer.py -x -q` | 4 passed in 0.25s | PASS |
| Integration tests skip without Bedrock env | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/integration/test_pool_bedrock.py -q` | 3 skipped | PASS |
| load_role_config('librarian') returns correct values | `uv run python -c "from model_adapter.loader import load_role_config; cfg = load_role_config('librarian'); assert cfg['max_tokens']==2048 and cfg['max_concurrency']==5; print('ok')"` | ok | PASS |
| trace CLI command registered | `uv run --package code-wiki-agent code-wiki-agent trace --help` | help output rendered | PASS |
| subagent_runtime public imports work | `uv run python -c "from subagent_runtime import SubagentPool, FanOutResult, PerItemError; print('ok')"` | ok | PASS |
| No bare print() in cli.py | `grep -c "print(" cli.py` | 0 | PASS |
| asyncio.TaskGroup absent (anti-pattern) | `grep -c "asyncio.TaskGroup" pool.py` | 0 | PASS |
| configurable.recursion_limit anti-pattern absent | `grep -c "configurable.*recursion_limit" pool.py` | 0 | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BED-02 | 02-01 | ModelRegistry keyed by logical role name → ChatBedrockConverse | SATISFIED | load_role_config() + make_llm() with 9-role registry; 20 tests pass |
| BED-03 | 02-01 | Per-role config includes model_id, max_tokens, max_concurrency | SATISFIED | All 9 roles in models.toml have all 3 keys plus region |
| BED-04 | 02-01 | Models configured via single TOML file, no hardcoded IDs | SATISFIED | models.toml is the only source; model IDs are config-driven |
| BED-05 | 02-01/02 | Token + cost accounting per invocation propagated to traces | SATISFIED | tokens_in/tokens_out captured from usage_metadata; None-guard present; test_trace_record_completeness_success_path passes |
| SUB-01 | 02-02 | cores/subagent-runtime exposes fan-out primitive | SATISFIED | SubagentPool.run_all() exported; package importable |
| SUB-02 | 02-02/03 | SubAgentMiddleware evaluated; real-Bedrock integration test for partial failure | GATED | asyncio.gather path chosen (SUB-03); integration test exists; requires live Bedrock to verify |
| SUB-03 | 02-02 | asyncio.gather(return_exceptions=True) path; recorded as Key Decision | SATISFIED | pool.py uses asyncio.gather; SUMMARY documents the decision |
| SUB-04 | 02-02/03 | Recursion limit propagated from parent to child | FAILED | RunnableConfig constructed but not delivered to task callable |
| SUB-05 | 02-02/03 | Per-role max_tokens and concurrency caps enforced at fan-out | SATISFIED (unit) / GATED (Bedrock) | Semaphore in run_all(); unit tests confirm cap; Bedrock throttle test needs live env |
| SUB-06 | 02-02 | Fan-out call emits structured JSONL trace record | SATISFIED | _write_trace called on both success and error paths; 9-field schema confirmed |
| SUB-07 | 02-02 | Partial failure: returns successes + per-item errors | SATISFIED | FanOutResult with errors list; 4 unit tests cover partial failure patterns |
| OBS-01 | 02-02 | JSONL trace written to configurable path | SATISFIED | trace_dir param in SubagentPool.__init__; test_separate_trace_files_per_run_all passes (with 1.1s workaround) |
| OBS-02 | 02-03 | code-wiki-agent trace <file> viewer subcommand | SATISFIED (with gap) | trace command renders well-formed files; unit tests pass; malformed-line error handling absent |
| OBS-03 | 02-03 | Cost summary at end of interactive run | PARTIALLY SATISFIED | Trace viewer Summary block present; in-process post-run-all cost summary deferred to Phase 3+ per documented scope split |

---

## Human Verification Required

### 1. ROADMAP Success Criteria #1, #3 — Real Bedrock Integration

**Test:** With `CODE_WIKI_RUN_INTEGRATION=1` and valid AWS credentials, run:
```bash
CODE_WIKI_RUN_INTEGRATION=1 uv run --package subagent-runtime pytest \
    cores/subagent-runtime/tests/integration/test_pool_bedrock.py -v
```

**Expected:**
- `test_partial_failure_real_bedrock`: 3 successes, 1 error (item=="bad"), 4 JSONL records
- `test_no_throttling_at_max_concurrency_real_bedrock`: 0 errors from 10 parallel linter invocations
- `test_recursion_limit_propagated_real_bedrock`: Note this test passes even with the CR-01 bug because it uses raw ainvoke, not a compiled graph. It does NOT prove SC#2 is met.

**Why human:** Requires live AWS Bedrock credentials; cannot verify programmatically.

---

## Gaps Summary

Three gaps block full phase goal achievement:

**Gap 1 (CR-01 — BLOCKER): RunnableConfig recursion limit is assembled but silently dropped.**
The `_config` local variable is constructed and immediately abandoned. The task callable receives only `item`. This directly violates ROADMAP SC#2 ("every subagent invocation site passes an explicit recursion_limit in config"). The unit test for this (test_12) passes because it monkeypatches the RunnableConfig constructor — it verifies that RunnableConfig was called with the right argument, not that the argument reached the task. When Phase 3 tasks wrap compiled LangGraph graphs, they will hit the default 25-step recursion cap silently.

**Gap 2 (CR-02 — BLOCKER): Trace file names collide for same-second run_all() calls.**
The 1-second resolution means any two `run_all()` calls within the same wall-clock second write to the same file, merging logically separate runs. The test for separate files works only because of a 1.1-second `asyncio.sleep()` workaround that should not exist in a unit test suite. Production workflows (e.g., Phase 3 query command calling run_all() multiple times) will silently merge trace records.

**Gap 3 (CR-03 — BLOCKER): json.loads in the trace CLI has no error handler.**
A malformed JSONL line (truncated write, binary noise, BOM) crashes the trace viewer with a Python traceback. The ROADMAP SC#4 promises that operators can render trace files; this promise breaks on any non-perfectly-formed file.

All three gaps were identified in the 02-REVIEW.md code review (ea85bb7) but no fix was applied before verification. The code review findings are confirmed by direct code inspection.

---

_Verified: 2026-05-13_
_Verifier: Claude (gsd-verifier)_
