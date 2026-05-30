---
phase: quick-260529-q8r
plan: 01
subsystem: eval-harness
one_liner: "Wire per-role DivergenceMetric + package baselines dir into run_full_matrix so Gate 1 stops auto-FAILing every sweep candidate"
tags: [eval-harness, sweep, two-gate, divergence]
requires:
  - "eval_harness.two_gate.score_two_gate (unchanged)"
  - "eval_harness.divergence.metric.DivergenceMetric (unchanged)"
provides:
  - "run_full_matrix passes a real DivergenceMetric + baselines_dir per divergence-eligible role"
affects:
  - "packages/eval-harness/src/eval_harness/sweep.py"
tech-stack:
  added: []
  patterns:
    - "Module-level _BASELINES_DIR constant derived from __file__ (mirrors test_two_gate_scorer.py)"
    - "Per-role Gate 1 wiring gated on membership in ROLES_WITH_DIVERGENCE"
key-files:
  created:
    - "packages/eval-harness/tests/test_sweep_full_matrix.py"
  modified:
    - "packages/eval-harness/src/eval_harness/sweep.py"
    - "packages/eval-harness/tests/eval/test_sweep_eval.py"
decisions:
  - "synthesizer + code_reader keep no recorded baseline JSON; load_baseline() returns {} (0-failure floor) — recording them is an explicit non-goal"
metrics:
  duration_min: 3
  completed: "2026-05-30"
requirements: [SWEEP-01]
---

# Phase quick-260529-q8r Plan 01: Fix C — Sweep Gate 1 Divergence Wiring Summary

Wired the per-role `DivergenceMetric` and the package `baselines/` directory into the
`score_two_gate(...)` call inside `run_full_matrix`, replacing the two hardcoded `None`
arguments that forced `gate1_passed=False` for every candidate (all 6 in-scope roles are
in `ROLES_WITH_DIVERGENCE`). The cost-frontier sweep's Gate 1 is now meaningful instead of
a guaranteed fail. `two_gate.py` / `metric.py` / the divergence package were left byte-for-byte
unchanged — the bug was purely in the caller.

## What Changed

### Task 1 — Wire divergence_metric + baselines_dir (commit e810d6a)
- Added module-level imports `from eval_harness.divergence import ROLE_CHECKS, ROLE_RUBRICS`
  and `from eval_harness.divergence.metric import DivergenceMetric` alongside the existing
  `eval_harness.*` imports.
- Added module-level constant `_BASELINES_DIR = Path(__file__).resolve().parents[2] / "baselines"`.
- In the second `for role, candidates` loop of `run_full_matrix`, after the `threshold` block:
  for a role in `ROLES_WITH_DIVERGENCE`, construct `DivergenceMetric(role=..., checks=ROLE_CHECKS[role],
  rubric_path=ROLE_RUBRICS[role], wiki=wiki_dir(workspace_path))` and set `baselines_dir_for_role =
  _BASELINES_DIR`; otherwise both stay `None` (preserves the D-08 contract).
- Replaced `divergence_metric_or_none=None` → `divergence_metric_or_none=divergence_metric` and
  `baselines_dir=None` → `baselines_dir=baselines_dir_for_role` in the `score_two_gate` call.
- Added an inline comment noting synthesizer + code_reader have no recorded baseline yet.

### Task 2 — Offline capture test + live-test assertion (commit 43c9dd6)
- Created `packages/eval-harness/tests/test_sweep_full_matrix.py` (no `@pytest.mark.eval`, no
  `GRAPH_WIKI_RUN_EVAL` guard). Drives `run_full_matrix(dry_run=True)` with a kwargs-capturing
  `score_two_gate` wrapper (returns a stub `TwoGateOutcome`, never runs real checks), then asserts
  the captured librarian call has `isinstance(divergence_metric_or_none, DivergenceMetric)` and an
  existing-dir `Path` baselines_dir.
- Extended `test_full_matrix_live`: imported `ROLES_WITH_DIVERGENCE` into the test's local
  `eval_harness.two_gate` import and added a per-call assertion that divergence-eligible roles get
  non-None `divergence_metric_or_none` and `baselines_dir`.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `uv run --package eval-harness pytest packages/eval-harness -q -k "not eval"` → 157 passed,
  4 skipped, 26 deselected (was 156 before; +1 new offline test).
- New offline test in isolation → 1 passed.
- `test_sweep_eval.py` collects cleanly (16 tests collected) — live assertion compiles.
- Protected-file guards: `two_gate.py`, `metric.py`, and the entire
  `packages/eval-harness/src/eval_harness/divergence/` directory show zero git diff.
- The two former hardcoded `None`s in the `score_two_gate` call are replaced by per-role variables.

## Known Stubs

None. (The offline test's stub `TwoGateOutcome` is intentional and local to the test — it avoids
running real divergence checks; production code wires real values.)

## Commits

- e810d6a — fix(quick-260529-q8r): wire per-role divergence metric + baselines_dir into run_full_matrix
- 43c9dd6 — test(quick-260529-q8r): lock Gate 1 divergence wiring with offline capture + live assertion

## Self-Check: PASSED

- FOUND: packages/eval-harness/tests/test_sweep_full_matrix.py
- FOUND: .planning/quick/260529-q8r-fix-c-sweep-gate-1-divergence-wiring/260529-q8r-SUMMARY.md
- FOUND commit: e810d6a
- FOUND commit: 43c9dd6
