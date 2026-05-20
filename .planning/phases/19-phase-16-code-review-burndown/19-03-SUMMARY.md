---
phase: 19-phase-16-code-review-burndown
plan: 03
subsystem: test-quality
tags: [tests, dead-code, docstring, caplog, divergence-metric, trace-io]
requires:
  - 19-CONTEXT.md (D-04, D-09, D-10, D-13)
  - 16-REVIEW.md (WR-04, IN-03, IN-04, IN-07)
provides:
  - Loosened trace coverage assertion that exempts disclaimer/empty-fallback records
  - Strengthened OSError-swallow contract test (caplog WARNING assertion)
  - Dead Union import removed from divergence/metric.py
  - Module docstring in sweep_candidates test matches asserted 5–6 range
affects:
  - packages/eval-harness/src/eval_harness/divergence/metric.py
  - packages/subagent-runtime/tests/test_trace_io.py
  - packages/eval-harness/tests/test_models_toml_sweep_candidates.py
  - agents/graph-wiki-agent/tests/integration/test_trace_coverage.py
tech-stack:
  added: []
  patterns:
    - "caplog.at_level('WARNING', logger=...) + getMessage() substring assertion"
    - "Exemption-branch parallelism in integration assertions (mirror existing error-record branch)"
key-files:
  created:
    - .planning/phases/19-phase-16-code-review-burndown/19-03-SUMMARY.md
  modified:
    - agents/graph-wiki-agent/tests/integration/test_trace_coverage.py
    - packages/eval-harness/src/eval_harness/divergence/metric.py
    - packages/subagent-runtime/tests/test_trace_io.py
    - packages/eval-harness/tests/test_models_toml_sweep_candidates.py
decisions:
  - "Used local-variable extraction (`tokens_in = rec.get('tokens_in')`) so the grep-gate expression `tokens_in is None and tokens_out is None` appears verbatim in source"
  - "Logger fragment for caplog assertion: 'Trace write failed' (stable prefix of trace_io.py:88 warning)"
  - "D-13 phrasing keeps the historical 3-case reference so future readers can reconcile the Phase 16 D-07 expansion"
metrics:
  duration_seconds: 208
  tasks_completed: 4
  files_modified: 4
  completed: 2026-05-20
---

# Phase 19 Plan 03: Code-Review Burndown — Test + Dead-Import Fixes Summary

One-liner: Landed four CONTEXT.md decisions (D-04, D-09, D-10, D-13) — exempted the disclaimer/empty-fallback path in trace_coverage, removed a dead `Union` import in `divergence/metric.py`, added a `caplog` WARNING assertion to the OSError-swallow test, and corrected a stale module docstring — all test-adjacent surface, zero production logic changes.

## What Shipped

| Task | Decision | File | Commit |
|------|----------|------|--------|
| 1 | D-04 (WR-04) | `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py` | `09fa270` |
| 2 | D-09 (IN-03) | `packages/eval-harness/src/eval_harness/divergence/metric.py` | `85f3535` |
| 3 | D-10 (IN-04) | `packages/subagent-runtime/tests/test_trace_io.py` | `d0ae3c5` |
| 4 | D-13 (IN-07) | `packages/eval-harness/tests/test_models_toml_sweep_candidates.py` | `fbe6c1d` |

### Task 1 — D-04 (WR-04)
Added a third exemption branch in `test_trace_pipeline_records_token_usage`: when `tokens_in is None and tokens_out is None`, `continue`. Mirrors the existing error-record exemption and covers the short-circuit disclaimer/empty-fallback path where no model call was issued. Local-variable extraction was used so the grep-gate substring `tokens_in is None and tokens_out is None` appears verbatim.

### Task 2 — D-09 (IN-03)
Deleted `from typing import Union` (line 31) from `divergence/metric.py`. The module uses PEP-604 `A | B` syntax elsewhere. Post-edit `grep -c Union ...` returns 0.

### Task 3 — D-10 (IN-04)
Extended `test_write_trace_record_swallows_oserror` with the standard `caplog` pattern:

```python
with caplog.at_level("WARNING", logger="subagent_runtime.trace_io"):
    write_trace_record(...)
...
warnings = [r for r in caplog.records if r.levelname == "WARNING"]
assert any("Trace write failed" in r.getMessage() for r in warnings)
```

The fragment `Trace write failed` is the stable prefix of the `logger.warning("Trace write failed (data loss): %s", exc)` call at `trace_io.py:88`. No production code change.

### Task 4 — D-13 (IN-07)
Updated the module docstring at line 9 from `"code_reader_cases.json has 3 vault-thin fixture cases (D-09)"` to `"code_reader_cases.json has 5–6 vault-thin fixture cases (Phase 16 D-07 expansion from the original 3)"`, so the docstring now mirrors the asserted `5 <= len(cases) <= 6` range while preserving the historical reference.

## Deviations from Plan

None — plan executed exactly as written. Tasks 1-4 landed in the order specified; the per-commit gate passed after each; the plan-close gate (`uv run pytest packages/eval-harness/tests/ packages/subagent-runtime/tests/ agents/graph-wiki-agent/tests/ -m "not integration"`) reports `389 passed, 23 skipped, 9 deselected`.

The only minor judgment call was Task 1's local-variable extraction: the plan's done-grep is literal `tokens_in is None and tokens_out is None`, which `rec.get("tokens_in") is None and ...` would not satisfy. Extracting locals (`tokens_in = rec.get("tokens_in")`) satisfies both the grep-gate and the parallel-structure acceptance criterion. Not a deviation — both forms are equivalent and the plan permitted matching `the existing exemption's style`.

## Threat Flags

None. All edits are test surface or dead-import removal; no new attack surface, no schema/network/auth change.

## Self-Check: PASSED

- `.planning/phases/19-phase-16-code-review-burndown/19-03-SUMMARY.md` will be committed by the closing commit below.
- Commits exist (verified via `git rev-parse --short HEAD` on each task):
  - `09fa270` — Task 1
  - `85f3535` — Task 2
  - `d0ae3c5` — Task 3
  - `fbe6c1d` — Task 4
- Grep gates verified:
  - `grep -n "tokens_in is None and tokens_out is None" agents/graph-wiki-agent/tests/integration/test_trace_coverage.py` → hit at line 98
  - `grep -c Union packages/eval-harness/src/eval_harness/divergence/metric.py` → 0
  - `grep -n caplog packages/subagent-runtime/tests/test_trace_io.py` → caplog in param list + body
  - `grep -n "vault-thin" packages/eval-harness/tests/test_models_toml_sweep_candidates.py` → docstring updated (line 9)
- Per-commit verification gate (`uv run pytest ... -m "not integration"`) exits 0 — 389 passed.
