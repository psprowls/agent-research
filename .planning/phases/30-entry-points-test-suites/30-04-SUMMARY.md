---
phase: 30-entry-points-test-suites
plan: 04
subsystem: graph-io
tags:
  - graph-io
  - update-orchestration
  - strict-tree-invariant
  - call-order-pitfall
  - fixture-extension

requires:
  - phase: 29-structural-nodes-containment-tree
    provides: "update.run scaffolding with structural_nodes.emit + resolve.sweep call order; sample_monorepo fixture base"
  - phase: 30-entry-points-test-suites
    provides: "entry_points.emit (Plan 30-02), test_suites.emit (Plan 30-03), Phase 29 orphan-test-file emission hotfix (Plan 30-03)"

provides:
  - "update.run is the canonical writer for Phase 30 data — entry_points + test_suites + invariant run on every cg update inside one transaction (D-21)"
  - "Always-on strict-tree invariant check (D-19b) — _enforce_strict_tree_invariant raises StrictTreeInvariantError and rolls back the transaction on duplicate physically_contains parents"
  - "Extended sample_monorepo fixture with two Phase 30 test files (D-19a)"
  - "Call-order pitfall regression test that proves SC#3/SC#4/SC#5 via SQL surrogates against the post-update.run DB"

affects:
  - 31-domain-layer-derived-edges
  - 32-query-layer
  - 33-cg-cli-commands

tech-stack:
  added: []
  patterns:
    - "Single deferred-import line pulls every emitter the orchestrator needs (entry_points + structural_nodes + test_suites) to keep the import cycle one-directional"
    - "Always-on invariant check inside the orchestrator transaction — a raise propagates and rolls back metadata writes too, so the on-disk DB stays at the previous indexed commit"
    - "Workspace-level pytest norecursedirs guard for src/ trees so ontology-named modules (e.g. test_suites.py) don't get collected as test modules"

key-files:
  created:
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/__tests__/index.test.js
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/__tests__/__init__placeholder
    - packages/graph-io/tests/fixtures/conftest.py
  modified:
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/tests/test_test_suites.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/tests/test_foo.py
    - packages/graph-io/tests/test_structural_nodes.py
    - pyproject.toml

key-decisions:
  - "Deferred import combines entry_points + structural_nodes + test_suites in a single line — minimizes the diff to update.run and keeps the cycle-avoidance rationale documented at one site"
  - "_enforce_strict_tree_invariant runs AFTER resolve.sweep but BEFORE _set_metadata so a violation rolls back the metadata writes (last_indexed_commit / last_indexed_at) too; the on-disk DB stays at the previous indexed commit"
  - "StrictTreeInvariantError message truncates the offending_child_ids list at 20 ids to keep CI logs usable; the full list is available via the attribute"
  - "Phase 29 fixture-regression test (test_physically_contains_is_strict_tree) updated in-place: test files now expected to have parent kind 'test_suite' post-Phase-30 wiring (D-14 hand-off Phase 29's comment anticipated); D-15 generic-container guard scoped to package/subpackage/file kinds because Phase 30 D-16 explicitly names the flat-tests TestSuite 'tests'"
  - "test_pyproject_scripts_entry_point_resolves_to_file uses pytest.skip when the fixture has no [project.scripts] — keeps the assertion in place for when the fixture grows one without breaking the suite today"

patterns-established:
  - "Ontology kinds with names that pytest would collect as tests (test_suites, test_files, etc.) must be excluded from collection at the workspace root via norecursedirs; per-package testpaths already scopes correctly"
  - "Fixture sub-trees with test_*.py files that depend on tmp_path-relative imports get a conftest.py with collect_ignore_glob=['*'] inside the fixtures dir"

requirements-completed: []

duration: 10min
completed: 2026-05-26
---

# Phase 30 Plan 04: Integration + Enforcement Summary

**`update.run` now invokes `entry_points.emit` + `test_suites.emit` + an always-on strict-tree invariant check inside the same transaction; the call-order pitfall regression test proves SC#3/SC#4/SC#5 against the extended sample_monorepo fixture; the full graph-io suite (215 passed + 1 skipped) verifies no regression.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-26T02:53:07Z
- **Completed:** 2026-05-26T03:03:50Z
- **Tasks:** 4 completed
- **Files modified:** 8 (3 created + 5 modified)

