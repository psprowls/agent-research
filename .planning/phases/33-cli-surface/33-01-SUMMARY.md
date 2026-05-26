---
phase: 33-cli-surface
plan: 01
subsystem: cli
tags: [graph-io, cli, exit-codes, status, repository]

requires:
  - phase: 32-query-layer-extensions
    provides: queries.describe_repository(conn) -> RepoDescription | None
provides:
  - exit_codes.AMBIGUOUS = 7 (foundation for cg what-tests probe-both)
  - cg status human output now prepends "repository: <uri>" line (CLI-14)
  - cg status --fmt json now includes top-level "repository" field
  - test pinning all 8 exit-code constants
  - tests pinning repository-line in human + json status output
affects: [33-03, 33-05, anti-regression]

tech-stack:
  added: []
  patterns: [stable exit-code numbering, queries-as-cli-helper-source]

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/exit_codes.py
    - packages/graph-io/src/graph_io/cli/ops_status.py
    - packages/graph-io/tests/test_cli_exit_codes.py
    - packages/graph-io/tests/test_cli_status_staleness.py

key-decisions:
  - "AMBIGUOUS = 7 (NOT 2 as in CONTEXT.md D-20). Value 2 is already STALE and is actively consumed by cg status — assigning AMBIGUOUS=2 would collide. Next free integer (7) selected; documented in test_exit_codes_module_constants."
  - "describe_repository called from run(), not from _collect(), keeping _collect pure (D-15 implementation choice)."

patterns-established:
  - "Exit code numbering rule: when CONTEXT.md proposes a value that collides, document the deviation in the plan <objective> and pin the chosen value in a test."

requirements-completed:
  - CLI-14

duration: ~10min
completed: 2026-05-26
---

# Phase 33 Plan 01: Foundation Summary

**Adds exit_codes.AMBIGUOUS=7 and extends `cg status` with a `repository: <uri>` first line (CLI-14).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-26
- **Completed:** 2026-05-26
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- `exit_codes.AMBIGUOUS = 7` added — unblocks `cg what-tests` probe-both in 33-03.
- `cg status` (human) prepends `repository: <uri>` as line 1 (D-15 / CLI-14).
- `cg status --fmt json` adds top-level `"repository"` key.
- 3 new tests pin all behaviors.

## Task Commits

1. **Task 1: Add exit_codes.AMBIGUOUS = 7** — `1a0f7b2` (feat)
2. **Task 2: Extend ops_status.py with repository line** — `a43b4bd` (feat)
3. **Task 3: Pin AMBIGUOUS + status repository-line** — `ec56bd1` (test)

## Files Created/Modified

- `packages/graph-io/src/graph_io/exit_codes.py` — added `AMBIGUOUS = 7`.
- `packages/graph-io/src/graph_io/cli/ops_status.py` — import `queries`; call `describe_repository(conn)` and emit `repository:` first line / JSON field.
- `packages/graph-io/tests/test_cli_exit_codes.py` — new `test_exit_codes_module_constants`.
- `packages/graph-io/tests/test_cli_status_staleness.py` — new `test_status_repository_line_prepended_human` + `test_status_repository_field_in_json`.

## Decisions Made

- **AMBIGUOUS = 7 (not 2).** Documented in plan `<objective>` and pinned by `test_exit_codes_module_constants`. Avoids collision with `STALE=2`.
- **`describe_repository` called from `run()`, not `_collect()`.** Keeps `_collect` pure so existing unit tests on `_collect` need no fixture updates.

## Deviations from Plan

None — plan executed as written (the AMBIGUOUS=7 vs CONTEXT.md=2 is a deviation owned by the plan itself, not by execution).

## Issues Encountered

None.

## Next Phase Readiness

- 33-03 can rely on `exit_codes.AMBIGUOUS == 7`.
- 33-05 anti-regression test will exercise the new status behavior.

---
*Phase: 33-cli-surface*
*Completed: 2026-05-26*
