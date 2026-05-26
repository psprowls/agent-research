---
phase: 32-query-layer-extensions
plan: 03
subsystem: graph-io
tags: [recursive-cte, bubble-up, cross-cutting, queries]

requires:
  - phase: 32-query-layer-extensions
    provides: _VALID_KINDS, dataclasses, projectors, describe_*, list_* (plans 01+02)
provides:
  - 6 helpers completing the 16-helper Phase 32 surface (2 per-package + 4 bubble-up/cross-cutting)
  - _DOMAIN_DESCENDANTS_CTE module constant (defence-in-depth UNION for cycle safety)
  - 15 unit + edge-case tests including a paranoid CTE-cycle-termination test
affects: [33-cg-cli-extensions]

tech-stack:
  added: []
  patterns:
    - "Single-source recursive CTE constant + interpolation pattern: _DOMAIN_DESCENDANTS_CTE is a string fragment prepended to per-helper SQL bodies — keeps the recursive walk identical across tests_for_domain / domain_references / domain_depends_on"
    - "Defence-in-depth cycle safety: UNION (not UNION ALL) in the CTE provides implicit dedup; a test inserts a manually crafted cycle and asserts the helper returns within 5 seconds via signal.alarm"

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/tests/test_queries.py

key-decisions:
  - "Marked tests_for_domain and tests_for_package with `__test__ = False` at the test module's import site to prevent pytest's `python_functions` rule from collecting them as test cases (their names start with 'tests' which matches pytest's test-prefix heuristic once imported)."
  - "Added _make_node / _make_edge convenience wrappers in test_queries.py — PLAN's pseudo-signature `_upsert_node(conn, kind=..., name=..., attrs=...)` doesn't match the actual signature `_upsert_node(conn, GraphNode(...))`. The wrappers preserve the plan's intent without distorting upsert.py."
  - "cross_cutting_packages ranking uses SUM(usage_count), not distinct-domain count (D-11, deliberate divergence from ONTOLOGY-SPEC §11.4). Docstring explicitly flags this as a rendering choice, not a spec amendment."

patterns-established:
  - "Targeted edge-case tests for UNION branches: separate test for each branch using _make_node/_make_edge so a regression in one branch fails the targeted test, not the integrated `test_tests_for_domain_union`."
  - "Empty-DB variant per helper: every Wave 2 helper has a `_returns_empty_on_empty_db` test confirming the SQL returns `[]` (not raising) on an empty schema-applied DB."

requirements-completed: [QUERY-04]

duration: 25min
completed: 2026-05-26
---

# Phase 32 Plan 03: Recursive-CTE + Cross-Cutting Summary

**Closes Phase 32's helper surface: 6 bubble-up / cross-cutting query helpers backed by a single-source recursive CTE fragment, plus a paranoid CTE-cycle-termination test that guarantees future emitter bugs can't hang the query layer.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 5
- **Files modified:** 2

## Accomplishments
- 6 new helpers: `tests_for_package`, `entry_points_for_package`, `tests_for_domain`, `domain_references`, `domain_depends_on`, `cross_cutting_packages`.
- `_DOMAIN_DESCENDANTS_CTE` is the single source of truth for descendant-walking SQL — interpolated into 3 helpers.
- 15 new tests (8 happy-path + 6 empty-DB + 1 cycle-safety).
- All Phase 32 helpers (16/16) now present in `queries.py`.

## Task Commits

1. **Tasks 1-5: Helpers + CTE constant + tests** — `56133dc` (feat)

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -x` → 63 passed, 1 skipped (`test_domain_depends_on_no_self_loop` — fixture lacks depends_on edges, documented gracefully-skip behaviour).
- `uv run --package graph-io pytest packages/graph-io/tests/` → 295 passed, 1 skipped (zero regressions).
- `grep -nE "INSERT |UPDATE |DELETE FROM|CREATE |DROP " packages/graph-io/src/graph_io/queries.py` → no mutations (D-16 read-only).
- `grep -nE "kind='[A-Z]" packages/graph-io/src/graph_io/queries.py` → 0 hits (lowercase kinds throughout).
- `test_cte_cycle_safe` returns within 5s on an injected cycle → `signal.alarm` guard never fires.

## Deviations from Plan

**[Rule 1 — bug] PLAN's `_upsert_node(conn, kind=..., name=...)` signature is fake** — Found during: Task 5 (cycle-safety test write). | Issue: actual `_upsert_node(conn: sqlite3.Connection, node: GraphNode) -> int` — takes a single GraphNode, not kwargs. | Fix: added local `_make_node` / `_make_edge` helpers in test_queries.py that build the dataclasses and delegate. PLAN's intent preserved. | Verification: all 3 hand-built-fixture tests pass.

**[Rule 1 — bug] Pytest collected `tests_for_domain` and `tests_for_package` as tests** — Found during: Task 5 (first pytest run after appending tests). | Issue: pytest's `python_functions` default of `test_*` is implemented as a prefix match — `tests_for_domain` starts with "tests" which the matcher treats as a test name, raising `ERROR at setup of tests_for_domain: fixture 'domain_name' not found`. | Fix: set `tests_for_domain.__test__ = False` and `tests_for_package.__test__ = False` at the test module import site. Pytest respects this attribute and skips collection. | Verification: collect-only shows no `tests_for_*` test items; full suite passes.

**Total deviations:** 2 auto-fixed (both Rule 1 — runtime-reality reconciliation). **Impact:** test ergonomics; production helper API unchanged.

## Self-Check: PASSED

- All 5 task acceptance criteria run green (greps + import checks + tests).
- 63/63 + 1 graceful skip in test_queries.py (the skip is the documented empty-state behaviour for `depends_on`, not a failure).
- 295/295 + 1 skip in full graph-io test suite — no regressions.
- All 16 Phase 32 helpers exist in queries.py (4 describe_* + 6 list_* + 2 *_for_package + 4 domain helpers = 16).

Phase 32 complete. Phase 33 picks up: wires every Phase 32 helper to a `cg` subcommand.
