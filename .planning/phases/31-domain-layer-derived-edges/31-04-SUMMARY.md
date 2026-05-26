---
phase: 31-domain-layer-derived-edges
plan: 04
subsystem: graph-io
tags: [graph-io, derived-edges, references, depends-on, update-orchestration, testsuite-domain]
requires:
  - 31-02
  - 31-03
provides:
  - graph_io.derived_edges module (compute + two helpers)
  - update.run wiring for domains.emit + derived_edges.compute (D-16 order)
  - references / depends_on / TestSuite→Domain edges computed in one transaction (D-17)
affects:
  - Phase 32 query layer will consume references / depends_on edges
  - Phase 33 cg CLI subcommands for Domain queries
tech-stack:
  added:
    - "packages/graph-io/src/graph_io/derived_edges.py (new module)"
  patterns:
    - "Single-transaction delete-then-recompute (D-17) — trivially idempotent at the compute level AND at the update.run orchestration level"
    - "Shared traversal for references + depends_on — single pass over the import graph, two bucket maps emit both edge kinds"
    - "Direct-membership-only at compute time (DERIVED-04) — transitive closure is a query-time concern"
key-files:
  created:
    - packages/graph-io/src/graph_io/derived_edges.py
    - packages/graph-io/tests/test_derived_edges.py
  modified:
    - packages/graph-io/src/graph_io/update.py
key-decisions:
  - "Tasks 1+2+3 landed together in one commit (34450c4) — compute() calls both helpers, so a stub-first sequence would have created a transient broken state. Same approach as Plan 31-03 used for tightly-coupled tasks."
  - "Deferred imports for domains + derived_edges inside update.run (Rule 1 deviation from plan AC#1) — top-of-module imports would create the circular cycle update -> derived_edges -> import_scan -> structural_nodes -> update. The codebase already uses the deferred-import pattern for entry_points/structural_nodes/test_suites for the same reason; adding domains+derived_edges to the same block is consistent with the existing convention."
  - "scan_package_imports only called for Packages with at least one belongs_to_domain edge (i.e., domain-member packages) — non-domain packages cannot be the SOURCE of a references / depends_on edge per D-08/D-09, so skipping them saves I/O without affecting correctness."
  - "Schema columns confirmed src/dst (not parent_id/child_id as CONTEXT.md pseudocode suggested) — the planner caught this in RESEARCH §6; the implementation uses the actual edges table columns."
requirements-completed:
  - DERIVED-03
  - DERIVED-04
duration: "30 min"
completed: 2026-05-26
---

# Phase 31 Plan 04: Derived Edges + update.run Wiring Summary

Final Wave 2 plan landing the `references`, `depends_on`, and
`TestSuite → Domain` derived edges, plus the `update.run` wiring that
calls `domains.emit` and `derived_edges.compute` in the D-16-locked
order. Closes Phase 31.

**Tasks:** 5 (skeleton+impl combined; wiring; tests)
**Files created:** 2 (derived_edges.py, test_derived_edges.py)
**Files modified:** 1 (update.py — net +9 lines)
**Duration:** ~30 min
**Test result:** 246 passed, 1 skipped (up from 237 — net +9 new tests, no Phase 28/29/30 regressions)

## Task Outcomes

| # | Task | Commit | Result |
|---|------|--------|--------|
| 1+2+3 | derived_edges.py module (compute + 2 helpers) | 34450c4 | Module imports; 15 AC pass across Tasks 1-3 |
| 4 | update.run wiring (D-16 call order) | c3491d1 | domains.emit + derived_edges.compute inserted; order check passes |
| 5 | 9 unit + end-to-end tests | 5c00b16 | 9/9 pass first run; 11 AC pass |

## update.run call order after Plan 31-04 (D-16 locked)

```
structural_nodes.emit
entry_points.emit
test_suites.emit
domains.emit            <-- INSERTED by 31-04
resolve.sweep
_enforce_strict_tree_invariant
derived_edges.compute   <-- INSERTED by 31-04
_set_metadata (last_indexed_commit + last_indexed_at)
```

## Derived edge semantics

- **references** (`Domain D` → `Package P`): emitted when at least one Package in D directly imports P AND P is NOT in D. `attrs.usage_count` = distinct importer count.
- **depends_on** (`Domain A` → `Domain B`, A ≠ B): emitted when at least one Package in A imports at least one Package in B. `attrs.usage_count` = distinct (importer, importee) pair count. **No self-loops** (D-09).
- **TestSuite → Domain** (kind=`tests`): emitted ONLY when (a) suite has ≥ 2 distinct `tests` edges to Packages; (b) every Package the suite touches belongs to the SAME single Domain; (c) no Package has extra Domain memberships beyond the intersection.

All three are recomputed in a single transaction with DELETE-then-INSERT semantics — trivially idempotent (D-17, SC#3).

## Deviations from Plan

**[Rule 1 - Bug/contradiction fix]** Plan Task 4 AC#1 specified module-top imports of `domains` and `derived_edges`. Implementing this would create a circular import (`update → derived_edges → import_scan → structural_nodes → update`). The codebase already uses deferred imports inside `run()` for `entry_points`/`structural_nodes`/`test_suites` to break the same cycle; I extended that block to include `domains` and `derived_edges`. AC#1's literal text fails by `grep`, but the structural intent (both modules accessible inside `run()`) is satisfied. AC#2/AC#3 (lines containing both call sites, ordering) all pass.

**Total deviations:** 1 (import-location only; behaviour unchanged)
**Impact:** None — full test suite remains green; existing deferred-import convention preserved.

## Self-Check: PASSED

- Key files exist on disk: `derived_edges.py`, `test_derived_edges.py`, updated `update.py`
- `git log --oneline --grep="31-04"` returns 4 commits
- All `<acceptance_criteria>` re-run: PASS (26 AC across 5 tasks, with the documented deviation on Task 4 AC#1)
- Plan-level `<verification>` (full graph-io suite): PASS — 246 passed, 1 skipped

## Phase 31 Closeout

Phase 31 is complete. All 9 requirements (DOMAIN-01..05 + DERIVED-01..04) are
satisfied. Net test count growth across the phase: +31 (8 import_scan + 14 domains
+ 9 derived_edges). The full graph-io suite stands at 246 passed / 1 skipped,
up from the Phase 30 baseline of 215 passed / 1 skipped.

Ready for Phase 32 (Query Layer Extensions).
