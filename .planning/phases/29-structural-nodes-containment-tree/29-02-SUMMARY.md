---
phase: 29-structural-nodes-containment-tree
plan: 02
subsystem: database
tags: [sqlite, resolve-sweep, structural-guard, struct-06]

requires:
  - phase: 28-schema-v2-uri-foundation
    provides: nodes.uri column (Phase 28 D-10), _upsert_node pop-uri-to-column path
provides:
  - resolve.sweep predicate extended with `AND uri IS NULL`
  - test_sweep_preserves_uri_bearing_structural_nodes sentinel test
affects: [29-03, 29-04, 30-test-suites-entry-points, 31-domain-edges]

tech-stack:
  added: []
  patterns: ["URI-bearing structural nodes survive resolve.sweep via uri-column predicate"]

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/resolve.py
    - packages/graph-io/tests/test_resolve.py

key-decisions:
  - "Self-maintaining sweep: new structural kinds (v1.7+) need no further sweep edits as long as they carry a URI"
  - "Sentinel test lives in test_resolve.py (unit under test is sweep), not test_structural_nodes.py"

patterns-established:
  - "Pattern: URI-bearing structural nodes carry path=NULL but non-NULL uri; orphan AST nodes carry both NULL"

requirements-completed:
  - STRUCT-06

duration: 5min
completed: 2026-05-26
---

# Phase 29 / Plan 02: resolve.sweep guard for URI-bearing structural nodes

**Locked the centerpiece Phase 29 safety net: `resolve.sweep` now distinguishes URI-bearing structural nodes from orphan AST nodes by predicate, not by hard-coded kind list.**

## Performance

- **Duration:** ~5 min
- **Completed:** 2026-05-26
- **Tasks:** 2 completed (RED test, GREEN edit)
- **Files modified:** 2

## Accomplishments
- Sentinel test `test_sweep_preserves_uri_bearing_structural_nodes` added (D-17), confirmed RED before edit
- `resolve.sweep` DELETE WHERE clause extended with `AND uri IS NULL` (D-16 / STRUCT-06)
- All 7 tests in test_resolve.py pass (6 pre-existing + 1 new sentinel)

## Task Commits

1. **Task 1 + Task 2 combined: sentinel test + sweep edit** - `fbd4124` (feat)

(Both tasks were committed atomically because the predicate edit is the smallest possible response to the RED sentinel — splitting the commit would have left the test red on disk.)

## Files Created/Modified
- `packages/graph-io/src/graph_io/resolve.py` - WHERE clause extended with `AND uri IS NULL` + one-line comment referencing D-16/STRUCT-06
- `packages/graph-io/tests/test_resolve.py` - new test_sweep_preserves_uri_bearing_structural_nodes (~25 lines)

## Decisions Made
None - plan executed exactly as written.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- Plan 03 (`structural_nodes.emit`) can safely emit Repository with `path=NULL` and SubPackage with `path=<rel>` — neither will be deleted by sweep
- The contract `URI-bearing ⇒ survives sweep` is now machine-checked, so Plan 04's wiring of structural_nodes.emit BEFORE resolve.sweep cannot silently break it

---
*Phase: 29-structural-nodes-containment-tree*
*Completed: 2026-05-26*
