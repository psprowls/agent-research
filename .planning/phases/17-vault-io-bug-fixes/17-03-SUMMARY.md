---
phase: 17-vault-io-bug-fixes
plan: "03"
subsystem: vault-io
tags: [vault-io, workspace, repo-resolution, detect-containers, python, pytest]

requires:
  - phase: 16-carry-forward-debt-cleanup
    provides: workspace-io resolve_wiki_and_repo() second return value returning correct repo_root

provides:
  - "WSRES-01: init_vault.main() and detect_containers.main() resolve repo via resolve_wiki_and_repo() second return value"
  - "WSRES-02: detect_containers.detect() accepts optional workspace_path parameter with D-11 v1-layout guard"
  - "WSRES-03: synthetic-fixture unit tests covering v2 layout positive path and v1 guard"

affects: [17-vault-io-bug-fixes]

tech-stack:
  added: []
  patterns:
    - "workspace_path as optional parameter on pure classifier functions — keeps detect() env-free while enabling v2-layout exclusion"
    - "D-11 guard: exclude workspace subdir only when wp != repo_root AND wp.parent == repo_root"

key-files:
  created:
    - packages/vault-io/tests/test_detect_containers.py
  modified:
    - packages/vault-io/src/vault_io/init_vault.py
    - packages/vault-io/src/vault_io/detect_containers.py

key-decisions:
  - "Use resolve_wiki_and_repo() second return value for repo in both init_vault and detect_containers — wiki.parent is wrong under v2 layout"
  - "workspace_path exclusion is a per-call parameter on detect(), not a SKIP_DIRS extension — dynamic not constant"
  - "D-11 guard: only exclude when workspace is a proper subdir of repo_root (wp != repo_root AND wp.parent == repo_root)"

patterns-established:
  - "detect() stays pure — no internal call to resolve_wiki_and_repo(); env resolution stays in main()"

requirements-completed: [WSRES-01, WSRES-02, WSRES-03]

duration: 8min
completed: 2026-05-19
---

# Phase 17 Plan 03: vault-io WSRES Bug Fixes Summary

**Fixed workspace/repo resolution in init_vault and detect_containers using resolve_wiki_and_repo() second return value, added workspace_path exclusion on detect() with D-11 v1-layout guard, and 4 synthetic-fixture unit tests covering v2 positive path and v1 guard.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-19T20:51:00Z
- **Completed:** 2026-05-19T20:59:43Z
- **Tasks:** 2
- **Files modified:** 3 (2 source edits, 1 new test file)

## Accomplishments

- Replaced `repo = wiki.parent` with `wiki, repo = resolve_wiki_and_repo()` in both `init_vault.main()` and `detect_containers.main()` — fixes v2 layout repo root resolution (WSRES-01)
- Added optional `workspace_path` parameter to `detect()` with D-11 guard preventing v1-layout self-exclusion (WSRES-02)
- `detect_containers.main()` now passes `workspace_path=wiki.parent` to `detect()` so the workspace dir is never self-classified as a `docs` container under v2 layout
- 4 passing unit tests in `test_detect_containers.py` covering v2 positive path, workspace exclusion, v1 guard, and end-to-end synthetic monorepo scenario (WSRES-03)

## Task Commits

1. **Task 1: Fix repo resolution + add workspace_path exclusion (WSRES-01, WSRES-02)** - `57d185c` (fix)
2. **Task 2: Synthetic-fixture unit tests for v2 layout and v1 guard (WSRES-03)** - `20006d1` (test)

## Files Created/Modified

- `packages/vault-io/src/vault_io/init_vault.py` — Line 305: `wiki, _ = ... ; repo = wiki.parent` → `wiki, repo = resolve_wiki_and_repo()`
- `packages/vault-io/src/vault_io/detect_containers.py` — `detect()` signature + D-11 exclusion logic; `main()` resolver and `detect()` call updated
- `packages/vault-io/tests/test_detect_containers.py` — New file: 4 unit tests using `tmp_path` + `monkeypatch.setenv`

## Decisions Made

- Used `Path.resolve()` equality (not `samefile()`) for the D-11 guard — symlinks are not a concern in this context (per CONTEXT.md discretion list)
- Tests call `detect()` directly with synthetic paths — no mocking of `resolve_wiki_and_repo()` needed

## Deviations from Plan

None — plan executed exactly as written.

**Note:** `test_scan_companion_fold.py::test_layout_pinned_package_skips_companions` was pre-existing failing when this plan started (written by concurrent Plan 17-01/02 for SCAN fixes whose source implementation has not yet landed). This failure is not caused by WSRES changes — confirmed by git stash verification. 76 pre-existing tests + 4 new tests = 80 pass when excluding that pre-existing failure.

## Issues Encountered

Pre-existing test failure from concurrent Plan 17-01 (SCAN companion-fold): `test_scan_companion_fold.py::test_layout_pinned_package_skips_companions`. The test file was committed by Plan 17-01 before the matching source implementation in `scan_monorepo.py` landed. Not caused by this plan's changes; confirmed by stash/unstash verification.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- WSRES requirements fully addressed; `detect_containers --json` no longer self-classifies the workspace dir as a `docs` container under v2 layout
- Both source files now use workspace-aware repo resolution for both v1 and v2 layouts
- Phase 17 WSRES cluster complete pending orchestrator merge

## Self-Check: PASSED

- `packages/vault-io/tests/test_detect_containers.py` — FOUND
- `packages/vault-io/src/vault_io/detect_containers.py` — FOUND
- `packages/vault-io/src/vault_io/init_vault.py` — FOUND
- `.planning/phases/17-vault-io-bug-fixes/17-03-SUMMARY.md` — FOUND
- Commit `57d185c` (Task 1) — FOUND
- Commit `20006d1` (Task 2) — FOUND
