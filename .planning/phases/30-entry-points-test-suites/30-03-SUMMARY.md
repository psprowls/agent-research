---
phase: 30-entry-points-test-suites
plan: 03
subsystem: graph-io
tags:
  - graph-io
  - test-suites
  - emitter
  - re-parenting

requires:
  - phase: 28-graph-io-foundation
    provides: "test_suite_uri helper, GraphRecords upsert, store.transaction context"
  - phase: 29-structural-nodes-containment-tree
    provides: "Repository + Package + SubPackage + File node emission; _TEST_DIR_NAMES; _resolve_import_root"
  - phase: 30-entry-points-test-suites
    provides: "Module-level _owning_package (Plan 30-01); amended _is_test_path with D-01 src-override (Plan 30-01)"

provides:
  - "test_suites.emit(conn, *, repo_root, ctx, skip_dirs) — flat TestSuite node emitter (TEST-01..07)"
  - "Atomic re-parenting: every is_test=true File moves from Repository -> File to TestSuite -> File via DELETE-then-INSERT (D-14)"
  - "Tests-edge derivation: TestSuite -> Package via Python (D-10) + JS/TS (D-11) import scans; TestSuite -> Repository at K>=5 (D-12)"
  - "D-17 kind classification (integration/e2e/contract/unit/unknown)"
  - "D-18 framework-config testpaths discovery (pyproject [tool.pytest.ini_options] + pytest.ini)"

affects:
  - 30-04-update-orchestration
  - 31-domain-layer-derived-edges
  - 32-query-layer

tech-stack:
  added: []
  patterns:
    - "Atomic re-parenting via DELETE-then-INSERT inside the outer update.run transaction"
    - "Flat suite naming convention: repo-owned suites use full rel_path; package-owned suites use basename + path discriminator (D-16)"
    - "Import-scan via two compiled regexes (_PYTHON_IMPORT_RE / _JS_IMPORT_RE) + best-effort JS relative-spec resolution against common extension list"

key-files:
  created:
    - packages/graph-io/src/graph_io/test_suites.py
    - packages/graph-io/tests/test_test_suites.py
  modified:
    - packages/graph-io/src/graph_io/structural_nodes.py

key-decisions:
  - "K=5 threshold for the TestSuite -> Repository edge is a module-private constant _REPOSITORY_EDGE_THRESHOLD; can be tuned without changing call sites"
  - "JS relative-spec resolution tries 6 common extensions + 6 index.* shapes; first existing match wins; if no Package owns the resolved path, the spec is silently skipped (no edge)"
  - "Suite naming differs by owner: repository-owned suites use the full rel_path so 'tests/integration' and 'tests/unit' are distinguishable; package-owned suites use the basename ('tests' / '__tests__') with path as the upsert discriminator"

patterns-established:
  - "An emitter module receives no explicit transaction object — it operates inside whatever transaction the caller (update.run for production, store.transaction for tests) has opened"
  - "Defensive parse: malformed config -> stderr warning + fall back to filesystem-only discovery"
  - "Idempotency invariant: re-running emit() with no FS changes produces a byte-identical edge set"

requirements-completed:
  - TEST-01
  - TEST-02
  - TEST-03
  - TEST-04
  - TEST-05
  - TEST-06
  - TEST-07

duration: 7min
completed: 2026-05-26
---

# Phase 30 Plan 03: Test-Suites Emitter Summary

**`test_suites.emit` discovers test root directories from filesystem layout + framework config, emits flat TestSuite nodes, atomically re-parents every is_test=true File from Repository to its TestSuite, and derives `tests` edges from per-file import scans with a K=5 whole-system fallback.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-26T02:44:51Z
- **Completed:** 2026-05-26T02:51:34Z
- **Tasks:** 4 completed
- **Files modified:** 3 (1 new module + 1 new test file + 1 hotfix to Phase 29 structural_nodes)

## Accomplishments
- New module `packages/graph-io/src/graph_io/test_suites.py` (≈460 lines) exposes a single public `emit()` plus private discovery, classification, and import-scan helpers.
- Test-root discovery (`_discover_test_roots`) covers repo-root `tests/` (subdirs-or-flat), Package-local `tests/` + `__tests__/`, and pyproject `[tool.pytest.ini_options] testpaths` / pytest.ini config-driven roots (D-18).
- Flat suite emission (TEST-07): `tests/integration/auth/` produces ONE TestSuite named `tests/integration/auth/`, never nested.
- D-17 kind classification follows priority order: dir-name tokens (integration/e2e/system/contract) -> filename `*_spec.*` -> filename `test_*.py` / `*.test.*` -> unknown.
- Atomic re-parenting (D-14): every is_test=true File's existing `physically_contains` parent edge is DELETEd and a fresh TestSuite -> File edge INSERTed, all inside the outer transaction.
- `_emit_tests_edges` scans each test file for Python imports (`_PYTHON_IMPORT_RE`) and JS/TS bare + relative specs (`_JS_IMPORT_RE`), looks up each match against the first-party Package map, deduplicates per-suite, and emits one TestSuite -> Package edge per pair. When >= K=5 distinct first-party packages are imported by a suite, an additional TestSuite -> Repository edge is emitted (D-12).
- 14 unit tests cover all 13 named cases from the plan's behavior list plus the skeleton-import test. All 211 graph-io tests pass.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: skeleton-import test** — `d2e24a6` (test)
2. **Task 1 GREEN: module skeleton + discovery + classification** — `1fbcb69` (feat)
3. **Task 2 RED: TestSuite emission + re-parenting tests** — `0d74c7d` (test)
4. **Task 2 GREEN: emit body + atomic re-parenting** — `ce6fe5d` (feat)
5. **Task 3 RED: tests-edge derivation tests** — `bb17f1a` (test)
6. **Task 3 GREEN: `_emit_tests_edges` + Phase 29 orphan-test-file hotfix** — `6fe73d4` (feat)
7. **Task 4: D-17 classification + D-18 config + malformed + idempotency tests** — `ea5a0d9` (test)

