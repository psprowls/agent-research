---
phase: 06-prompt-content-port-divergence-eval
plan: 10
subsystem: eval-harness/divergence
tags: [divergence-eval, baseline, regression-gate, accept-flag, EVAL-13]
requirements: [EVAL-13]

dependency_graph:
  requires: [06-09]
  provides: [baseline-persistence, regression-gate, initial-baselines]
  affects: [06-11]

tech_stack:
  added: []
  patterns:
    - "json.dumps(..., indent=2) + newline JSON write pattern"
    - "lazy import of ROLE_CHECKS to avoid circular import in check_regression"
    - "-JUDGE suffix detection for judge-severity override in regression gate"

key_files:
  modified:
    - cores/eval-harness/src/eval_harness/divergence/metric.py
    - cores/eval-harness/tests/test_divergence_baseline.py
  created:
    - cores/eval-harness/baselines/divergence-librarian.json
    - cores/eval-harness/baselines/divergence-ingestor.json
    - cores/eval-harness/baselines/divergence-linter.json
    - cores/eval-harness/baselines/divergence-scanner.json

decisions:
  - "load_baseline returns {} on missing file (RESEARCH Pitfall 5) rather than raising FileNotFoundError"
  - "check_regression uses lazy import of ROLE_CHECKS to avoid circular import at module load time"
  - "-JUDGE suffix detection is a hardcoded rule in check_regression — judge non-determinism (RESEARCH Pitfall 2) makes hard-gating judges inappropriate regardless of severity_lookup"
  - "Baselines generated via write_baseline programmatically to guarantee D-11 schema consistency"

metrics:
  duration: "~8 minutes"
  completed: "2026-05-15"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 6
---

# Phase 06 Plan 10: Baseline Persistence + Regression Gate Summary

Delivered EVAL-13: three module-level functions in `divergence/metric.py` (`load_baseline`, `write_baseline`, `check_regression`) plus initial all-zero baseline JSON files for all 4 roles and 9 unit tests covering the full flow without Bedrock.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add load_baseline / write_baseline / check_regression to metric.py | e363f70 | cores/eval-harness/src/eval_harness/divergence/metric.py |
| 2 | Initialize 4 baseline JSON files + populate test_divergence_baseline.py | fdeefb9 | baselines/divergence-{librarian,ingestor,linter,scanner}.json + test_divergence_baseline.py |

## Implementation Details

### Task 1: Three module-level functions in metric.py

`load_baseline(role, baselines_dir)` — reads `divergence-{role}.json` from baselines_dir, returns `{}` when missing (RESEARCH Pitfall 5 safety for first-run scenarios).

`write_baseline(role, baselines_dir, results, agent_commit)` — wraps `summarize()` to build the D-11 envelope, creates the directory with `mkdir(parents=True, exist_ok=True)`, writes with `json.dumps(envelope, indent=2) + "\n"` per the codebase JSON write pattern. Returns the written path.

`check_regression(role, current, baseline)` — builds a `severity_lookup` from `ROLE_CHECKS[role]` (lazy import to avoid circularity). For each rule_id in current: `-JUDGE` suffix → always soft; otherwise lookup severity with `"soft"` as defensive default. Hard-severity rules with `current_failures > baseline_failures` raise `AssertionError` with the role, rule_id, counts, and the `--accept-divergence-baseline` recovery hint. Soft rules are silent.

### Task 2: 4 baseline JSON files + test coverage

Baseline files generated programmatically via `write_baseline` with all-zero failure counts across all programmatic rule IDs plus the per-role `-JUDGE` aggregate entry. Files validated against D-11 schema.

`test_divergence_baseline.py` implements 9 tests:
- `test_load_baseline_returns_empty_when_missing` — {} on missing file
- `test_write_baseline_schema` — all 4 required D-11 keys present
- `test_write_baseline_json_format` — trailing newline + 2-space indent
- `test_check_regression_raises_on_hard_increase` — hard regression raises with accept-divergence-baseline message
- `test_check_regression_does_not_raise_for_soft` — LIB-004 (soft) regression is silent
- `test_check_regression_does_not_raise_for_judge` — LIB-JUDGE regression is silent
- `test_check_regression_passes_when_equal` — equal failures do not raise
- `test_check_regression_passes_when_decreased` — improved failures do not raise
- `test_accept_baseline_flag_rewrites_file` — second write_baseline call overwrites file content

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all functions are fully implemented with no placeholder behavior.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary-crossing surfaces introduced. Baseline files are committed to git (tamper detection via git diff, per T-06-21). The `check_regression` hard-gate test directly validates T-06-23.

## Self-Check: PASSED

All key files verified present. Both commits confirmed in git log.
