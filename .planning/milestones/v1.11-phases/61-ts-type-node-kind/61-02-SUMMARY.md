---
phase: 61
plan: "02"
subsystem: graph-io
tags: [typescript, type-node-kind, cross-kind-resolution, deriver-version]
dependency_graph:
  requires: [61-01]
  provides: [cross-kind-resolution-type, DERIVER_VERSION-5, _VALID_KINDS-type]
  affects: [graph_io.resolve, graph_io.schema, graph_io.queries]
tech_stack:
  added: []
  patterns: [deriver-version-bump, kind-allowlist]
key_files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/resolve.py
    - packages/graph-io/src/graph_io/schema.py
    - packages/graph-io/src/graph_io/queries.py
decisions:
  - "_CROSS_KIND_RESOLVABLE and cross-kind SQL extended to include 'type' alongside function/method/class"
  - "DERIVER_VERSION bumped 4→5; SCHEMA_VERSION unchanged (kind is unconstrained TEXT)"
  - "'type' added to _VALID_KINDS; _VALID_APP_KINDS left untouched (unrelated)"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-30"
  tasks_completed: 3
  files_changed: 3
---

# Phase 61 Plan 02: graph-io cross-kind resolution for `type` + DERIVER bump Summary

**One-liner:** Added `type` to cross-kind resolution (Python set + SQL), bumped DERIVER_VERSION to 5, and added `type` to the `_VALID_KINDS` allowlist so `cg find --kind type` works.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add `type` to `_CROSS_KIND_RESOLVABLE` and the cross-kind SQL in resolve.py | c08c8b8 |
| 2 | Bump `DERIVER_VERSION` 4 → 5 in schema.py | 5524b6a |
| 3 | Add `type` to `_VALID_KINDS` in queries.py | 2f75fc3 |

## What Was Built

### Task 1: Cross-kind resolution for `type`
- `_CROSS_KIND_RESOLVABLE` expanded from `{"function", "method", "class"}` to `{"function", "method", "class", "type"}`
- The inline cross-kind sweep SQL `kind IN ('function', 'method', 'class')` updated to `kind IN ('function', 'method', 'class', 'type')`
- This enables a `type` placeholder export-edge destination (emitted by 61-01's `symbol_kind` fix) to resolve to a real `type` node when exactly one such node of that name exists graph-wide

### Task 2: DERIVER_VERSION bump
- `DERIVER_VERSION` changed from `4` to `5` in schema.py
- `SCHEMA_VERSION` left at `2` — `kind` is an unconstrained TEXT column with no CHECK constraint, so no schema migration is needed for the new `type` kind value
- The iqo mechanism (deriver_version mismatch forces `full=True` in `update.run()`) ensures existing graphs auto-rebuild on next `cg update`

### Task 3: `_VALID_KINDS` allowlist
- `"type"` added to the `_VALID_KINDS` frozenset in queries.py with a comment attributing it to Phase 61
- `_VALID_APP_KINDS` (the app-subtype allowlist at line 34) left unchanged — unrelated
- `cg find --kind type` and `find(kind="type")` no longer raise `ValueError("unknown kind 'type'; valid: ...")`

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

- **Before:** 508 passed, 3 skipped, 1 xfailed
- **After:** 508 passed, 3 skipped, 1 xfailed (no regressions)

## Known Stubs

None.

## Threat Flags

None. These are pure in-memory/SQLite changes with no network, auth, or new storage surface.

## Self-Check: PASSED

- [x] `packages/graph-io/src/graph_io/resolve.py` — `_CROSS_KIND_RESOLVABLE` contains `"type"`; SQL includes `'type'` in `kind IN (...)`
- [x] `packages/graph-io/src/graph_io/schema.py` — `DERIVER_VERSION == 5`, `SCHEMA_VERSION == 2`
- [x] `packages/graph-io/src/graph_io/queries.py` — `"type" in _VALID_KINDS`
- [x] All 3 task commits exist: c08c8b8, 5524b6a, 2f75fc3
- [x] `uv run pytest -q` → 508 passed, 3 skipped, 1 xfailed