## Files Created/Modified
- `packages/graph-io/src/graph_io/test_suites.py` — new module; emit + discovery + classification + import-scan helpers.
- `packages/graph-io/tests/test_test_suites.py` — new test file; 14 tests including 13 named cases from the plan.
- `packages/graph-io/src/graph_io/structural_nodes.py` — **hotfix**: orphan test files (paths outside any Package) are now emitted as File nodes with Repository parent so test_suites.emit can re-parent them. D-14 mandated this from Phase 29 but the original implementation skipped them.

## Decisions Made
- **K=5 threshold for whole-system edge.** Module-private constant `_REPOSITORY_EDGE_THRESHOLD = 5` keeps the threshold tunable without touching call sites or attrs.
- **JS extension fallback list.** Relative specs (`./foo`) are resolved by trying the exact path, then `.ts/.js/.tsx/.jsx/.mjs/.cjs`, then `index.<ext>` inside the directory. First hit wins; misses are silent (no edge).
- **Suite naming differs by owner.** Repo-owned suites use the full rel_path as name (so two repo-root suites like `tests/integration` and `tests/unit` are distinguishable). Package-owned suites use the basename (`tests` / `__tests__`) with path as the upsert discriminator (so a Python `tests/` and a JS `__tests__/` in different packages don't collide). D-16 left this to Claude's discretion.
- **Conditional-export uniqueness pattern reused** (carried over from Plan 30-02): the SQLite `(kind, name, path)` upsert key is the natural disambiguator for nodes that share a display name.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Hotfix Phase 29 orphan-test-file emission**
- **Found during:** Task 3 — `test_tests_edge_python_imports` failed because test files at repo-root `tests/integration/` were never emitted as File nodes (Phase 29 `structural_nodes.emit` skipped files outside any Package).
- **Issue:** Phase 29 D-14 specifies `Repository -> File for test files only`, but the implementation comment at line 555-557 acknowledged the intent and the code skipped them. Plan 30-03 must_haves explicitly require repo-root tests to become TestSuite-parented File nodes (lines 38, 45 of PLAN.md).
- **Fix:** Added an orphan-test-file branch to `structural_nodes.emit`'s file loop: when `_owning_package` returns None and `_is_test_path` (with package_dirs) returns True, emit the File with `pkg_key = repo_key` so the existing `if is_test: parent_src = repo_key` branch handles parent placement. Non-test files outside any Package remain skipped.
- **Files modified:** `packages/graph-io/src/graph_io/structural_nodes.py`
- **Commit:** `6fe73d4` (combined with the Task 3 GREEN feat)
- **Verification:** All 39 prior Phase 29 structural_nodes tests still pass; new Plan 30-03 tests that depend on repo-root test File nodes now pass.

**Total deviations:** 1 Rule-2 auto-fixed. **Impact:** Carries a Phase 29 contract that was specified but not implemented; required by every Plan 30-03 must_have that mentions repo-root tests. No new public surface — the change is a single conditional inside the file loop.

## Verification Results

- `uv run --package graph-io pytest packages/graph-io/tests/test_test_suites.py -v` → **14 passed** in 0.45s.
- `uv run --package graph-io pytest packages/graph-io/tests/ -q` → **211 passed** in 10.25s (no regressions across the graph-io suite).
- `uv run --package graph-io python -c "from graph_io.test_suites import emit; print('ok')"` → **ok**.
- `grep -c 'kind="test_suite"' .../test_suites.py` → **1**.
- `grep -c '_REPOSITORY_EDGE_THRESHOLD' .../test_suites.py` → **3** (constant + two comparison sites).
- No new external deps verified by import grep (only stdlib + source_parser + graph_io).
- All 13 named test functions present (verified via grep -cE pattern → 13).

## Self-Check: PASSED

- File `packages/graph-io/src/graph_io/test_suites.py` exists and imports cleanly.
- File `packages/graph-io/tests/test_test_suites.py` exists with 14 tests.
- All 13 named test functions from the plan present.
- Phase 29 structural_nodes hotfix preserves all existing behavior (39/39 prior tests pass).
- Full graph-io suite: 211 passed.
- Commit hashes verified via `git log`.

## Next Plan Readiness

Plan 30-04 wires this module into `update.run()` after `entry_points.emit` and before `resolve.sweep`, asserts the call order via a unit test, and adds an end-to-end fixture run that exercises the JS `__tests__/index.test.js` file living next to a `_init_placeholder` so the directory is git-tracked. The 30-04 plan task 3 has an explicit guard verifying the Phase 29-04 fixture exists.
