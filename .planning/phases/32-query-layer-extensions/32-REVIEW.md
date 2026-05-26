---
phase: 32-query-layer-extensions
status: clean
reviewer: gsd-execute-phase (inline)
completed: 2026-05-26
---

# Phase 32 Code Review

**Status:** clean

## Scope

Reviewed files (against `f5d7383..HEAD`):

- `packages/graph-io/src/graph_io/queries.py` — +543 lines (4 new dataclasses, 16 new helpers, 1 module constant)
- `packages/graph-io/tests/conftest.py` — +64 lines (2 fixtures)
- `packages/graph-io/tests/test_queries.py` — +729 lines (~48 new tests across Wave 0/1/2 + parametrizations)
- `packages/graph-io/tests/fixtures/sample_monorepo/**` — 3 new python packages + 1 new test file + 4 modified fixture files

## Findings

### Bugs
None found. Spotted three plan-vs-reality bugs during execution and resolved each as documented deviations:

1. PLAN's `seeded_db` used wrong DB path (`.graph-wiki/graph/code.db`) — fixed to `workspace/.graph/code.db` via `graph_dir()`.
2. PLAN's `_load_entry_point_description` used `attrs.get("kind")` but emitter writes `entry_kind` — projector now reads both with `entry_kind` preferred.
3. PLAN's `_upsert_node(conn, kind=..., name=...)` kwargs don't match the actual signature (`GraphNode` positional) — wrapped via `_make_node` in test_queries.py.

### Security
- No new external inputs.
- All SQL uses parameterised queries (`?` placeholders). Only one string-interpolation site: `_RESOLVED_FILTER.replace("e.", "t.")` inside `tests_for_package` — interpolating a module-private constant whose content is fixed at module-import time, no user input flows in. Safe.

### Code Quality
- `_DOMAIN_DESCENDANTS_CTE` is a single-source-of-truth module constant reused by 3 helpers — good DRY.
- `_load_entry_point_description` / `_load_suite_description` are private projectors reused across describe_* / list_* / *_for_* helpers — keeps SQL projection in one place.
- `_list_by_kind` thin wrapper removes duplication across the 5 single-kind list helpers.
- Frozen dataclasses + `field(default_factory=list)` preserves positional construction for `PackageDescription` (D-01).
- `list_scripts` uses `UNION` (not `UNION ALL`) — documented intent.
- `tests_for_domain` two-branch `UNION` is documented with reference to Phase 31 D-12/D-13.

### Test Coverage
- 48 net-new test functions/parametrizations across Waves 0/1/2.
- Each describe_* / list_* / bubble-up helper has a paired empty-DB `_returns_empty_on_empty_db` (or `_returns_none_on_missing`) variant.
- `test_cte_cycle_safe` is paranoid defence-in-depth — uses `signal.alarm(5)` to assert non-hang behaviour on an injected cycle.
- 295/295 graph-io tests pass (1 graceful skip — `test_domain_depends_on_no_self_loop` documents the empty-state for the depends_on case).
- 4 new Phase 32 dataclasses verified for frozen-ness via `dataclasses.FrozenInstanceError` catch.

### Architecture
- Read-only contract preserved: `grep -nE 'INSERT |UPDATE |DELETE FROM|CREATE |DROP ' packages/graph-io/src/graph_io/queries.py` returns 0 new mutations (D-16).
- Lowercase node kinds used throughout (D-19 / RESEARCH §1): `grep -nE "kind='[A-Z]"` returns 0.
- `src`/`dst` edge columns used throughout (no `parent_id`/`child_id`): `grep -nE "parent_id|child_id"` returns 0.

### Performance
- `cross_cutting_packages` makes one query per zero-domain package via `describe_package` — N+1 pattern but bounded by the fixture's package count and not exercised in hot paths.
- `tests_for_domain` recursive CTE is bounded by Phase 31's domain DAG depth — sample fixture has 3 domains.

## Conclusion

The phase delivers all 16 helpers specified in the CONTEXT.md `<domain>` paragraph 4 (4 describe_* + 6 list_* + 2 *_for_package + 4 domain helpers), backed by 48 net-new tests and a back-filled sample_monorepo fixture. All plan deviations were emitter-vs-plan reconciliations (Rule 1 bugs), each documented in the corresponding SUMMARY.md. No blocking issues found.
