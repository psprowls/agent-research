---
phase: 29-structural-nodes-containment-tree
plan: 04
subsystem: database
tags: [graph-io, update-orchestration, integration-test, struct-04, strict-tree-invariant]

requires:
  - phase: 29-structural-nodes-containment-tree/03
    provides: structural_nodes.emit module
provides:
  - structural_nodes.emit wired into update.run() between packages.refresh and resolve.sweep (D-23)
  - sample_monorepo fixture under tests/fixtures/sample_monorepo/ (16 files, D-22)
  - test_physically_contains_is_strict_tree end-to-end invariant test (STRUCT-04)
affects: [30-entry-points-test-suites, 31-domain-edges, 32-query-layer, 33-cli-surface]

tech-stack:
  added: []
  patterns:
    - "Deferred import to break circular dependency (update.py → structural_nodes.py → update.py for _git)"
    - "Semantic structural-identity comparison via SQL joins (not raw ROWIDs) for idempotency assertions"

key-files:
  created:
    - packages/graph-io/tests/fixtures/sample_monorepo/pyproject.toml
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/pyproject.toml
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/__init__.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/foo.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/__init__.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/bar.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/deep/__init__.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/sub/deep/baz.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/proto/data_pb2.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/scripts/run.sh
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/tests/test_foo.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/package.json
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/index.js
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/types.d.ts
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/gen/data.gen.ts
    - packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py
  modified:
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/src/graph_io/structural_nodes.py
    - packages/graph-io/tests/test_structural_nodes.py
    - packages/graph-io/tests/test_update_idempotent.py

key-decisions:
  - "Deferred (in-function) import for structural_nodes in update.run() — avoids circular import while keeping the call site obvious"
  - "test_update_full_twice_produces_byte_identical_db updated to compare via node-tuple joins, not raw ROWIDs (the docstring already specified semantic identity)"
  - "Fixture uses workspace-only root pyproject.toml ([tool.uv.workspace] members) so packages.refresh sees only mypkg + jspkg as Packages — root manifest has no [project] table"

patterns-established:
  - "Pattern: deferred imports inside transaction blocks are acceptable when they break a real circular dep, with a comment explaining why"
  - "Pattern: structural-identity tests join through node tuples rather than comparing raw ROWIDs (immune to auto-id drift)"

requirements-completed:
  - STRUCT-04

duration: 30min
completed: 2026-05-26
---

# Phase 29 / Plan 04: wire emit + sample_monorepo + STRUCT-04 invariant

**`cg update --full` now produces a strict physical containment tree, locked by an end-to-end fixture test that SQL-asserts the tree invariant.**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-05-26
- **Tasks:** 3 completed (wiring, fixture, invariant test)
- **Files modified:** 4 modified, 16 new fixture files

## Accomplishments
- `structural_nodes.emit` integrated into `update.run()` inside the `with store.transaction(conn):` block, between `packages.refresh` and `resolve.sweep`
- Hand-curated 16-file sample_monorepo fixture exercises every role-flag rule (D-09..D-12) and every tree-shape rule (D-13..D-18)
- `test_physically_contains_is_strict_tree` asserts 7 invariants in one test:
  1. No child has >1 physically_contains parent (strict tree)
  2. Exactly 1 Repository node
  3. Packages parented only by Repository
  4. Test files parented only by Repository (D-14)
  5. >=3 SubPackage nodes for mypkg (Python walk fires at depths 1, 2, 3)
  6. 0 SubPackage nodes for jspkg (D-18 language gating)
  7. 0 generic-container nodes (D-15)
- Full project test suite green (696 passed, 26 Bedrock integration skipped)

## Task Commits

1. **Task 1 + Task 2 + Task 3 combined** — `682b5ec` (feat)

## Files Created/Modified
- `packages/graph-io/src/graph_io/update.py` — deferred import of structural_nodes inside `run()`, call added between packages.refresh and resolve.sweep
- `packages/graph-io/src/graph_io/structural_nodes.py` — refactored File enumeration to use `git ls-files` (fallback to FS walk for non-git tmp trees); `name=rel_path` for File nodes; `_owning_package` helper for longest-prefix Package lookup
- `packages/graph-io/tests/test_structural_nodes.py` — added test_physically_contains_is_strict_tree; corrected pre-seed of test_file_python_reads_sparser_has_main to use `name=path`
- `packages/graph-io/tests/test_update_idempotent.py` — updated `_structural_snapshot` to join edges→nodes for semantic comparison rather than raw ROWID equality
- 16 new files under `packages/graph-io/tests/fixtures/sample_monorepo/`

