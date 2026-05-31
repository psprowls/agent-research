---
phase: 55-dependency-classification-fix
plan: 02
subsystem: graph-io
tags: [graph-io, queries, describe-package, depends_on_package, cli]

# Dependency graph
requires:
  - phase: 55-dependency-classification-fix (plan 01)
    provides: "the depends_on_package edge emitted by packages.refresh()"
provides:
  - "describe_package() surfaces internal_dependencies (outgoing) and internal_dependents (incoming) via depends_on_package edges"
  - "PackageDescription gains two list fields (JSON via dataclasses.asdict)"
  - "cg describe-package human output renders both new collections"
affects: [phase-57-index-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Both-direction edge surfacing in a describe_* query via two parameterized edges JOIN nodes selects"

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/src/graph_io/cli/q_describe_package.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/test_cli_describe.py

key-decisions:
  - "Both new fields use field(default_factory=list) so the dataclass change is additive — existing constructions and asdict consumers unaffected"
  - "Both endpoint sides filtered to kind IN ('package','app') so an app-classified workspace member resolves"

patterns-established:
  - "Incoming (dependents) vs outgoing (dependencies) distinguished purely by which edge endpoint is matched to the queried name"

requirements-completed: [CLASS-02]

# Metrics
duration: 3 min
completed: 2026-05-28
---

# Phase 55 Plan 02: describe-package surfaces internal deps/dependents Summary

**`cg describe-package <name>` now surfaces both directions of the `depends_on_package` edge — internal dependents (incoming, SC#3) and internal dependencies (outgoing, D-08) — in JSON and human output.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-28T23:33:00Z
- **Completed:** 2026-05-28T23:35:46Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `PackageDescription` gains `internal_dependencies` (outgoing) and `internal_dependents` (incoming), both `field(default_factory=list)`.
- `describe_package()` adds two parameterized `edges JOIN nodes` SELECTs on `kind='depends_on_package'`: dst names where src is this package (dependencies), src names where dst is this package (dependents). Both endpoints filtered to `package`/`app`; ordered by name; empty lists when no edges.
- CLI human output renders two aligned lines (`internal deps:` / `internal dependents:`) after `counts:`; empty shows `-`. JSON output exposes the fields automatically via `dataclasses.asdict`.

## Task Commits

1. **Task 1: describe_package + PackageDescription fields** - `3d44d0b` (feat)
2. **Task 2: CLI text output rendering** - `7a2fcef` (feat)
3. **Task 3: query + CLI tests** - `a79f6b4` (test)

## Files Created/Modified
- `packages/graph-io/src/graph_io/queries.py` - two `PackageDescription` fields + two `describe_package` edge queries (both JOIN directions).
- `packages/graph-io/src/graph_io/cli/q_describe_package.py` - two `print` lines in the human branch.
- `packages/graph-io/tests/test_queries.py` - `test_describe_package_internal_deps_and_dependents` (both directions + empty-list case).
- `packages/graph-io/tests/test_cli_describe.py` - new `workspace_with_internal_dep` fixture + 3 tests (JSON outgoing, JSON incoming/SC#3, human output).

## JOIN directions
- **internal_dependencies (outgoing):** `SELECT dst.name ... WHERE kind='depends_on_package' AND src.name = ?` — packages this one depends on.
- **internal_dependents (incoming, SC#3):** `SELECT src.name ... WHERE kind='depends_on_package' AND dst.name = ?` — packages that depend on this one.

## New tests and what each asserts
- `test_describe_package_internal_deps_and_dependents` (query): seeds beta→alpha `depends_on_package`; asserts `alpha.internal_dependents == ["beta"]` (incoming), `beta.internal_dependencies == ["alpha"]` (outgoing), and an edgeless gamma has both empty.
- `test_cg_describe_package_internal_deps_json` (CLI): end-to-end via `cg update --full` over a workspace where beta declares alpha; asserts `beta` JSON `internal_dependencies == ["alpha"]`.
- `test_cg_describe_package_internal_dependents_json` (CLI): asserts `alpha` JSON `internal_dependents == ["beta"]` (SC#3).
- `test_cg_describe_package_internal_deps_human` (CLI): asserts the human output prints `internal deps:` and `alpha`.

## Decisions Made
None beyond the plan — executed as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CLASS-02 fully delivered across both plans (edge emission in 55-01, both-direction surfacing here).
- Phase 57 IDX-05 nesting / index generator can now consume `depends_on_package` and `describe_package().internal_dependencies`.
- Full graph-io suite green: 462 passed, 1 skipped (pre-existing), 1 xfailed.

---
*Phase: 55-dependency-classification-fix*
*Completed: 2026-05-28*
