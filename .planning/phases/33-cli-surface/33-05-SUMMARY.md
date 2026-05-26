---
phase: 33-cli-surface
plan: 05
subsystem: cli
tags: [graph-io, cli, registration, anti-regression]

requires:
  - phase: 33-cli-surface
    provides: 12 q_* CLI modules (plans 33-02, 33-03, 33-04)
provides:
  - cg --help lists all 25 subcommands (13 pre-existing + 12 new)
  - test_cli_anti_regression.py with 12 passing + 1 xfailed assertions covering pre-existing subcommands
affects: [34-brand-sweep]

tech-stack:
  added: []
  patterns: [module-scoped pytest fixture seeding a minimal repo for CLI smoke tests]

key-files:
  created:
    - packages/graph-io/tests/test_cli_anti_regression.py
  modified:
    - packages/graph-io/src/graph_io/cli/main.py

key-decisions:
  - "cg --help argument order: dict insertion order (D-19) — no special grouping in v1.6. New subcommands appear in CONTEXT.md D-18 order (repo → packages → entry-points → scripts → suites → tests dispatch → domains → cross-cutting)."
  - "sync-wiki anti-regression test is xfail-marked because it requires a configured wiki target (Phase 14)."
  - "Existing `cg find <name>` requires a positional name — the anti-regression test uses 'find main' against the seeded fixture rather than '--kind file' (which the current parser does not support)."

patterns-established:
  - "Module-scoped pytest fixture pattern for CLI smoke tests (one seed per test module)."

requirements-completed:
  - CLI-01
  - CLI-02
  - CLI-03
  - CLI-04
  - CLI-05
  - CLI-06
  - CLI-07
  - CLI-08
  - CLI-09
  - CLI-10
  - CLI-11
  - CLI-12
  - CLI-13

duration: ~10min
completed: 2026-05-26
---

# Phase 33 Plan 05: CLI Registration + Anti-Regression Summary

**Wires 12 new q_* modules into cg's _SUBCOMMANDS dict and pins 13 pre-existing subcommands with a smoke test.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2
- **Files modified:** 1
- **Files created:** 1

## Accomplishments

- `_SUBCOMMANDS` now has 25 entries (13 pre-existing + 12 new) — `cg --help` lists them all.
- `test_cli_anti_regression.py`: 12 passed + 1 xfailed (sync-wiki) — proves Phase 33's CLI expansion did not break argparse dispatch.
- Verified end-to-end smoke run: all 13 new subcommands produce sensible human + JSON output against a real DB.

## Task Commits

1. **Task 1: Register 12 new q_* modules in main.py** — `b904708` (feat)
2. **Task 2: Anti-regression smoke test** — `1ca3c43` (test)

## Files Created/Modified

- `packages/graph-io/src/graph_io/cli/main.py` — added 12 imports + 12 dict entries; `_build_parser`, `main()`, and top-level argparse args unchanged.
- `packages/graph-io/tests/test_cli_anti_regression.py` — new file with module-scoped fixture and two parametrized tests.

## Decisions Made

- **sync-wiki marked xfail** in the bonus assertions: it requires a configured wiki target (Phase 14). The xfail reason is logged so the failure is triageable rather than silent.
- **`cg find` test uses `find main`**, not the prototype's `find --kind file --name update.py`, because the current `q_find.py` parser requires a positional name and does not yet accept the kind-only variant.

## Deviations from Plan

- **Description string untouched.** Plan 33-05 says "do NOT touch the description string." The working tree already has `description="graph-wiki code graph CLI"` (uncommitted phase-34 work); this plan's edits did not introduce that change, only added imports + dict entries.

## Issues Encountered

None.

## Next Phase Readiness

- Phase 33 complete — `cg` has the full v1.6 graph surface.
- Phase 34 brand sweep can proceed safely; the anti-regression test will guard the rebrand from breaking argparse dispatch.

---
*Phase: 33-cli-surface*
*Completed: 2026-05-26*