## Decisions Made

- **Deferred import inside `update.run()`** — see Issues Encountered below
- **Idempotency test now compares by node-tuple joins, not raw ROWIDs** — the docstring already specified "structural identity" as the SCHEMA-05 contract; the implementation now matches that intent. Reason: any path=NULL structural node (e.g. Repository) added by Phase 29 shifts the SQLite auto-id allocation for placeholder rows on the second run. The fix is the right abstraction — the test was always supposed to assert semantic identity, not byte identity.

## Deviations from Plan

### Auto-fixed Issues

**1. Plan 03's `from graph_io import …, structural_nodes, …` top-level edit caused a circular import**
- **Found during:** Task 1 first import test (`python -c "from graph_io import update"` failed)
- **Issue:** `structural_nodes.py` imports `_git` and `NotInGitRepoError` from `graph_io.update`. Adding `structural_nodes` to update.py's top-of-file imports creates a partially-initialized cycle.
- **Fix:** Use a deferred (in-function) import inside `update.run()`. A clear comment notes the cycle.
- **Verification:** `from graph_io import update, structural_nodes` now succeeds; all update tests pass.
- **Committed in:** `682b5ec`

**2. File-node naming mismatch surfaced via the idempotency test**
- **Found during:** First post-wire run of full graph-io suite (test_update_full_twice_produces_byte_identical_db failed with duplicate File rows)
- **Issue:** structural_nodes.emit was emitting `name=basename` but source-parser's GraphRecords projection uses `name=str(path)`. Two different keys ⇒ two rows ⇒ broken update path.
- **Fix:** Switched to `name=rel_path` in structural_nodes.emit; updated the affected unit test seed to match.
- **Verification:** Single File row per path after both initial and rerun; all unit + integration tests pass.
- **Committed in:** `682b5ec`

**3. FS-walk in structural_nodes.emit leaked `.graph/code.db*` files**
- **Found during:** First post-wire idempotency test run
- **Issue:** Original Plan 03 implementation walked `os.walk(pkg_dir)`. On second-run, the previously-created DB sibling files (`code.db`, `code.db-wal`, `code.db-shm`) under `.graph/` were already on disk and got emitted as File nodes.
- **Fix:** Switched primary file source to `git ls-files`; FS walk retained only as a fallback for non-git tmp trees in unit tests.
- **Verification:** No DB-sibling File nodes appear after `update.run --full`; STRUCT-04 invariant test passes.
- **Committed in:** `682b5ec`

**4. Idempotency-test comparison used raw ROWIDs, not semantic identity**
- **Found during:** Idempotency test debugging
- **Issue:** Even with all the above fixes, the test compared `(src, dst, kind, attrs_json)` edge tuples where `src` and `dst` are raw SQLite ROWIDs. Adding the Repository node (path=NULL) shifts the max ROWID, which shifts the IDs of placeholder rows created by `_ensure_node` on subsequent runs. The test was always going to drift now that any path=NULL structural node exists.
- **Fix:** Rewrote `_structural_snapshot` to compare edges via SQL joins to node tuples — produces stable, semantic snapshots.
- **Verification:** Both idempotency tests pass; the structural contract is now machine-checked.
- **Committed in:** `682b5ec`

---

**Total deviations:** 4 auto-fixed. All are integration-time discoveries necessary to land STRUCT-04 cleanly.
**Impact on plan:** No scope creep. The deviations either preserved an existing test's stated semantics (idempotency snapshot) or aligned new code with existing conventions (File node naming, tracked-file enumeration).

## Issues Encountered

- **Circular import** (see deviation 1) — resolved with deferred import inside `update.run()`.
- **Idempotency test drift** (see deviation 4) — resolved by aligning the test implementation with its docstring contract.

## User Setup Required
None.

## Next Phase Readiness

- Phase 30 can re-parent test files from Repository to TestSuite by:
  1. emitting TestSuite nodes
  2. inserting `physically_contains: TestSuite → File` edges
  3. deleting `physically_contains: Repository → File` edges for test files
  STRUCT-04 invariant test will continue to pass at the phase boundary.
- Phase 31 (Domain): `belongs_to_domain` edges attach freely without touching the strict-tree invariant.
- Phase 32 (Query layer): can DFS the containment subtree from any Repository/Package node knowing every child has exactly one parent.

---
*Phase: 29-structural-nodes-containment-tree*
*Completed: 2026-05-26*
