---
status: complete
phase: quick-260530-jap
plan: "01"
one_liner: "Post-pass sweep deletes skip-dir NULL-uri file nodes + orphaned edges; DERIVER_VERSION bumped to 2 for auto-rebuild"
subsystem: graph-io
tags: [graph-io, resolve, sweep, skip-dirs, deriver-version]
dependency_graph:
  requires: [260530-iqo]
  provides: [sweep_skip_dir_files]
  affects: [packages/graph-io/src/graph_io/resolve.py, packages/graph-io/src/graph_io/update.py, packages/graph-io/src/graph_io/schema.py]
tech_stack:
  added: []
  patterns: [plain-sqlite DELETE with Python-side path-component filter, TDD RED/GREEN]
key_files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/resolve.py
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/src/graph_io/schema.py
    - packages/graph-io/tests/test_resolve.py
decisions:
  - "Implemented sweep as post-pass on existing graph (not at _ensure_node time) — lowest-risk option, matches plan spec"
  - "Used Python-side filter (should_skip) rather than SQL path LIKE — reuses canonical _ignore.should_skip semantics"
  - "ON DELETE CASCADE not relied upon — explicit edge orphan cleanup added for portability"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-30"
  tasks_completed: 3
  files_changed: 4
---

# Phase quick-260530-jap Plan 01: Stop Materializing Dist/Build Import-Target File Nodes Summary

## What Was Built

Post-pass cleanup sweep `resolve.sweep_skip_dir_files(conn, skip_dirs)` that deletes `file` nodes whose path has a skip-dir component (`dist`, `build`, `node_modules`, etc.) AND whose `uri IS NULL` — i.e., import-edge targets that bypassed the walk's skip-dir filter. Orphaned edges (src or dst no longer in nodes) are removed in the same pass. `DERIVER_VERSION` bumped from 1 to 2 so existing graphs auto-rebuild on next `cg update` run.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing tests for sweep_skip_dir_files | 1cce928 | tests/test_resolve.py |
| 1 (GREEN) | Implement resolve.sweep_skip_dir_files | 5eee2f5 | src/graph_io/resolve.py |
| 2 | Wire sweep into update.run + bump DERIVER_VERSION | f6766f9 | update.py, schema.py |
| 3 | Full graph-io suite regression check | (no commit — no production changes) | — |

## TDD Gate Compliance

- RED gate: commit `1cce928` — 5 failing tests covering all specified cases (A–E)
- GREEN gate: commit `5eee2f5` — all 12 resolve tests pass
- REFACTOR: not needed (implementation was clean on first pass)

## Verification Results

- `test_resolve.py`: 12/12 passed (7 pre-existing + 5 new A–E tests)
- `test_update_full.py` + `test_update_incremental.py` + `test_schema.py`: 28/28 passed
- Full graph-io suite: 487 passed, 3 skipped, 1 xfailed — zero new failures

## Deviations from Plan

None — plan executed exactly as written. The plan's interface block correctly described the `update.py` pipeline tail and the `_ignore.should_skip` signature.

## Known Stubs

None.

## Threat Flags

No new network endpoints, auth paths, or trust-boundary changes introduced.

## Self-Check: PASSED

- `packages/graph-io/src/graph_io/resolve.py` contains `def sweep_skip_dir_files` — FOUND
- `packages/graph-io/src/graph_io/schema.py` has `DERIVER_VERSION = 2` — FOUND
- `packages/graph-io/src/graph_io/update.py` contains `resolve.sweep_skip_dir_files(conn, skip_dirs)` — FOUND
- `packages/graph-io/tests/test_resolve.py` contains `sweep_skip_dir_files` tests — FOUND
- Commit `1cce928` (RED), `5eee2f5` (GREEN), `f6766f9` (Task 2) — all exist on branch
