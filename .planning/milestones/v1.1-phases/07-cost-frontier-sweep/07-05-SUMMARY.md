---
phase: 07-cost-frontier-sweep
plan: "05"
subsystem: testing
tags: [sweep-runner, single-role-swap, two-gate-scoring, eval-harness, bedrock, asyncio]

requires:
  - phase: 07-02
    provides: role_model_overrides added to run_query, model_override on run_scan/run_lint/run_ingest_source
  - phase: 07-03
    provides: Phase-6 divergence baselines and DivergenceMetric infrastructure
  - phase: 07-04
    provides: estimate_sweep_cost, preflight_check, EvalWorktree isolation

provides:
  - "ROLES_WITH_DIVERGENCE frozenset: {librarian, ingestor, linter, scanner}"
  - "TwoGateOutcome frozen dataclass capturing gate1_passed, gate2_passed, divergence_failures, panel_mean, threshold_used, notes"
  - "score_two_gate(role, metric, outputs, baselines_dir, panel_mean, default_panel_mean, threshold) -> TwoGateOutcome"
  - "ROLE_COMMAND_MAP: 6-role dispatch table mapping role names to private helper names"
  - "run_role_sweep(role, candidate_model_id, cases_path, vault_path, repeats, semaphore) -> list[SweepResult]"
  - "_sweep_query_role, _sweep_scan_role, _sweep_lint_role, _sweep_ingest_role helpers"

affects:
  - "07-06: report + pareto frontier rendering reads SweepResult produced by run_role_sweep"
  - "07-07: outer multi-cell driver calls run_role_sweep per cell, score_two_gate per role"

tech-stack:
  added: []
  patterns:
    - "Two-gate scoring: Gate 1 (divergence regression) + Gate 2 (quality threshold) per D-07; D-08 roles skip Gate 1"
    - "Frozen dataclass for immutable scoring outcomes (TwoGateOutcome)"
    - "ROLE_COMMAND_MAP dispatch: string keys map to _sweep_*_role helper function names; resolved at call time via _dispatch dict"
    - "Semaphore-gated asyncio.gather per run_role_sweep cell loop (Pitfall 4 throttle)"
    - "Single-role-swap via role_model_overrides={role: candidate} for query roles; model_override=candidate for command roles"

key-files:
  created:
    - cores/eval-harness/src/eval_harness/two_gate.py
  modified:
    - cores/eval-harness/src/eval_harness/sweep.py
    - cores/eval-harness/tests/test_two_gate_scorer.py
    - cores/eval-harness/tests/test_role_sweep.py

key-decisions:
  - "check_regression imported at module level in two_gate.py so tests can patch eval_harness.two_gate.check_regression cleanly"
  - "ROLE_COMMAND_MAP values are strings resolved via _dispatch dict — avoids forward-reference issues at module load time"
  - "_sweep_ingest_role falls back to vault_path when case lacks source_path key — documented in module docstring"
  - "Two-gate outcome notes capture human-readable gate decision for debugging and sweep reports"

patterns-established:
  - "score_two_gate: caller sets threshold (0.95 quality, 0.90 mid/cheap-fast) — not hardcoded in scorer"
  - "TwoGateOutcome.qualified = True only when all applicable gates are in {True, None}; both-None case is always False (no quality signal)"

requirements-completed: [SWEEP-01]

duration: 35min
completed: 2026-05-16
---

# Phase 7 Plan 05: Role-Rotation Sweep Runner + Two-Gate Scorer Summary

**asyncio.Semaphore-throttled run_role_sweep dispatches one (role, candidate) cell through ROLE_COMMAND_MAP with single-role-swap, and score_two_gate applies D-07/D-08 two-gate qualification against Phase-6 divergence baselines**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-16T22:35:00Z
- **Completed:** 2026-05-16T23:10:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `two_gate.py` delivers `score_two_gate` with correct D-07 (divergence + quality gates) and D-08 (quality only) branching; `TwoGateOutcome` frozen dataclass captures all gate signals
- `ROLE_COMMAND_MAP` + `run_role_sweep` in `sweep.py` implement the single-role-swap protocol (D-06): 6 roles routed to correct command functions with per-cell `EvalWorktree` isolation and `asyncio.Semaphore(8)` throttle
- 17 new unit tests green (6 scorer + 11 sweep), all mock-only (no live Bedrock), covering divergence fail, quality fail, D-08 synthesizer bypass, partial-failure isolation, repeats, model-id sanitization

## Task Commits

1. **Task 1: two_gate.py + test_two_gate_scorer.py** - `d577cf3` (feat)
2. **Task 2: run_role_sweep + dispatch map + test_role_sweep.py** - `2b2ff0c` (feat)

## Dispatch Table

