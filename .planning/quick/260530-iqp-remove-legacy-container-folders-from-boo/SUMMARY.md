---
status: complete
phase: quick-260530-iqp
plan: "01"
subsystem: wiki-io
tags: [bootstrap, init_vault, cleanup, legacy-removal]
dependency_graph:
  requires: []
  provides: [init_vault-no-legacy-container-dirs]
  affects: [wiki-io/init_vault, wiki-io/tests/test_init_vault]
tech_stack:
  added: []
  patterns: [tdd-red-green]
key_files:
  created: []
  modified:
    - packages/wiki-io/src/wiki_io/init_vault.py
    - packages/wiki-io/tests/test_init_vault.py
decisions:
  - "Remove structural_dirs loop entirely rather than filtering — container vault_dirs must not be materialized at all"
  - "Leave pinned/_resolve_pinned_containers and manifest 'containers' write intact — detection metadata for scan/lint consumers preserved"
  - "Cosmetic wiki/packages/ strings in next_steps (lines 309/327) deferred — out of scope per plan constraints"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-30T19:36:48Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase quick-260530-iqp Plan 01: Remove Legacy Container Folders from Bootstrap Summary

**One-liner:** Removed `dependencies` from `FIXED_VAULT_DIRS` and eliminated the `structural_dirs` mkdir loop so vault bootstrap no longer materializes `dependencies/`, `apps/`, `packages/`, or `domains/` even when container detection returns them.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for legacy container removal | 59c680c | packages/wiki-io/tests/test_init_vault.py |
| 1 (GREEN) | Remove legacy container folder creation | 45bac22 | packages/wiki-io/src/wiki_io/init_vault.py |

## Changes Made

### packages/wiki-io/src/wiki_io/init_vault.py

- Dropped `"dependencies"` from `FIXED_VAULT_DIRS` (now 6 entries: concepts, architecture, adrs, entities, sources, .templates)
- Removed `structural_dirs = [c["vault_dir"] for c in pinned if c["vault_dir"]]` assignment
- Changed mkdir loop from `for d in structural_dirs + FIXED_VAULT_DIRS:` to `for d in FIXED_VAULT_DIRS:` — container vault_dirs are no longer materialized at all
- `pinned = _resolve_pinned_containers(...)` and `"containers": pinned` manifest write preserved unchanged

### packages/wiki-io/tests/test_init_vault.py

- Added `test_dependencies_not_in_fixed_vault_dirs` — asserts `"dependencies" not in FIXED_VAULT_DIRS`
- Added `test_legacy_container_folders_not_created_by_bootstrap` — stubs `_resolve_pinned_containers` to return non-empty list with vault_dirs `"apps"`, `"packages"`, `"domains"`; asserts none of those dirs nor `dependencies/` exist after `init_wiki`; asserts all canonical dirs (entities, concepts, architecture, adrs, sources, .templates) still exist

## Test Results

Full wiki-io test suite: **385 passed, 6 skipped, 1 xfailed** (all skips/xfails are pre-existing and expected).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Deferred Follow-up Items

- **Cosmetic `wiki/packages/` strings** in `init_vault.py` next_steps messages (lines 309 and 327) still reference `wiki/packages/` in user-facing output. These are display strings only and do not affect behavior. Flagged as out-of-scope by the plan; a future task should align them with the entities-folder model.
- **Broader scan/lint/template/prompt alignment**: `scan_monorepo.py`, `lint/container.py`, and prompt fragments may still reference legacy container folder concepts. Out of scope for this task.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The manifest `containers` write path (T-iqp-01) was preserved intact.

## Self-Check: PASSED

- `packages/wiki-io/src/wiki_io/init_vault.py` — modified, verified via grep and test run
- `packages/wiki-io/tests/test_init_vault.py` — modified, 8/8 tests pass including 2 new
- Commit 59c680c exists (RED phase test commit)
- Commit 45bac22 exists (GREEN phase implementation commit)
- `structural_dirs` no longer in init_vault.py (grep confirms)
- `"dependencies"` no longer in FIXED_VAULT_DIRS (grep confirms)
- `"containers": pinned` at line 268 (grep confirms)
