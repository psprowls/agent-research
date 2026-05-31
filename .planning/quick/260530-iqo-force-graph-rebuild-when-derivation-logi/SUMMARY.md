---
status: complete
phase: quick-260530-iqo
plan: "01"
subsystem: graph-io
tags: [graph-io, update, schema, incremental, versioning]
dependency_graph:
  requires: []
  provides: [DERIVER_VERSION constant, deriver-version mismatch rebuild, deriver_version metadata]
  affects: [packages/graph-io/src/graph_io/schema.py, packages/graph-io/src/graph_io/update.py, packages/graph-io/tests/test_update_full.py]
tech_stack:
  added: []
  patterns: [metadata-versioned-rebuild, sqlite-metadata-stamp]
key_files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/schema.py
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/tests/test_update_full.py
decisions:
  - "Use DELETE rather than UPDATE-to-sentinel for the test probe — upsert keys on (kind,name,path), so renamed nodes accumulate rather than replace; deletion proves re-derivation cleanly"
  - "Mismatch guard fires only when prev is not None — fresh DBs already do a full build; no spurious stderr on first run"
  - "Write deriver_version metadata on every successful run (full and incremental) — stamps old graphs on their first post-upgrade run at no extra cost"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-30T19:37:21Z"
  tasks_completed: 2
  files_modified: 3
---

# Phase quick-260530-iqo Plan 01: Force Graph Rebuild When Derivation Logic Changes Summary

**One-liner:** DERIVER_VERSION stamp in schema + mismatch check in update.run() auto-forces full rebuild when derivation logic changes, bypassing the HEAD-unchanged short-circuit.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add DERIVER_VERSION stamp + force full rebuild on mismatch | 23a8369 | schema.py, update.py |
| 2 | Test — deriver version bump forces rebuild at unchanged HEAD | 92f02c3 | test_update_full.py |

## What Was Built

**schema.py:** Added `DERIVER_VERSION = 1` immediately below `SCHEMA_VERSION`, with a comment stating it should be bumped whenever derivation logic changes (e.g. `classification.classify`, app_kind precedence, derived-edge rules) so existing graphs auto-rebuild.

**update.py `run()`:** After reading `prev = _get_metadata(conn, "last_indexed_commit")`, reads `stored_deriver = _get_metadata(conn, "deriver_version")`. If `prev is not None` (existing graph) and `stored_deriver != str(schema.DERIVER_VERSION)`, sets `full = True` and prints a one-line stderr hint. The existing full-rebuild path is reused as-is — no duplicated logic. At the end of every successful transaction, writes `_set_metadata(conn, "deriver_version", str(schema.DERIVER_VERSION))`.

**test_update_full.py:** Two new tests:
- `test_deriver_version_bump_forces_rebuild`: builds graph, stamps `deriver_version=0`, deletes function node, calls `run(full=False)` at unchanged HEAD, asserts function re-derived and deriver_version updated.
- `test_unchanged_deriver_version_still_short_circuits`: builds graph, deletes function node, calls `run(full=False)` at unchanged HEAD with current deriver_version, asserts function node stays absent (short-circuit fired).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test sentinel approach: rename vs delete**
- **Found during:** Task 2 (first test run)
- **Issue:** Plan spec said to UPDATE a function node name to `STALE_SENTINEL` as the stale-value probe. But `upsert_records` keys nodes on `(kind, name, path)` — renaming a node doesn't overwrite it; a full rebuild inserts the real-name node alongside the renamed one, so both exist post-rebuild. The rename-based sentinel can't prove the rebuild cleared the stale value.
- **Fix:** Changed the test to DELETE the function node instead. Full rebuild re-inserts it; short-circuit leaves it absent. The DELETE approach unambiguously distinguishes rebuild vs. no-rebuild.
- **Files modified:** `packages/graph-io/tests/test_update_full.py`
- **Commit:** 92f02c3

## Test Results

Full graph-io suite: **482 passed, 3 skipped, 1 xfailed** (no regressions).

New deriver_version tests: both pass.

## Self-Check: PASSED

- packages/graph-io/src/graph_io/schema.py: FOUND, contains DERIVER_VERSION
- packages/graph-io/src/graph_io/update.py: FOUND, contains deriver_version mismatch check
- packages/graph-io/tests/test_update_full.py: FOUND, contains both new tests
- Commit 23a8369: FOUND
- Commit 92f02c3: FOUND