| Role | dispatch | Gate 1 | Gate 2 |
|------|----------|--------|--------|
| librarian | `_sweep_query_role` | divergence (D-07) | quality |
| ingestor | `_sweep_ingest_role` | divergence (D-07) | quality |
| linter | `_sweep_lint_role` | divergence (D-07) | quality |
| scanner | `_sweep_scan_role` | divergence (D-07) | quality |
| synthesizer | `_sweep_query_role` | N/A (D-08) | quality |
| code_reader | `_sweep_query_role` | N/A (D-08) | quality |

## Two-Gate Fail Matrix

| gate1_passed | gate2_passed | qualified | notes |
|---|---|---|---|
| True | True | True | both gates PASS |
| True | None | True | Gate 2 N/A (panel_mean unavailable) |
| None | True | True | Gate 1 N/A (D-08 role) |
| None | None | False | no quality signal |
| False | * | False | Gate 1 (divergence) FAIL |
| True | False | False | Gate 2 (quality) FAIL |

## Unit Test Outcomes

| File | Tests | Result |
|------|-------|--------|
| test_two_gate_scorer.py | 6 | All PASS |
| test_role_sweep.py | 11 | All PASS |
| test_sweep.py (existing) | 7 | All PASS (preserved) |

## Files Created/Modified

- `/Users/pat/Personal/agent-research/packages/eval-harness/src/eval_harness/two_gate.py` — ROLES_WITH_DIVERGENCE, TwoGateOutcome, score_two_gate
- `/Users/pat/Personal/agent-research/packages/eval-harness/src/eval_harness/sweep.py` — ROLE_COMMAND_MAP, _sweep_*_role helpers, run_role_sweep, new imports
- `/Users/pat/Personal/agent-research/packages/eval-harness/tests/test_two_gate_scorer.py` — 6 tests replacing scaffold stubs
- `/Users/pat/Personal/agent-research/packages/eval-harness/tests/test_role_sweep.py` — 11 tests replacing scaffold stubs

## Decisions Made

- `check_regression` imported at module level in `two_gate.py` (not lazily inside `score_two_gate`) so test patches at `eval_harness.two_gate.check_regression` work cleanly.
- `ROLE_COMMAND_MAP` values are string names resolved via a `_dispatch` dict inside `run_role_sweep` — avoids circular imports and forward references at module load time.
- `_sweep_ingest_role` falls back to `vault_path` as the `source_path` when the eval case lacks a `source_path` key — documented in module docstring.
- Threshold is caller-supplied (not hardcoded in `score_two_gate`) so Plan 07-07 can set per-role thresholds (0.95 quality, 0.90 mid/cheap-fast).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level import needed for check_regression to be patchable**
- **Found during:** Task 1 (test_two_gate_scorer.py first run)
- **Issue:** `check_regression` was imported lazily inside `score_two_gate` — `patch("eval_harness.two_gate.check_regression", ...)` failed with AttributeError since the name wasn't in the module dict
- **Fix:** Moved `from eval_harness.divergence.metric import check_regression, load_baseline` to module-level imports in `two_gate.py`
- **Files modified:** `cores/eval-harness/src/eval_harness/two_gate.py`
- **Verification:** All 6 two_gate_scorer tests passed after fix
- **Committed in:** d577cf3 (Task 1 commit)

**2. [Rule 1 - Bug] LintResult/IngestResult summary strings used non-existent field names**
- **Found during:** Task 2 (authoring _sweep_lint_role and _sweep_ingest_role)
- **Issue:** Draft used `result.page_quality_issues` (not a LintResult field) and `result.pages_written` (not an IngestResult field)
- **Fix:** Changed to `result.orphans`/`result.errors` for lint and `result.page_path`/`result.status` for ingest
- **Files modified:** `cores/eval-harness/src/eval_harness/sweep.py`
- **Verification:** Import and test run confirmed correct fields
- **Committed in:** 2b2ff0c (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs)
**Impact on plan:** Both fixes were implementation-time corrections, not scope changes. No architectural impact.

## Issues Encountered

None - both deviations were caught and fixed before committing.

## Known Stubs

None — all code paths are fully wired. score_two_gate calls real DivergenceMetric/check_regression; run_role_sweep dispatches to real command functions.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes. T-07-09 (Semaphore throttle) and T-07-10 (_sanitize_model_id) mitigations are present as required.

## Next Phase Readiness

- `run_role_sweep` + `score_two_gate` are the structural core of the Phase 7 engine
- Plan 07-06 (report + pareto frontier) can import `SweepResult` from `sweep.py` unchanged
- Plan 07-07 (outer multi-cell driver) calls `run_role_sweep` per cell, then `score_two_gate` across aggregated results

## Self-Check: PASSED

- two_gate.py: FOUND
- test_two_gate_scorer.py: FOUND
- test_role_sweep.py: FOUND
- commit d577cf3: FOUND
- commit 2b2ff0c: FOUND

---
*Phase: 07-cost-frontier-sweep*
*Completed: 2026-05-16*
