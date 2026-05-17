---
phase: 07-cost-frontier-sweep
plan: "01"
subsystem: testing
tags: [eval-harness, pytest, test-scaffolding, wave-0, cost-frontier]

requires: []

provides:
  - Wave-0 test scaffolds for all 6 Phase-7 behaviors
  - Module-level-skipped unit test files pointing to their unlock plans
  - pytest.mark.eval integration scaffold for dry-run sweep

affects:
  - 07-04-PLAN (unlocks test_preflight_estimator.py)
  - 07-05-PLAN (unlocks test_role_sweep.py, test_two_gate_scorer.py)
  - 07-06-PLAN (unlocks test_report_role_doc.py, test_recommendation_block.py, test_sweep_dry_run.py)

tech-stack:
  added: []
  patterns:
    - "Module-level pytestmark skip guards test scaffolds until implementation lands"
    - "AsyncMock/patch style from test_sweep.py for sweep role tests"
    - "DivergenceMetric + AgentOutputProxy construction pattern from test_divergence_metric.py"
    - "pytest.mark.eval double-gate (--run-eval + CODE_WIKI_RUN_EVAL) for eval/ tests"

key-files:
  created:
    - cores/eval-harness/tests/test_role_sweep.py
    - cores/eval-harness/tests/test_two_gate_scorer.py
    - cores/eval-harness/tests/test_report_role_doc.py
    - cores/eval-harness/tests/test_preflight_estimator.py
    - cores/eval-harness/tests/test_recommendation_block.py
    - cores/eval-harness/tests/eval/test_sweep_dry_run.py
  modified: []

key-decisions:
  - "All scaffolds use module-level pytestmark skip (not per-test) to fail fast if a later plan flips a test without implementing the code"
  - "test_sweep_dry_run.py carries both pytest.mark.eval AND pytest.mark.skip so it is skipped in both normal pytest -m not eval runs and when --run-eval is passed before Plan 07-06 lands"
  - "test_preflight_estimator.py imports nothing from eval_harness.sweep at module level to avoid ImportError before estimate_sweep_cost exists"

patterns-established:
  - "Wave-0 scaffold pattern: create test file with module-level pytestmark skip + assert False / NotImplementedError body for each stub"
  - "Plan-ID pointer in skip reason: pytest.mark.skip(reason='Pending Plan 07-NN') makes CI failure messages self-documenting"

requirements-completed: [SWEEP-01, SWEEP-02, SWEEP-03, SWEEP-04]

duration: 8min
completed: 2026-05-16
---

# Phase 7 Plan 01: Cost-Frontier Sweep Wave-0 Test Scaffolds Summary

**Six module-level-skipped pytest scaffold files covering all Phase-7 behaviors — run_role_sweep dispatch, D-07 two-gate scoring, render_role_doc, pre-flight estimator, recommendation block, and dry-run integration — each pointing to the plan that will unlock it.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-16T00:00:00Z
- **Completed:** 2026-05-16
- **Tasks:** 2 of 2
- **Files created:** 6

## Accomplishments

- Created 5 unit-test scaffold files under `cores/eval-harness/tests/` covering SWEEP-01..04 and D-07/D-11/D-13 behaviors
- Created 1 integration-test scaffold under `cores/eval-harness/tests/eval/` with pytest.mark.eval double-gate
- All 19 scaffolded tests collect cleanly (145 total in suite); 20 skipped in `not eval` run; no pre-existing tests broken

## Task Commits

1. **Task 1: Scaffold 5 unit test files** - `9588827` (test)
2. **Task 2: Scaffold dry-run integration test** - `a22fb25` (test)

## Files Created/Modified

- `cores/eval-harness/tests/test_role_sweep.py` - run_role_sweep dispatch + single-role-swap scaffold (SWEEP-01)
- `cores/eval-harness/tests/test_two_gate_scorer.py` - D-07 two-gate scoring scaffold (Gate 1 + Gate 2 + synthesizer exception)
- `cores/eval-harness/tests/test_report_role_doc.py` - render_role_doc + pareto_frontier scaffold (SWEEP-03)
- `cores/eval-harness/tests/test_preflight_estimator.py` - estimate_sweep_cost pre-flight scaffold (D-13)
- `cores/eval-harness/tests/test_recommendation_block.py` - render_recommendation_block scaffold (SWEEP-04)
- `cores/eval-harness/tests/eval/test_sweep_dry_run.py` - dry-run end-to-end integration scaffold (SWEEP-03, Pending Plan 07-06)

## Plan-to-Test Mapping

| Plan | Unlocks |
|------|---------|
| 07-04 | test_preflight_estimator.py (3 tests) |
| 07-05 | test_role_sweep.py (4 tests), test_two_gate_scorer.py (4 tests) |
| 07-06 | test_report_role_doc.py (2 tests), test_recommendation_block.py (3 tests), test_sweep_dry_run.py (3 tests) |

## Collect-Only Counts

```
cores/eval-harness/tests/test_role_sweep.py          4 collected
cores/eval-harness/tests/test_two_gate_scorer.py     4 collected
cores/eval-harness/tests/test_report_role_doc.py     2 collected
cores/eval-harness/tests/test_preflight_estimator.py 3 collected
cores/eval-harness/tests/test_recommendation_block.py 3 collected
cores/eval-harness/tests/eval/test_sweep_dry_run.py  3 collected
Total new tests: 19 (all skipped)
Suite total: 145 collected
```

## Decisions Made

- Module-level pytestmark skip chosen over per-test skip to make the "not implemented" signal unambiguous — if someone runs these before the unlock plan, every test in the file is skipped with a clear pointer to the right plan
- `test_sweep_dry_run.py` carries both `pytest.mark.eval` and `pytest.mark.skip` so the file is inert in both the quick unit suite and under `--run-eval` until Plan 07-06 lands
- `test_preflight_estimator.py` intentionally imports nothing from `eval_harness.sweep` at module level; the production function `estimate_sweep_cost` does not exist yet, and an ImportError would break the entire test suite collection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The existing test suite has pre-existing `ValueError: Plugin already registered` errors in `cores/subagent-runtime/tests` and `cores/vault-io/tests` when pytest is invoked workspace-wide. These are unrelated to this plan and not caused by any new files. The eval-harness scoped suite (`uv run --package eval-harness pytest cores/eval-harness/tests/`) runs clean.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All files are pure test scaffolds with no executable logic.

## Next Phase Readiness

- Wave-0 scaffolds in place; Plans 07-04, 07-05, 07-06 have exact target test signatures to flip green
- No production code touched; no imports from not-yet-existing modules at module level
- Suite collects cleanly; downstream plans can run `--collect-only` to verify scaffold targets

---
*Phase: 07-cost-frontier-sweep*
*Completed: 2026-05-16*

## Self-Check: PASSED

Files verified:
- `cores/eval-harness/tests/test_role_sweep.py` - FOUND
- `cores/eval-harness/tests/test_two_gate_scorer.py` - FOUND
- `cores/eval-harness/tests/test_report_role_doc.py` - FOUND
- `cores/eval-harness/tests/test_preflight_estimator.py` - FOUND
- `cores/eval-harness/tests/test_recommendation_block.py` - FOUND
- `cores/eval-harness/tests/eval/test_sweep_dry_run.py` - FOUND

Commits verified:
- `9588827` - FOUND (test(07-01): scaffold 5 unit test files for wave-0 sweep behaviors)
- `a22fb25` - FOUND (test(07-01): scaffold dry-run integration test for sweep pipeline)
