---
phase: 30-entry-points-test-suites
plan: 01
subsystem: graph-io
tags:
  - graph-io
  - structural-nodes
  - is-test-amendment
  - helper-hoist
  - phase-30-hotfix

requires:
  - phase: 29-structural-nodes-containment-tree
    provides: "Original D-09 _is_test_path heuristic and pkg_index lookup inside emit()"

provides:
  - "D-01 src-override on _is_test_path: files inside a Package import root are is_test=False regardless of filename"
  - "_owning_package hoisted to a module-level function reusable by Phase 30 entry_points and test_suites emitters"

affects:
  - 30-02-entry-points
  - 30-03-test-suites
  - 30-04-update-orchestration

tech-stack:
  added: []
  patterns:
    - "Module-level helpers (_owning_package) reusable across emitter modules instead of per-emitter closures"

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/structural_nodes.py
    - packages/graph-io/tests/test_structural_nodes.py

key-decisions:
  - "D-01 src-override is keyword-only (package_dirs, repo_root) so legacy unit tests calling _is_test_path('test_foo.py') keep their D-09 verdict"
  - "Python vs JS/TS branch chosen by manifest probe (pyproject.toml / package.json) when repo_root is given; falls back to file extension otherwise"
  - "Root-Package sentinel (empty pkg_rel) is explicitly skipped in the override loop to avoid ambiguous import-root probes"

patterns-established:
  - "Heuristics that depend on Package context accept package_dirs as a keyword-only kwarg and degrade gracefully when called without it"

requirements-completed: []

duration: 2min
completed: 2026-05-26
---

# Phase 30 Plan 01: Amend `_is_test_path` Heuristic + Hoist `_owning_package` Summary

**D-01 src-override added to `_is_test_path`, and `_owning_package` hoisted to a module-level helper so Plans 30-02 and 30-03 can reuse the deepest-Package-wins lookup.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-26T02:35:22Z
- **Completed:** 2026-05-26T02:37:36Z
- **Tasks:** 2 completed (both TDD, RED+GREEN per task)
- **Files modified:** 2

## Accomplishments
- `_is_test_path` now applies the D-01 src-override: a file inside a Python Package's import root (`<pkg>/src/<importable>/` or `<pkg>/<importable>/`) or inside a JS/TS Package directory but outside any `tests/` subdir is `is_test=False` even when the filename matches `test_*.py` / `*.test.ts`.
- The `tests/` directory branch remains authoritative — anything under a `tests/` ancestor stays `is_test=True`.
- `_owning_package` is hoisted from a closure inside `structural_nodes.emit` to a module-level helper with signature `_owning_package(rel_path, pkg_index) -> tuple[str, str | None] | None`.
- All Phase 29 structural-node tests (36) plus 4 new Phase 30 tests pass (39 total — one combined hoist test + three D-01 cases).

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing test for module-level `_owning_package`** — `38a4d25` (test)
2. **Task 1 GREEN: hoist `_owning_package` to module level** — `99333b0` (feat)
3. **Task 2 RED: failing D-01 tests for `_is_test_path` src-override** — `750174c` (test)
4. **Task 2 GREEN: amend `_is_test_path` with D-01 src-override** — `d86a95d` (feat)

## Files Created/Modified
- `packages/graph-io/src/graph_io/structural_nodes.py` — `_owning_package` hoisted to module level; `_is_test_path` signature extended with `package_dirs` and `repo_root` keyword-only args plus the D-01 override logic; `emit()` call site updated to pass both kwargs.
- `packages/graph-io/tests/test_structural_nodes.py` — top-of-file imports `_is_test_path` directly; four new tests added (`test_owning_package_is_module_level_callable`, `test_is_test_path_filename_inside_import_root_is_not_test`, `test_is_test_path_tests_dir_branch_unchanged`, `test_is_test_path_jsts_inside_package_root_is_not_test`).

## Decisions Made
- **Keyword-only kwargs.** `package_dirs` and `repo_root` are keyword-only so existing single-arg call sites (and the unit tests inherited from Phase 29) continue to work without changes.
- **Manifest-based branch selection.** When `repo_root` is provided, the Python vs JS/TS branch is chosen by probing for `pyproject.toml` / `package.json` in the Package directory. Without `repo_root`, the file extension is used as a fallback.
- **Root-Package sentinel skipped.** Entries with empty `pkg_rel` in `package_dirs` are skipped because the import-root probe (`<pkg>/src/<importable>/__init__.py`) is ambiguous for a Package at repo root.

## Deviations from Plan

None — plan executed exactly as written. The algorithm matched the plan's step-by-step pseudocode, including the `repo_root=None` fallback and the legacy `package_dirs=None` behavior.

## Verification Results

- `uv run --package graph-io pytest packages/graph-io/tests/test_structural_nodes.py -q` → **39 passed** in 0.27s.
- `uv run --package graph-io python -c "from graph_io.structural_nodes import _is_test_path, _owning_package, _resolve_import_root; print('ok')"` → **ok**.
- `grep -c 'def _is_test_path' packages/graph-io/src/graph_io/structural_nodes.py` → **1** (no duplicate definition).
- `grep -c 'def _owning_package' packages/graph-io/src/graph_io/structural_nodes.py` → **1** (module-level only, no closure remains).

## Self-Check: PASSED

- `_owning_package` is a module-level function — confirmed.
- `_is_test_path` accepts `package_dirs` and `repo_root` keyword-only args — confirmed.
- Three new D-01 tests pass — confirmed.
- All existing Phase 29 tests still pass — confirmed (36/36).
- Commit hashes verified via `git log`.

## Next Plan Readiness

Plan 30-02 (`entry_points.emit`) and Plan 30-03 (`test_suites.emit`) can now import and reuse `_owning_package` from `graph_io.structural_nodes`. Plan 30-04 will exercise the amended `_is_test_path` end-to-end with the Phase 29-04 fixture (`packages/jspkg/__tests__/index.test.js` must remain `is_test=True` via the directory branch).
