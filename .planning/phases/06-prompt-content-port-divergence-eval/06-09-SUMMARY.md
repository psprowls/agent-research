---
phase: 06-prompt-content-port-divergence-eval
plan: 09
subsystem: eval-harness/divergence
tags: [divergence-eval, metric, geval-judge, accepted-failures, tdd]
requirements: [EVAL-11, EVAL-12]

dependency_graph:
  requires:
    - 06-08  # divergence rule infrastructure (ROLE_CHECKS, ROLE_RUBRICS, check.py)
    - eval_harness.judge  # JUDGE_PANEL_CONFIG, make_judge, panel_score
  provides:
    - eval_harness.divergence.metric.DivergenceMetric
    - eval_harness.divergence.metric.summarize
  affects:
    - 06-10  # baseline.py will call summarize() output to write baseline JSON
    - 06-11  # pytest-evals harness uses DivergenceMetric end-to-end

tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN cycle (test commit before implementation commit)
    - Lazy deepeval import inside run_judge (no AWS needed at module load)
    - Re-export pattern (JUDGE_PANEL_CONFIG, make_judge) for import verification in tests

key_files:
  created:
    - cores/eval-harness/src/eval_harness/divergence/metric.py
    - cores/eval-harness/tests/test_divergence_metric.py
  modified: []

decisions:
  - "Used plain class __init__ instead of @dataclass for DivergenceMetric (rubric_text read in __post_init__ has awkward field semantics in dataclasses; __init__ is cleaner and matches judge.py style)"
  - "JUDGE_PANEL_CONFIG and make_judge imported and re-exported at module level so import-identity test (metric_mod.JUDGE_PANEL_CONFIG is judge_mod.JUDGE_PANEL_CONFIG) passes"
  - "Explicit _ROLE_JUDGE_ID dict instead of string slicing to avoid ambiguity between role names of different lengths"
  - "noqa F401 on JUDGE_PANEL_CONFIG/make_judge import — re-exported intentionally for test import-identity verification"

metrics:
  duration_minutes: 15
  completed_date: "2026-05-15"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
---

# Phase 06 Plan 09: DivergenceMetric Class Summary

**One-liner:** `DivergenceMetric` wraps programmatic check pass + lazy GEval judge pass into a single per-role D-11-shaped results dict, with `summarize()` building the baseline JSON envelope.

## What Was Built

### `cores/eval-harness/src/eval_harness/divergence/metric.py`

Implements the `DivergenceMetric` class and `summarize` helper:

- **`DivergenceMetric.__init__`** — stores role, checks, rubric_path, vault; reads rubric text at construction time (fail-fast on missing rubric)
- **`run_programmatic(outputs: list[tuple[str, AgentOutputProxy]])`** — runs every `DivergenceCheck.check` callable against each fixture output; aggregates into D-11 shape `{rule_id: {runs, failures, accepted_failures}}`; excerpts capped at 200 chars (T-06-19)
- **`run_judge(outputs: list[tuple[str, AgentOutputProxy, str]])`** — lazy-imports `deepeval.metrics.GEval` and `deepeval.test_case`; creates fresh `AmazonBedrockModel` per panel member per fixture via `make_judge(cfg)`; passes `model=judge` explicitly on every `GEval(...)` call (T-06-18 invariant); aggregates per-fixture mean score; failures go to `accepted_failures` array
- **`run(outputs)`** — merges `run_programmatic` + `run_judge` results (D-07 hybrid detection); keys do not collide (programmatic: `LIB-001..LIB-004`; judge: `LIB-JUDGE`)
- **`summarize(role, results, agent_commit)`** — module-level helper producing the D-11 envelope `{role, recorded_at, agent_commit, checks}` for 06-10's baseline writer

### `cores/eval-harness/tests/test_divergence_metric.py`

12 unit tests (programmatic path only — judge path tested in 06-11 under eval gate):

- Construction + rubric-at-init (reads on `__init__`)
- `FileNotFoundError` on missing rubric
- Import without AWS credentials (lazy import gate)
- D-11 result shape for all 4 roles
- Run count correctness (3 fixtures x N checks = 3N runs)
- Failure recording with fixture ID and excerpt <= 200 chars
- Zero failures on well-formed librarian output
- `summarize()` envelope keys and ISO timestamp
- Static grep gate: `grep -c "model=judge"` >= 1 (T-06-18)
- Import identity: `metric_mod.JUDGE_PANEL_CONFIG is judge_mod.JUDGE_PANEL_CONFIG`

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED -- failing tests | `c0dc540` | PASSED (1 failure: ModuleNotFoundError as expected) |
| GREEN -- implementation | `1679a4c` | PASSED (12/12 tests pass) |
| REFACTOR | N/A -- no cleanup needed | N/A |

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `DivergenceMetric` class with `run_programmatic`, `run_judge`, `run`, `summarize` | PASS |
| `run_programmatic` returns D-11 shape | PASS |
| `accepted_failures` entries have `fixture: str` and `excerpt: str` | PASS |
| `grep -c "model=judge" metric.py` returns 2 (>= 1) | PASS |
| `JUDGE_PANEL_CONFIG` + `make_judge` reused from `eval_harness.judge` | PASS |
| Module importable without AWS credentials | PASS |
| `summarize` returns `{role, recorded_at, agent_commit, checks}` | PASS |
| Programmatic path smoke test against real fixture vault | PASS (`OK programmatic-only`) |

## Deviations from Plan

None -- plan executed exactly as written.

The plan's `<action>` suggested using `@dataclass` with a non-init `_rubric_text` field, but noted "use a regular class with `__init__` per PATTERNS.md". The implementation uses `__init__` throughout, which is the correct approach consistent with `judge.py` style (also a regular class).

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes beyond what the plan's threat model covers. `metric.py` touches the same Bedrock/deepeval surface as the existing `judge.py`.

## Self-Check: PASSED

- `cores/eval-harness/src/eval_harness/divergence/metric.py` -- FOUND
- `cores/eval-harness/tests/test_divergence_metric.py` -- FOUND
- Commit `c0dc540` (RED) -- FOUND
- Commit `1679a4c` (GREEN) -- FOUND
- All 12 new tests pass; 98 existing tests pass with 0 regressions
