---
phase: 09-trace-observability-polish
plan: 01
subsystem: observability
tags: [trace, schema-version, jsonl, pool, query, obs-04]

# Dependency graph
requires:
  - phase: 02-subagent-fan-out-runtime
    provides: SubagentPool._write_trace inline JSONL writer
  - phase: 08-host-reliability
    provides: SubagentPool._write_batch_terminal (event-discriminator additive rule, D-06/D-07)
provides:
  - schema_version: 1 stamped on every JSONL record written by the three trace producers
  - unit-test coverage locking the field's presence on success, error, and batch-cancellation paths
  - unit-test coverage locking the field's presence on the per-query summary record
affects: [09-02, 09-03, 09-04, 09-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive trace evolution (Phase 8 D-06/D-07) extended to schema_version field"
    - "schema_version as first dict key per D-01 'self-describing line' rationale"

key-files:
  created:
    - agents/code-wiki-agent/tests/unit/test_query_summary_schema_version.py
  modified:
    - cores/subagent-runtime/src/subagent_runtime/pool.py (lines 211-222, 249-258)
    - cores/subagent-runtime/tests/test_pool.py (extended Tests 7/8; added Test 13)
    - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py (lines 981-992)

key-decisions:
  - "Task 2 test: created new file (test_query_summary_schema_version.py) — no existing test exercised the query_summary writer (grep on summary_record / query_summary / query_*.jsonl in tests/ returned no hits)"
  - "Auto-fixed pre-existing UnboundLocalError in _compute_cost_usd (Rule 1): UnknownModelError lazy import was referenced in except clause but unbound when import itself failed; replaced with (ImportError, KeyError) — UnknownModelError subclasses KeyError so coverage is equivalent and safe"

patterns-established:
  - "schema_version: 1 as the FIRST key of every trace record dict — preserves the 'JSONL line is self-describing' invariant when grep'd or stream-processed"

requirements-completed: [OBS-04]

# Metrics
duration: ~15 min
completed: 2026-05-17
---

# Phase 9 Plan 1: Trace schema_version stamping Summary

**Stamped `schema_version: 1` as the first key of every JSONL record written by all three trace producers (`SubagentPool._write_trace`, `SubagentPool._write_batch_terminal`, `query.py` `query_summary` writer) and locked the invariant with three focused unit tests.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-05-17T20:42:04Z
- **Tasks:** 2 (both atomic TDD: RED → GREEN per task)
- **Files modified:** 4 (3 production code + 1 test file modified, 1 test file created)

## Accomplishments
- All per-item subagent records (success / error / cancelled status) now stamp `schema_version: 1`
- All `event: batch_cancelled` terminal records stamp `schema_version: 1`
- All per-query `kind: query_summary` records stamp `schema_version: 1`
- Three test assertions lock the field's presence across success, error, and batch-cancellation paths in `test_pool.py`
- New focused test `test_query_summary_schema_version.py` drives `run_query` end-to-end with in-process stubs and asserts the field on the produced summary file
- All three writers preserve the "never raise" contract — `OSError` is still caught and logged at WARNING; no new `raise` introduced

## Task Commits

Each task was committed atomically:

1. **Task 1: Stamp schema_version in both pool.py writers + assert in unit tests** — `d1771ed` (feat) — adds the field in `_write_trace` and `_write_batch_terminal`; extends `test_trace_record_completeness_success_path` and `test_trace_record_error_path`; adds `test_batch_terminal_includes_schema_version`
2. **Task 2: Stamp schema_version in query.py query_summary writer + add focused test** — `e5f4ada` (feat) — adds the field in `summary_record`; creates `test_query_summary_schema_version.py`

## Files Created/Modified
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — `_write_trace` (line 211-222) and `_write_batch_terminal` (line 249-258) record dicts now begin with `"schema_version": 1`. Also: surgical fix to `_compute_cost_usd` removing the unbound `UnknownModelError` reference in the except clause (see Deviations).
- `cores/subagent-runtime/tests/test_pool.py` — Test 7 (`test_trace_record_completeness_success_path`) now includes `schema_version` in required_keys and asserts `== 1`; Test 8 (`test_trace_record_error_path`) gains the same assertion; new Test 13 (`test_batch_terminal_includes_schema_version`) reproduces the cancel-mid-fanout pattern from `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py` and asserts schema_version on both the terminal record and per-item cancelled records.
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — `summary_record` dict (line 981-992) now begins with `"schema_version": 1`.
- `agents/code-wiki-agent/tests/unit/test_query_summary_schema_version.py` (NEW) — single test that monkeypatches the same I/O boundaries used by `test_mcp_cancel.py` (`make_llm`, `resolve_wiki_and_repo`, `bm25_query`, `_cosine_search_sqlite`, `BedrockEmbeddings`) with fast stubs, drives `run_query` to completion, and asserts the written `query_{query_id}.jsonl` record carries `schema_version: 1` plus every pre-existing key.

## Decisions Made
- **Query-summary test location:** created a new file (`test_query_summary_schema_version.py`) rather than extending. Per the plan's decision rule, `read_first` checked the existing `tests/unit/test_query_*.py` files and grep on `summary_record` / `query_summary` / `query_*.jsonl` returned zero hits — no existing test exercises this writer.
- **Batch-terminal test pattern:** modeled after the proven cancellation timing in `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py` (3 s slow stub + 0.05 s yield). Held the test in `cores/subagent-runtime/tests/test_pool.py` (per-package locality) and used only stdlib + `unittest.mock` so it does not pull `code-wiki-agent` deps into `subagent-runtime`'s test closure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing UnboundLocalError in `_compute_cost_usd`**
- **Found during:** Task 1 RED — `test_trace_record_completeness_success_path` failed at `assert len(result.successes) == 1` because `_compute_cost_usd` was raising `UnboundLocalError: cannot access local variable 'UnknownModelError'` when called from the test environment, converting every "successful" task into a `PerItemError`.
- **Issue:** `_compute_cost_usd` lazy-imports `from eval_harness.pricing import UnknownModelError, cost_for_usage` inside the `try` block and catches `(ImportError, KeyError, UnknownModelError)`. When the import itself fails (which happens whenever `subagent-runtime`'s tests run in isolation without `eval-harness` installed in the closure), Python enters the `except` clause but `UnknownModelError` was never bound to a local — Python raises `UnboundLocalError` from the except-tuple evaluation, masking the original `ImportError`. Test confirmed pre-existing: same failure reproduces on `main` before this plan's changes (verified via `git stash`).
- **Fix:** Removed `UnknownModelError` from the lazy-import line and from the except-tuple. `UnknownModelError` subclasses `KeyError` (verified in `cores/eval-harness/src/eval_harness/pricing.py:10`), so catching `(ImportError, KeyError)` is equivalent coverage and avoids the unbound name. Added inline comment documenting the rationale and the Phase 9 OBS-04 surfacing context.
- **Files modified:** `cores/subagent-runtime/src/subagent_runtime/pool.py` (lines 277-285)
- **Verification:** All 13 tests in `cores/subagent-runtime/tests/test_pool.py` pass; all 142 tests in `agents/code-wiki-agent/tests/unit/` pass.
- **Committed in:** `d1771ed` (rolled into Task 1 commit; the fix was a required precondition to verifying Task 1).

---

**Total deviations:** 1 auto-fixed (Rule 1 — pre-existing bug surfaced by but not introduced by this plan)
**Impact on plan:** The fix was the minimum-surgical change required to unblock Task 1's verification (the plan's Task 1 `<verify>` block runs the same test that the bug had been failing). No scope creep — three lines changed in one helper function, with an explanatory comment.

## Issues Encountered
- Pre-existing failure in `test_trace_record_completeness_success_path` was blocking Task 1's TDD verification cycle. Resolved per Rule 1 above and documented as a deviation.

## User Setup Required
None — this is a purely additive, in-process change. No environment variables, dashboards, or external services.

## Next Phase Readiness
- Producer half of OBS-04 (`schema_version` stamping) is complete. The renderer half (lenient consumer for `schema_version > 1`, v0-inference warning for missing `schema_version`) is plan **09-05**'s scope per the phase context.
- The `additive-shape` rule is preserved: every existing reader continues to work because the new field is purely additive. Phase 8 fixtures (unversioned traces under `cores/vault-io/tests/fixtures/.../traces/`) are intentionally NOT rewritten per D-04 — they stay v0 and will exercise the renderer's v0-inference path when 09-05 lands.

## Self-Check

**Files created (verified):**
- `agents/code-wiki-agent/tests/unit/test_query_summary_schema_version.py` — FOUND

**Files modified (verified):**
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — modified (writers + helper fix)
- `cores/subagent-runtime/tests/test_pool.py` — modified (Test 7/8 extended; Test 13 added)
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — modified (summary_record writer)

**Commits (verified by hash in `git log --oneline`):**
- `d1771ed` — feat(09-01): stamp schema_version 1 on pool.py trace writers — FOUND
- `e5f4ada` — feat(09-01): stamp schema_version 1 on query.py query_summary writer — FOUND

## Self-Check: PASSED

---
*Phase: 09-trace-observability-polish*
*Completed: 2026-05-17*
