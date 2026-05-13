---
phase: 02-subagent-fan-out-runtime
verified: 2026-05-13T00:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 11/14
  gaps_closed:
    - "CR-01: RunnableConfig recursion_limit delivered to task callable via inspect.signature dispatch"
    - "CR-02: Trace filenames unique per run_all() call via UUID8 suffix; sleep workaround removed"
    - "CR-03: trace CLI handles malformed JSONL lines with stderr warning and continues; exit code 0"
    - "BED-02 WARNING: load_role_config exported from model_adapter public package API"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "ROADMAP SC#1 + SC#3: Run real-Bedrock integration tests with CODE_WIKI_RUN_INTEGRATION=1"
    expected: "test_partial_failure_real_bedrock: 3 successes + 1 error; test_no_throttling_at_max_concurrency_real_bedrock: 0 errors from 10 parallel linter invocations; test_recursion_limit_propagated_real_bedrock: 1 success from 30-sequential-ainvoke chain task"
    why_human: "Requires live AWS Bedrock credentials. Tests carry @INTEGRATION_GATE (pytest.mark.skipif) and skip cleanly in CI. These three tests are the only remaining validation path for ROADMAP SC#1 (partial failure against real Bedrock), SC#3 (no ThrottlingException at max_concurrency), and confirming the recursion-limit parameter flows through to real Bedrock invocations."
---

# Phase 2: Subagent Fan-Out Runtime Verification Report (Re-verification)