## Accomplishments
- `update.run` now imports `entry_points + structural_nodes + test_suites` in one deferred-import line and calls them in the D-21 order: `structural_nodes.emit -> entry_points.emit -> test_suites.emit -> resolve.sweep -> _enforce_strict_tree_invariant -> _set_metadata(...)`.
- New `StrictTreeInvariantError` class in `update.py` carries `offending_child_ids` and a D-20-shaped hint message. Module-private `_enforce_strict_tree_invariant(conn)` runs the literal SQL: `SELECT dst, COUNT(*) FROM edges WHERE kind='physically_contains' GROUP BY dst HAVING COUNT(*) > 1` and raises on any row. A raise propagates up and `store.transaction` rolls back the entire write — the on-disk DB stays at the previous indexed commit.
- Extended the Phase 29-04 `sample_monorepo` fixture: `packages/mypkg/tests/test_foo.py` now imports `mypkg.foo` (so test_suites.emit deterministically produces a TestSuite -> Package(mypkg) edge), and `packages/jspkg/__tests__/index.test.js` + `__init__placeholder` are new files that exercise the JS package-local `__tests__/` branch.
- Five integration tests cover the Phase 30 success criteria via SQL against the post-`update.run` DB:
  - `test_call_order_pitfall` — D-19a's five assertions (one parent, parent is TestSuite, Package excludes test file, integration suite kind, two-run idempotency)
  - `test_strict_tree_invariant_raises_on_duplicate_parent` — D-19b runtime check fires on a corrupted DB
  - `test_anti_regression_describe_package_smoke` — SC#5 surrogate (Package(mypkg) still findable post-pipeline)
  - `test_shebang_script_in_fixture_does_not_emit_entry_point` — ENTRY-05 anti-test
  - `test_pyproject_scripts_entry_point_resolves_to_file` — SC#4 path-qualified resolution (pytest.skip when fixture has no [project.scripts])
