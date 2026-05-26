---
phase: 33-cli-surface
plan: 03
subsystem: cli
tags: [graph-io, cli, q-modules, test-suites, what-tests-dispatch]

requires:
  - phase: 32-query-layer-extensions
    provides: list_test_suites, describe_test_suite, tests_for_package, tests_for_domain
  - phase: 33-cli-surface
    provides: exit_codes.AMBIGUOUS = 7
provides:
  - q_list_suites CLI module (CLI-05)
  - q_describe_suite CLI module (CLI-06)
  - q_what_tests CLI module with probe-both dispatch (CLI-07, CLI-08)
affects: [33-05]

tech-stack:
  added: []
  patterns: [inline LIMIT-1 probe pattern; AMBIGUOUS=7 exit usage]

key-files:
  created:
    - packages/graph-io/src/graph_io/cli/q_list_suites.py
    - packages/graph-io/src/graph_io/cli/q_describe_suite.py
    - packages/graph-io/src/graph_io/cli/q_what_tests.py
  modified: []

key-decisions:
  - "q_describe_suite omits the 'framework' line because the Phase 32 SuiteDescription dataclass does not expose framework. Documented in the module docstring."
  - "q_what_tests uses 2 inline LIMIT-1 SELECTs for the probe (no helper) — keeps the decision tree local to the CLI module."
  - "Empty-result on --kind path is the list-* graceful-degradation case (D-03), not the describe-* not-found case (D-04). 'cg what-tests package nonexistent' returns exit 0 with the empty-state stderr; this matches list-* convention because the command semantically asks 'which tests cover X', not 'tell me about X'."

patterns-established:
  - "Probe-both pattern: inline LIMIT-1 queries when a CLI name could resolve to multiple node kinds."

requirements-completed:
  - CLI-05
  - CLI-06
  - CLI-07
  - CLI-08

duration: ~10min
completed: 2026-05-26
---

# Phase 33 Plan 03: Test-Suite Surface + What-Tests Dispatch Summary

**Adds 3 CLI modules — list-suites, describe-suite, and what-tests with probe-both dispatch using AMBIGUOUS=7.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2
- **Files created:** 3

## Accomplishments

- 4 of 14 CLI surface requirements delivered (CLI-05..08).
- q_what_tests probe-both decision tree handles all 4 cases (both/pkg/dom/neither) per D-01.
- AMBIGUOUS=7 from plan 33-01 used inside q_what_tests.

## Task Commits

1. **Task 1: q_list_suites + q_describe_suite** — `5ba1829` (feat)
2. **Task 2: q_what_tests probe-both dispatch** — `b279a11` (feat)

## Files Created/Modified

- `q_list_suites.py` — list_test_suites binding, one-per-line + asdict JSON.
- `q_describe_suite.py` — describe_test_suite binding; suite/uri/kind/files lines; framework omitted (dataclass lacks field).
- `q_what_tests.py` — tests_for_package / tests_for_domain dispatch with 2-query probe path.

## Decisions Made

- **`framework` line omitted from describe-suite.** Phase 32 SuiteDescription has no framework field; we did NOT add a new helper. Documented in the module docstring and recoverable when the helper grows the field.

## Deviations from Plan

None — plan executed as written.

## Issues Encountered

None.

## Next Phase Readiness

- 3 new q_* modules ready for wiring in 33-05.

---
*Phase: 33-cli-surface*
*Completed: 2026-05-26*