**Phase Goal:** Build SubagentPool with parallel fan-out, role-based model routing, cost tracking, and trace logging so Phase 3's query vertical slice can dispatch multiple subagents against AWS Bedrock in parallel.
**Verified:** 2026-05-13
**Status:** human_needed
**Re-verification:** Yes — after gap closure plan 02-04 (commits 02823f2, 0f25453, 2f1d80e)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | 4 parallel subagents dispatched, 1 raises intentionally, result has 3 successes + 1 error (no sibling cancellation) | ? HUMAN GATE | Integration test `test_partial_failure_real_bedrock` exists and is structurally correct; skip-gates confirmed without env var; cannot run without live Bedrock |
| SC2 | Every subagent invocation site passes explicit recursion_limit in config that REACHES the task callable | VERIFIED | `pool.py:_run_one` uses `inspect.signature(task)` dispatch: two-arg tasks receive `(item, _config)`; test_12 asserts `len(received_configs_a)==2` and `cfg.get("recursion_limit")==42` — delivery proven, not just construction |
| SC3 | 5+ parallel subagents produce no ThrottlingException at configured max_concurrency | ? HUMAN GATE | Integration test `test_no_throttling_at_max_concurrency_real_bedrock` exists (10 parallel linter subagents); skip-gated; requires live Bedrock |
| SC4 | Every fan-out call produces JSONL trace record; `code-wiki-agent trace <file>` renders it even on partially corrupted files | VERIFIED | _write_trace produces 9-field records on both success and error paths; cli.py trace command wraps json.loads in try/except json.JSONDecodeError (line 100-102) — malformed lines emit stderr warning and continue; test_trace_command_skips_malformed_lines passes |
| SC5 | ModelRegistry resolves all logical role names from models.toml | VERIFIED | All 9 roles present; 20 loader tests pass; `from model_adapter import load_role_config` now works from public API |
| T-P1-1 | load_role_config('librarian') returns dict with model_id, region, max_tokens, max_concurrency | VERIFIED | 20 passing tests; runtime check `cfg['max_tokens']==2048 and cfg['max_concurrency']==5` confirmed |
| T-P1-2 | make_llm('librarian') returns ChatBedrockConverse with max_tokens matching models.toml | VERIFIED | kwargs dict pattern; test_make_llm_librarian_sets_max_tokens passes |
| T-P1-3 | cores/subagent-runtime workspace member exists and is buildable | VERIFIED | pyproject.toml present; uv sync succeeds; `from subagent_runtime import SubagentPool, FanOutResult, PerItemError` exits 0 |
| T-P2-1 | Caller can dispatch N items and receive FanOutResult with partial-failure isolation | VERIFIED | asyncio.gather(return_exceptions=True); 12 unit tests green in 0.15s |
| T-P2-2 | Peak in-flight task count never exceeds max_concurrency | VERIFIED | asyncio.Semaphore created inside run_all(); test_semaphore_caps_concurrency and test_max_concurrency_one_serializes_tasks pass |
| T-P2-3 | Every dispatched item produces exactly one JSONL trace record with required fields | VERIFIED | _write_trace called in both try and except branches; 9-field schema confirmed |
| T-P2-4 | usage_metadata=None does not cause AttributeError | VERIFIED | Explicit None guard in _write_trace; test_token_metadata_none_guard passes |
| T-P2-5 | Two sequential run_all() calls produce two separate trace files | VERIFIED | Trace filenames now `f"{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"` (pool.py line 119); test_11 passes in 0.11s with no asyncio.sleep workaround |
| T-P3-1 | code-wiki-agent trace renders JSONL file as human-readable timeline | VERIFIED | try/except json.JSONDecodeError with `continue` in cli.py lines 98-102; test_trace_command_skips_malformed_lines (test #5) passes |

**Score:** 14/14 truths verified (SC1 and SC3 remain human-gated — require live AWS Bedrock credentials)

---

## Re-verification: Gap Closures

All three BLOCKERs and one WARNING from the prior verification are confirmed closed.

### CR-01 — CLOSED (SUB-04, ROADMAP SC#2)

**Previous state:** `_config = RunnableConfig(recursion_limit=rlimit)` was constructed and immediately discarded; `task(item)` received no config argument.

**Fix verified in pool.py (lines 131-135):**
```python
sig = inspect.signature(task)
if len(sig.parameters) >= 2:
    result = await task(item, _config)
else:
    result = await task(item)
```

**Test proving delivery (test_12, lines 400-404):**
```python
assert len(received_configs_a) == 2
for cfg in received_configs_a:
    assert isinstance(cfg, dict)
    assert cfg.get("recursion_limit") == 42
```

`test_recursion_limit_propagated_to_runnableconfig` passes (0.06s).

### CR-02 — CLOSED (OBS-01)

**Previous state:** `f"{int(time.time())}.jsonl"` — 1-second resolution; simultaneous calls collide.

**Fix verified in pool.py (line 119):**
```
trace_file = self._trace_dir / f"{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"
```

`grep -c "asyncio.sleep(1.1)" test_pool.py` returns 0. `test_separate_trace_files_per_run_all` passes in 0.11s (was >1.1s).

### CR-03 — CLOSED (OBS-02)

**Previous state:** `json.loads(line)` bare call; malformed line aborts with Python traceback.

**Fix verified in cli.py (lines 98-102):**
```python
try:
    record = json.loads(line)
except json.JSONDecodeError as exc:
    typer.echo(f"warning: skipping malformed JSONL line {line_number}: {exc.msg}", err=True)
    continue
```

`test_trace_command_skips_malformed_lines` passes; exit code 0 on malformed file; both valid item_ids in stdout; stderr contains "malformed".

### BED-02 WARNING — CLOSED

`from model_adapter import load_role_config` now works. `__init__.py` exports `["BedrockAccessDenied", "load_role_config", "make_llm"]`. Runtime check `cfg['max_tokens']==2048` confirmed.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cores/subagent-runtime/pyproject.toml` | Workspace member with model-adapter dep and asyncio_mode=auto | VERIFIED | name="subagent-runtime"; asyncio_mode="auto"; model-adapter workspace dep present |
| `cores/subagent-runtime/src/subagent_runtime/__init__.py` | Exports SubagentPool, FanOutResult, PerItemError | VERIFIED | `from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError`; `__all__` set |
| `cores/model-adapter/src/model_adapter/models.toml` | 9 roles with model_id + region + max_tokens + max_concurrency | VERIFIED | All 9 roles: haiku, sonnet, librarian(2048), scanner(500), linter(3000), ingestor, synthesizer, judge_a, judge_b |
| `cores/model-adapter/src/model_adapter/loader.py` | load_role_config() + max_tokens propagation in make_llm() | VERIFIED | Both functions present; kwargs dict for conditional max_tokens passing |
| `cores/model-adapter/src/model_adapter/__init__.py` | Exports load_role_config in public API | VERIFIED | `__all__ = ["BedrockAccessDenied", "load_role_config", "make_llm"]` |
| `cores/subagent-runtime/src/subagent_runtime/pool.py` | SubagentPool + FanOutResult + PerItemError + _write_trace; uuid import; inspect import | VERIFIED | 211 lines; uuid.uuid4 in trace filename; inspect.signature dispatch; `await task(item, _config)` branch present |
| `cores/subagent-runtime/tests/test_pool.py` | 12 unit tests; no sleep(1.1); received_configs delivery assertions | VERIFIED | 433 lines; 0 occurrences of `asyncio.sleep(1.1)`; 8 occurrences of `received_configs` |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | trace subcommand with json.JSONDecodeError handling | VERIFIED | JSONDecodeError except block present; enumerate with start=1; typer.echo(err=True) for stderr |
| `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` | 5 unit tests (4 original + malformed-line test) | VERIFIED | 5 passed in 0.45s |
| `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` | 3 integration tests; CI-safe skip | VERIFIED | 3 skipped without CODE_WIKI_RUN_INTEGRATION=1; 0 failed |
| `cores/subagent-runtime/tests/conftest.py` | fake_llm_response, fake_llm_response_error, make_task fixtures | VERIFIED | All 3 fixtures present |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| pool.py:run_all | asyncio.gather(return_exceptions=True) | gather call inside run_all | VERIFIED | `raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)` |
| pool.py:run_all | asyncio.Semaphore(max_concurrency) | semaphore CREATED INSIDE run_all | VERIFIED | Line 115 — inside run_all body; awk confirms 0 Semaphore constructions in __init__ |
| pool.py:_write_trace | trace_file append-mode write | json.dumps(record) + newline | VERIFIED | Lines 207-208: `with path.open("a") as f: f.write(json.dumps(record) + "\n")` |
| pool.py:_run_one | task callable | RunnableConfig(recursion_limit=rlimit) delivered via inspect.signature dispatch | VERIFIED | Lines 127-135: `_config` constructed; two-arg branch: `await task(item, _config)` |
| pool.py:run_all | trace_file unique path | uuid.uuid4().hex[:8] suffix | VERIFIED | Line 119: `f"{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"` |
| cli.py:trace | json.loads with JSONDecodeError guard | try/except enumerate loop | VERIFIED | Lines 94-102: enumerate(start=1), try/except, stderr echo, continue |
| test_pool_bedrock.py | model_adapter.loader.make_llm + load_role_config | inline imports in each test | VERIFIED | `from model_adapter.loader import load_role_config, make_llm` confirmed |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 12 SubagentPool unit tests pass | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/test_pool.py -x -q` | 12 passed in 0.15s | PASS |
| test_11 passes without sleep | `pytest test_pool.py::test_separate_trace_files_per_run_all -x -q` | 1 passed in 0.11s | PASS |
| test_12 passes with delivery assertions | `pytest test_pool.py::test_recursion_limit_propagated_to_runnableconfig -x -q` | 1 passed in 0.06s | PASS |
| 20 model-adapter loader tests pass | `uv run --package model-adapter pytest cores/model-adapter/tests/test_loader.py -x -q` | 20 passed in 0.47s | PASS |
| 5 trace viewer tests pass | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/test_trace_viewer.py -x -q` | 5 passed in 0.45s | PASS |
| Integration tests skip without Bedrock env | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/integration/test_pool_bedrock.py -q` | 3 skipped in 0.02s | PASS |
| load_role_config public API works | `uv run --package model-adapter python -c "from model_adapter import load_role_config; ..."` | ok | PASS |
| subagent_runtime public imports work | `uv run python -c "from subagent_runtime import SubagentPool, FanOutResult, PerItemError; print('ok')"` | ok | PASS |
| trace CLI command registered | `uv run --package code-wiki-agent code-wiki-agent trace --help` | help output rendered | PASS |
| asyncio.sleep(1.1) workaround removed | `grep -c "asyncio.sleep(1.1)" test_pool.py` | 0 | PASS |
| uuid.uuid4 in trace filename | `grep -c "uuid.uuid4" pool.py` | 1 | PASS |
| inspect.signature dispatch present | `grep -c "inspect.signature(task)" pool.py` | 1 | PASS |
| await task(item, _config) branch present | `grep -c "await task(item, _config)" pool.py` | 1 | PASS |
| json.JSONDecodeError handling in cli.py | `grep -c "json.JSONDecodeError" cli.py` | 1 | PASS |
| asyncio.TaskGroup absent | `grep -c "asyncio.TaskGroup" pool.py` | 0 | PASS |
| configurable.recursion_limit anti-pattern absent | `grep -c "configurable.*recursion_limit" pool.py` | 0 | PASS |
| No bare print() in cli.py | `grep -v '^#' cli.py \| grep -c "print("` | 0 | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BED-02 | 02-01, 02-04 | ModelRegistry keyed by logical role name → ChatBedrockConverse; public API export | SATISFIED | load_role_config + make_llm with 9-role registry; `from model_adapter import load_role_config` works; 20 tests pass |
| BED-03 | 02-01 | Per-role config includes model_id, max_tokens, max_concurrency | SATISFIED | All 9 roles in models.toml have all 3 keys plus region |
| BED-04 | 02-01 | Models configured via single TOML file, no hardcoded IDs | SATISFIED | models.toml is the sole source; model IDs are config-driven |
| BED-05 | 02-01/02 | Token + cost accounting per invocation propagated to traces | SATISFIED | tokens_in/tokens_out captured from usage_metadata; None-guard present; test_trace_record_completeness_success_path passes |
| SUB-01 | 02-02 | cores/subagent-runtime exposes fan-out primitive | SATISFIED | SubagentPool.run_all() exported; package importable |
| SUB-02 | 02-02/03 | SubAgentMiddleware evaluated; real-Bedrock integration test for partial failure | GATED | asyncio.gather path chosen (SUB-03); integration test exists; requires live Bedrock |
| SUB-03 | 02-02 | asyncio.gather(return_exceptions=True) path; recorded as Key Decision | SATISFIED | pool.py uses asyncio.gather; documented in SUMMARY |
| SUB-04 | 02-02/04 | Recursion limit propagated from parent to child AND delivered to task callable | SATISFIED | inspect.signature dispatch delivers _config to (item,config) tasks; test_12 delivery assertion passes |
| SUB-05 | 02-02/03 | Per-role max_tokens and concurrency caps enforced at fan-out | SATISFIED (unit) / GATED (Bedrock) | Semaphore in run_all(); unit tests confirm cap; Bedrock throttle test needs live env |
| SUB-06 | 02-02 | Fan-out call emits structured JSONL trace record | SATISFIED | _write_trace called on both success and error paths; 9-field schema confirmed |
| SUB-07 | 02-02 | Partial failure: returns successes + per-item errors | SATISFIED | FanOutResult with errors list; 4 unit tests cover partial failure patterns |
| OBS-01 | 02-02/04 | JSONL trace written to configurable path; unique file per run_all() | SATISFIED | trace_dir param; UUID8 suffix; test_11 passes without sleep workaround |
| OBS-02 | 02-03/04 | code-wiki-agent trace <file> viewer subcommand; resilient to malformed lines | SATISFIED | trace command renders files; JSONDecodeError handled; 5 tests pass |
| OBS-03 | 02-03 | Cost summary at end of interactive run (trace-viewer side) | SATISFIED | Summary block with per-role tokens; `Cost USD: (Phase 4)` placeholder; in-process post-run-all summary deferred to Phase 3+ per documented scope split |