- 215 graph-io tests pass + 1 skipped (SC#4 test, expected — fixture has no pyproject [project.scripts]). 730 tests pass workspace-wide + 27 skipped (integration/eval gates).

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: failing test for StrictTreeInvariantError + helper** — `eadfe1f` (test)
2. **Task 1 GREEN: exception + invariant helper** — `410369e` (feat)
3. **Task 2 RED: failing call-order test** — `366e742` (test)
4. **Task 2 GREEN: wire emit + invariant into update.run + Phase 29 test updates** — `6b6712c` (feat)
5. **Task 3: extend sample_monorepo fixture (D-19a)** — `6b60666` (feat)
6. **Task 4: 5 integration tests + fixtures conftest + workspace pytest norecursedirs** — `841168a` (test)

## Files Created/Modified
- `packages/graph-io/src/graph_io/update.py` — new exception + helper + wiring inside `run()`.
- `packages/graph-io/tests/test_test_suites.py` — 7 new tests (one Task-1 skeleton + one Task-2 ordering check + 5 Task-4 integration tests).
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/tests/test_foo.py` — content rewritten from bare `assert True` to `from mypkg.foo import foo` + `test_smoke()` so the fixture deterministically produces a `TestSuite -> Package(mypkg)` tests-edge.
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/__tests__/index.test.js` — new JS test file that requires `../index.js`.
- `packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/__tests__/__init__placeholder` — keeps the directory git-tracked even if the .test.js file is ever removed.
- `packages/graph-io/tests/fixtures/conftest.py` — new file with `collect_ignore_glob = ["*"]` so pytest doesn't try to import fixture test_*.py files at collection time.
- `packages/graph-io/tests/test_structural_nodes.py` — Phase 29 test `test_physically_contains_is_strict_tree` updated: (a) Assertion 4 now expects `parent_kinds == {"test_suite"}` after Phase 30 wiring; (b) Assertion 7 D-15 generic-container guard scoped to `kind IN ('package','subpackage','file')` so the Phase 30 `TestSuite(name='tests')` for a flat repo-root tests/ doesn't trip it.
- `pyproject.toml` — workspace-level `[tool.pytest.ini_options].norecursedirs` added so `packages/graph-io/src/graph_io/test_suites.py` (the emitter, named per the TestSuite ontology kind) isn't collected as a test module by workspace-root pytest runs.

## Decisions Made
- **Invariant placement.** `_enforce_strict_tree_invariant` runs AFTER `resolve.sweep` but BEFORE `_set_metadata`. A raise propagates and `store.transaction` rolls back the entire write — including the metadata writes — so the on-disk DB stays at the previous indexed commit. This is the strictest possible failure mode for a corrupted graph (per D-20).
- **Truncated id sample in the exception message.** The full `offending_child_ids` list is exposed via the attribute, but the message truncates to the first 20 ids to keep CI logs usable.
- **Phase 29 fixture test updated in-place rather than xfailed.** The Phase 29 comment said "Phase 30 will re-parent under TestSuite" — the post-Phase-30 shape IS the spec. Asserting it directly is more informative than a conditional `xfail`.
- **D-15 generic-container guard scoping.** Phase 29's D-15 forbade `tests` as a node name across all kinds. Phase 30's D-16 explicitly names the flat-tests TestSuite `tests` with `path='tests'` as the discriminator. The guard now scopes to the structural kinds (package/subpackage/file) that D-15 was actually protecting.
- **Workspace pytest `norecursedirs`.** Adding `src` (plus the usual ignore list) at the workspace root avoids re-collecting any future ontology-named modules. Per-package `testpaths = ["tests"]` already scopes things correctly when running inside a package; this is a guard for workspace-root invocations only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong column reference in test SQL**
- **Found during:** Task 4 — `test_call_order_pitfall` Assertion 1 used `COUNT(e.id)` but the `edges` table has no `id` column (composite primary key `(src, dst, kind)`).
- **Fix:** Changed to `COUNT(e.src)` (NULL-safe count of joined rows, equivalent for the assertion's intent).
- **Files modified:** `packages/graph-io/tests/test_test_suites.py`
- **Commit:** Folded into `841168a`.

**2. [Rule 2 - Missing critical functionality] Pytest collection of test_suites.py at workspace root**
- **Found during:** Full workspace test suite run after Task 4.
- **Issue:** `packages/graph-io/src/graph_io/test_suites.py` is named per the TestSuite ontology kind (matches the existing `entry_points.py` / `structural_nodes.py` pattern). Running pytest from the workspace root collects it as a test module because the filename starts with `test_`, then tries to call its imported symbol `test_suite_uri` (the URI helper from `graph_io.uri`).
- **Fix:** Added `norecursedirs = ["src", ...]` to the workspace `[tool.pytest.ini_options]` block. Per-package `testpaths = ["tests"]` already scopes pytest correctly when run inside a package; this guard catches workspace-root invocations.
- **Files modified:** `pyproject.toml`
- **Commit:** Folded into `841168a`.

**3. [Rule 2 - Missing critical functionality] Pytest collection of fixture test files**
- **Found during:** Full workspace test suite run.
- **Issue:** `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/tests/test_foo.py` imports `from mypkg.foo import foo` — that import only resolves once the fixture is copied to a tmp_path and pytest is invoked with the tmp_path as the project root. Letting pytest collect it in-place fails with `ModuleNotFoundError`.
- **Fix:** Added `packages/graph-io/tests/fixtures/conftest.py` with `collect_ignore_glob = ["*"]`.
- **Files modified:** `packages/graph-io/tests/fixtures/conftest.py` (new)
- **Commit:** Folded into `841168a`.

**4. [Rule 1 - Bug] Phase 29 test_physically_contains_is_strict_tree assertions stale post-Phase-30 wiring**
- **Found during:** Task 2 GREEN — after wiring `test_suites.emit` into `update.run`, the Phase 29 fixture regression test failed because (a) test files now have parent kind 'test_suite' (was 'repository'), and (b) the Phase 30 `TestSuite(name='tests')` for a flat repo-root tests/ trips the D-15 generic-container guard.
- **Fix:** Updated both assertions in-place to reflect the post-Phase-30 contract (D-14 hand-off Phase 29's comment explicitly anticipated; D-15 guard narrowed to structural kinds).
- **Files modified:** `packages/graph-io/tests/test_structural_nodes.py`
- **Commit:** Folded into `6b6712c`.

**5. [Rule 1 - Bug] mypkg.foo has no `hello` symbol**
- **Found during:** Task 3 — plan's spec showed `from mypkg.foo import hello`, but `mypkg/src/mypkg/foo.py` (from Phase 29-04) exports `foo`, not `hello`.
- **Fix:** Changed the import to `from mypkg.foo import foo`.
- **Files modified:** `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/tests/test_foo.py`
- **Commit:** Folded into `6b60666`.

**Total deviations:** 5 auto-fixed (3 Rule-1 bugs, 2 Rule-2 missing-functionality). **Impact:** None on the plan's contract — every must_have item still holds, all SC#3/SC#4/SC#5 surrogate assertions pass, the runtime invariant fires on a corrupted DB, and the full test suite (215 graph-io / 730 workspace) is green.

## Verification Results

- `uv run --package graph-io pytest packages/graph-io/tests/ -q` → **215 passed, 1 skipped** in 10.75s.
- `uv run pytest packages/ -q` → **730 passed, 27 skipped** in 98.06s (no regressions across the workspace).
- `uv run --package graph-io python -c "from graph_io.update import StrictTreeInvariantError, _enforce_strict_tree_invariant; print('ok')"` → **ok**.
- `grep -cE 'entry_points\.emit|test_suites\.emit|_enforce_strict_tree_invariant|StrictTreeInvariantError' packages/graph-io/src/graph_io/update.py` → **8** (≥5 required).
- Fixture tree confirmed: `packages/graph-io/tests/fixtures/sample_monorepo/` exists with `packages/mypkg/tests/test_foo.py` + `packages/jspkg/__tests__/index.test.js` + `__init__placeholder`.

## Self-Check: PASSED

- StrictTreeInvariantError + _enforce_strict_tree_invariant defined + importable.
- update.run sources include entry_points.emit + test_suites.emit + _enforce call in the D-21 order (verified by the test_update_run_calls_emitters_in_correct_order assertion).
- Five integration tests pass (one pytest.skipped because fixture has no [project.scripts]).
- 215/215 graph-io tests pass; 730/730 workspace tests pass.
- Commit hashes verified via `git log --oneline -10`.

## Next Phase Readiness

Phase 30 is complete: the four plans land entry-points + test-suites + strict-tree invariant + call-order pitfall test on top of Phase 29's structural foundation. Phase 31 (Domain Layer + Derived Edges) will introduce Domain nodes and the deferred D-13 TestSuite -> Domain edges. Phase 32 (Query Layer) will surface this data via SQL views. Phase 33 (cg CLI) will add the user-facing `cg list-entry-points`, `cg list-suites`, and `cg describe-package` commands that this plan's SC#3/SC#5 SQL surrogates anticipate.
