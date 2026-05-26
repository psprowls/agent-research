---
phase: 32-query-layer-extensions
plan: 02
subsystem: graph-io
tags: [describe-helpers, list-helpers, queries, projectors]

requires:
  - phase: 32-query-layer-extensions
    provides: dataclasses, _VALID_KINDS, find() allow-list, seeded_db/empty_db fixtures (plan 32-01)
provides:
  - 10 of 16 new query helpers (4 describe_* + 6 list_*)
  - 2 module-private projectors (_load_entry_point_description, _load_suite_description) — DRY for plans 02 and 03
  - In-place extensions to describe_package (domains/entry_points/test_suites) and describe_path (role_flags)
affects: [32-03]

tech-stack:
  added: []
  patterns:
    - "Projector helpers (`_load_<x>_description`) take raw SQL rows and emit typed Descriptions — keeps SQL projection logic in one place across describe_* and list_* helpers"
    - "list_* helpers delegate to `_list_by_kind(conn, kind)` for shared ORDER BY name pattern"

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/tests/test_queries.py

key-decisions:
  - "Projector reads `entry_kind` (the Phase 30 emitter's actual attrs_json key) with a fallback to `kind` for projector-level unit tests that build fake rows. PLAN had `attrs.get('kind')` which doesn't match real DB rows."
  - "list_scripts SQL queries `json_extract(attrs_json, '$.entry_kind') = 'executable'` (not `$.kind`) — same emitter-vs-plan reconciliation."

patterns-established:
  - "Per-kind list helpers route through a single `_list_by_kind` thin wrapper for consistency; `list_scripts` is the lone heterogeneous helper with explicit UNION."
  - "Each describe_* helper returns `<Type>Description | None`; tests pair every happy-path test with a `_returns_none_on_missing` or `_empty_db` variant."

requirements-completed: [QUERY-01, QUERY-02, QUERY-03, QUERY-04]

duration: 18min
completed: 2026-05-26
---

# Phase 32 Plan 02: Describe + List Helpers Summary

**Adds the 10 read helpers Wave 2's bubble-up queries depend on — 4 describe_*, 6 list_*, 2 internal projectors — plus extended describe_package (domains/entry_points/test_suites) and describe_path (role_flags).**

## Performance

- **Duration:** ~18 min
- **Tasks:** 5
- **Files modified:** 2

## Accomplishments
- 4 `describe_<kind>` helpers wired through the right joins (`domain_contains_domain`, `declares_entry_point` + `implemented_by`, `physically_contains` for suite file_count).
- 6 `list_<kind>` helpers; `list_scripts` is the union of executable Files and executable EntryPoints.
- `describe_package` now returns Domain memberships, declared EntryPoints, and covering TestSuites; `describe_path` returns the 7-key role_flags dict.
- 29 new tests via parametrization (10 kinds × find_per_kind, 5 list_*, plus describe_* happy/None pairs).

## Task Commits

1. **Tasks 1-4: Projectors + describe_* + list_* + extensions** — `82760de` (feat)
2. **Task 5: Wave 1 tests** — same commit (atomic)

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -x` → 48 passed.
- `uv run --package graph-io pytest packages/graph-io/tests/` → 280 passed (no regressions).
- `grep -nE "INSERT |UPDATE |DELETE FROM|CREATE |DROP " packages/graph-io/src/graph_io/queries.py` → no new mutations (D-16 read-only enforcement).
- `grep -nE "kind='[A-Z]" packages/graph-io/src/graph_io/queries.py` → 0 hits (lowercase kinds only).
- `grep -nE "parent_id|child_id" packages/graph-io/src/graph_io/queries.py` → 0 hits (src/dst columns only).

## Deviations from Plan

**[Rule 1 — bug] Plan reads `attrs.get('kind')` but emitter writes `entry_kind`** — Found during: Task 1 (projector implementation). | Issue: Phase 30's `entry_points.py` writes the EntryPoint kind as `entry_kind` (e.g. `"entry_kind": "executable"`) in `attrs_json`, not `kind`. PLAN had `attrs.get("kind", "")` and list_scripts SQL had `$.kind = 'executable'`. | Fix: projector reads `entry_kind` first, falls back to `kind` for projector-level unit tests; `list_scripts` SQL uses `$.entry_kind = 'executable'`; `test_list_scripts` asserts `r.attrs.get("entry_kind") == "executable"`. | Verification: `test_list_scripts` and `test_describe_entry_point` both pass against seeded_db. | Commit hash: 82760de

**Total deviations:** 1 auto-fixed (Rule 1 — emitter-vs-PLAN reconciliation). **Impact:** projector + list_scripts SQL + one test assertion changed to match emitter; semantic intent preserved.

## Self-Check: PASSED

- All 5 task acceptance criteria run green (greps + import checks + tests).
- 48/48 test_queries.py tests pass; 280/280 graph-io tests pass overall.
- Lowercase-kind / src-dst / read-only invariants verified.

Ready for Plan 32-03.
