---
phase: 55-dependency-classification-fix
plan: 01
subsystem: graph-io
tags: [graph-io, packages, classification, depends_on_package, dependency-node, pep503]

# Dependency graph
requires:
  - phase: 50-app-reclassification
    provides: "classify() package/app kinds + the derived_edges D-04 stored-kind dst resolution pattern"
provides:
  - "CLASS-01 suppression: refresh() no longer emits a dependency node for any name matching a workspace package/app"
  - "depends_on_package edge (src=consumer, dst=internal package) for internal package->package deps"
  - "retargeted used_by edge resolved to the internal target's real package/app node (D-07)"
  - "_normalize_name() PEP 503-style name canonicalizer (lowercase + - to _)"
affects: [phase-55-02-describe-package, phase-57-index-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Internal package->package dependency = two same-direction edges (used_by + depends_on_package), intentionally redundant"
    - "Edge dst resolved to the target's ACTUAL stored node name + kind (not the consumer's declared spelling)"

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/packages.py
    - packages/graph-io/tests/test_packages.py

key-decisions:
  - "Edge dst uses the workspace package's actual node name (info[name]), not the consumer's declared dep spelling, so the edge resolves to the existing node instead of inserting a stub"
  - "No schema migration: depends_on_package is a free-text edge kind in edges.kind, distinct from the Domain->Domain depends_on by (src,dst,kind)"
  - "Shared seen_edges dedupe set across external and internal used_by edges preserves per-(consumer,target) dedupe for both edge kinds"

patterns-established:
  - "Workspace-name set + normalized-name -> (kind, name, rel_path) map built once in a pre-pass over the materialized _discover_manifests() list, before any dep accumulation"

requirements-completed: [CLASS-01, CLASS-02]

# Metrics
duration: 4 min
completed: 2026-05-28
---

# Phase 55 Plan 01: Suppress workspace-name dependency nodes + emit depends_on_package edge Summary

**graph-io's refresh() now suppresses the `dependency` node for any dependency naming a workspace package/app and emits a `depends_on_package` edge plus a retargeted `used_by` edge resolved to the real package/app node.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-28T23:29:08Z
- **Completed:** 2026-05-28T23:32:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- CLASS-01: a normalized workspace-package-name set is built once (PEP 503-style, `-`/`_` collapsed, lowercased) and gates dependency-node emission; cross-ecosystem; self-deps skipped.
- CLASS-02 / D-04: a new distinct `depends_on_package` edge kind (src=consumer, dst=internal package) is emitted from the same manifest-declaration parse where the `dependency` node is suppressed — no schema migration (free-text edge kind).
- CLASS-02 / D-07: the `used_by` edge for an internal pair is kept but retargeted from `("dependency", name, None)` to the internal target's REAL stored kind + name + rel_path; `depends_on_package` is emitted in addition (intentional two-edge redundancy, inline-commented).
- External (non-workspace) deps are unaffected — name-scoped suppression, verified by a boto3 regression assertion.

## Task Commits

1. **Task 1: Suppress + emit edges in refresh()** - `30316ff` (feat)
2. **Task 2: Unit tests (+ Rule 1 bug fix)** - `ca16c5b` (test)

## Files Created/Modified
- `packages/graph-io/src/graph_io/packages.py` - `_normalize_name()` helper + `_DEPENDS_ON_PACKAGE_KIND` constant; pre-pass building `workspace_names`/`workspace_kinds`; suppression gate in the Python dep loop; two-edge internal emission with shared dedupe.
- `packages/graph-io/tests/test_packages.py` - 3 new tests: suppression + edge resolution + external regression (CLASS-01/02/D-07); dedupe; app-target stored-kind resolution.

## No schema migration needed
`depends_on_package` is a free-text value in the existing `edges.kind` TEXT column keyed by `(src, dst, kind)`. A Domain->Domain `depends_on` row and a Package->Package `depends_on_package` row are already distinct rows — no `schema.py` change, no migration file.

## New tests and what they cover
- `test_workspace_dep_suppressed_and_depends_on_package_emitted` — CLASS-01 (zero `dependency` nodes for the normalized workspace name, with a `graph-io`/`graph_io` separator mismatch exercising D-02), external-dep regression (boto3 keeps its node + used_by), CLASS-02 (one `depends_on_package` edge with src/dst joined kinds in package/app), D-07 (internal `used_by` dst is a package/app node, not `dependency`).
- `test_internal_dep_edges_dedupe_per_consumer` — one `used_by` and one `depends_on_package` when the internal dep is declared in both `[project.dependencies]` and `[dependency-groups]`.
- `test_internal_dep_on_app_target_resolves_app_kind` — D-07 stored-kind resolution: both edges' dst resolve to `kind='app'` when the target has `[project.scripts]`.

## Decisions Made
- Edge dst uses the workspace package's actual node name, not the consumer's declared spelling (see deviation below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Edge dst used the consumer's declared dep spelling instead of the workspace node's real name**
- **Found during:** Task 2 (the suppression test with a `graph-io` vs `graph_io` mismatch)
- **Issue:** Task 1 set the edge `dst` name to `dep_name` (the consumer's declared string, e.g. `graph-io`). The actual workspace node was created from its own manifest as `graph_io`, so the edge dst would not resolve to the existing node — `upsert` would insert a `graph-io` stub. This is exactly the dangling-dst risk flagged as T-55-01-T2 in the threat model.
- **Fix:** Store `info["name"]` (the real workspace node name) in the `workspace_kinds` map and use it as the edge dst name. Changed the map value from `(kind, rel_path)` to `(kind, name, rel_path)`.
- **Files modified:** packages/graph-io/src/graph_io/packages.py
- **Verification:** `test_workspace_dep_suppressed_and_depends_on_package_emitted` asserts dst name == `graph_io` and dst kind in (package, app); passes.
- **Committed in:** ca16c5b (Task 2 commit, alongside the test that surfaced it)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug)
**Impact on plan:** Correctness fix essential for the edge to resolve to the real node; no scope creep.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The `depends_on_package` edge is now emitted and resolvable; Plan 55-02 can read it back in `describe_package`.
- Full graph-io suite green: 458 passed, 1 skipped (pre-existing), 1 xfailed.

---
*Phase: 55-dependency-classification-fix*
*Completed: 2026-05-28*