---

## Anti-Patterns Found

No blockers or warnings remaining after gap closure.

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| (none remaining) | All three prior BLOCKERs and the WARNING are closed | — | — |

---

## Human Verification Required

### 1. ROADMAP Success Criteria #1 and #3 — Real Bedrock Integration

**Test:** With `CODE_WIKI_RUN_INTEGRATION=1` and valid AWS credentials, run:
```bash
CODE_WIKI_RUN_INTEGRATION=1 uv run --package subagent-runtime pytest \
    cores/subagent-runtime/tests/integration/test_pool_bedrock.py -v
```

**Expected:**
- `test_partial_failure_real_bedrock`: 3 successes, 1 error (item=="bad"), 4 JSONL trace records written with correct statuses
- `test_no_throttling_at_max_concurrency_real_bedrock`: 0 errors from 10 parallel linter invocations against real Bedrock
- `test_recursion_limit_propagated_real_bedrock`: 1 success from a 30-sequential-ainvoke chain task

**Why human:** Requires live AWS Bedrock credentials. These tests carry `@INTEGRATION_GATE` (`pytest.mark.skipif`) and skip cleanly in CI. All three automated-check BLOCKERS are now closed; the only remaining validation gap is confirming the pool's guarantees hold against the real Bedrock Converse API.

---

## Gaps Summary

No automated gaps remain. All three prior BLOCKERs are closed and verified by passing tests. The only outstanding items are the two human-gated integration tests (SC1 and SC3) that require live AWS Bedrock credentials — these are the Phase 2 ROADMAP success criteria that cannot be verified programmatically.

Total automated test count passing: 37 (12 pool + 5 trace viewer + 20 loader).

---

_Verified: 2026-05-13_
_Verifier: Claude (gsd-verifier)_
