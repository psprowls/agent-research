---
phase: 32-query-layer-extensions
plan: 01
subsystem: graph-io
tags: [dataclasses, find-allowlist, fixture, queries, audit]

requires:
  - phase: 29-structural-nodes-containment-tree
    provides: lowercase node kinds, Repository/Package emit
  - phase: 30-entry-points-test-suites
    provides: EntryPoint/TestSuite emit + tests-edge derivation
  - phase: 31-domain-layer-derived-edges
    provides: domains.yaml emit + derived edges (references/depends_on/TS->Domain)
provides:
  - 4 new frozen dataclasses (RepoDescription, DomainDescription, EntryPointDescription, SuiteDescription) — import-time foundation for Plans 02/03
  - PackageDescription extended in place (domains/entry_points/test_suites with field(default_factory=list))
  - PathDescription extended in place (role_flags: dict[str, bool] | None)
  - _VALID_KINDS frozenset (10 lowercase kinds) + find() validation + kind-only branch
  - Session-scoped seeded_db fixture + function-scoped empty_db fixture in conftest
  - D-15 audit test (skips when domains.yaml absent; fails listing missing items when present-but-incomplete)
  - sample_monorepo fixture back-filled with pyutil, webutil, commonlib packages + tests/unit/test_core.py + multi-domain tests/integration/test_top.py + script entry + wildcard export
affects: [32-02, 32-03]

tech-stack:
  added: []
  patterns:
    - "Frozen dataclasses with `field(default_factory=list)` keep positional construction backward compatible when adding required-looking list fields"
    - "Read-only sqlite3.connect(f'file:{db}?mode=ro', uri=True) + session-scoped fixture pattern lifted from test_structural_nodes.py"
    - "Audit-failure remediation lives inside the same plan that defines the audit"

key-files:
  created:
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/pyutil/pyproject.toml
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/pyutil/src/pyutil/__init__.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/webutil/pyproject.toml
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/webutil/src/webutil/__init__.py
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/commonlib/pyproject.toml
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/commonlib/src/commonlib/__init__.py
    - packages/graph-io/tests/fixtures/sample_monorepo/tests/unit/test_core.py
    - .planning/phases/32-query-layer-extensions/32-01-SUMMARY.md
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/tests/conftest.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/fixtures/sample_monorepo/domains.yaml
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/jspkg/package.json
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/pyproject.toml
    - packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/src/mypkg/foo.py
    - packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py

key-decisions:
  - "Replaced PLAN's `subprocess.run(['uv','run','--package','graph-io','cg','update','--full'], ...)` with in-process `update.run(repo_root, full=True)` — matches test_structural_nodes.py pattern, avoids subprocess overhead, and lines up with the actual DB path (`workspace/.graph/code.db`, not the PLAN's incorrect `.graph-wiki/graph/code.db`)."
  - "Renamed cross-cutting package from `shared` to `commonlib` to avoid colliding with structural_nodes.py's D-15 generic-container-dir blocklist (`shared`, `common`, `packages`, etc.)."
  - "Back-filled sample_monorepo with 3 new python packages (pyutil/core, webutil/web, commonlib/none) + new TestSuite (tests/unit/) so the D-15 audit checklist clears: cross-cutting package, single-domain multi-package TS, multi-domain TS, callable EntryPoint via [project.scripts], wildcard EntryPoint via package.json exports."

patterns-established:
  - "Dataclass-field-shape test: import every new dataclass, assert dataclasses.fields(cls) field-name set is exactly the declared set, attempt mutation and catch FrozenInstanceError."
  - "Fixture audit pattern: a single test running multiple SQL existence checks against the seeded DB; collects all failures into one assertion message rather than failing on the first."

requirements-completed: [QUERY-01, QUERY-02, QUERY-03, QUERY-04]

duration: 25min
completed: 2026-05-26
---

# Phase 32 Plan 01: Query Layer Foundations Summary

**Typed foundation for Phase 32: 4 new frozen dataclasses, _VALID_KINDS allow-list driving find() validation, seeded/empty DB fixtures, and D-15 fixture audit — all green against a back-filled sample_monorepo.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 4
- **Files modified:** 12 (3 src/test + 9 fixture)

## Accomplishments
- Added 4 frozen dataclasses (Repo/Domain/EntryPoint/Suite Description) and extended PackageDescription + PathDescription in place — Wave 1+2 helpers can land on this foundation without further import-time changes.
- `find(conn, *, name=None, kind=None)` now validates `kind` against `_VALID_KINDS` (10 lowercase kinds) and supports kind-only listings with `ORDER BY name`.
- `seeded_db` + `empty_db` fixtures available to every graph-io test from conftest.
- D-15 audit checklist test passes against the back-filled fixture: ≥2 Domains, ≥1 `domain_contains_domain`, ≥1 cross-cutting Package, ≥1 callable EntryPoint, ≥1 wildcard EntryPoint, ≥1 single-domain TS->Domain edge, ≥1 multi-domain TS.

## Task Commits

1. **Tasks 1+2: Dataclasses + _VALID_KINDS + find() allow-list** — `99dae36` (feat)
2. **Task 3: seeded_db + empty_db fixtures** — `e4eb2cf` (test)
3. **Task 4: Wave 0 tests + sample_monorepo back-fill** — `71d5bb2` (test)

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -x` — 19 passed (15 pre-existing + 4 new Wave 0).
- `uv run --package graph-io pytest packages/graph-io/tests/` — 251 passed.
- `uv run --package graph-io python -c "from graph_io.queries import RepoDescription, DomainDescription, EntryPointDescription, SuiteDescription, PackageDescription, PathDescription; print('ok')"` exits 0.
- `uv run --package graph-io python -c "from graph_io.queries import _VALID_KINDS; assert _VALID_KINDS == frozenset({'function','class','method','file','package','repository','subpackage','entry_point','test_suite','domain'})"` exits 0.
- Backwards-compat: `PackageDescription(name='x', language='', version='', files=[], counts={})` constructs without the 3 new fields and they default to `[]`.

## Deviations from Plan

**[Rule 1 — bug] PLAN's seeded_db used wrong DB path** — Found during: Task 3 | Issue: PLAN specified `.graph-wiki/graph/code.db` but `update.run` writes to `workspace/.graph/code.db` (see `workspace_io.paths.graph_dir`). | Fix: changed fixture to call `update.run(repo_root, full=True)` directly + `graph_dir(ws)/'code.db'`. Mirrors `test_structural_nodes.py::test_physically_contains_is_strict_tree` which is the established in-repo pattern. | Verification: seeded_db opens successfully and the audit test runs against real data.

**[Rule 1 — bug] Renamed `shared` package to `commonlib`** — Found during: Task 4 (post-fixture-add test run) | Issue: structural_nodes.py D-15 has `shared` in its generic-container-dir blocklist; test_structural_nodes.py::test_physically_contains_is_strict_tree assertion 7 fails when any node named `shared` exists. | Fix: renamed package + directory + import in mypkg/foo.py. | Verification: full graph-io suite passes (251/251).

**Total deviations:** 2 auto-fixed (both Rule 1 — alignment with actual codebase). **Impact:** none on plan deliverables.

## Self-Check: PASSED

- All 4 task acceptance criteria run green.
- All 4 Wave 0 tests pass (1 audit test was failing initially with a list of missing fixture items — back-filled per the plan's audit-failure remediation contract; now green).
- Full graph-io test suite (251 tests) passes — no regressions introduced.

Ready for Plan 32-02.
