---
phase: 50-app-reclassification-graph-io
plan: "02"
subsystem: graph-io
tags: [app-kind, graph-io, emit-loop, kind-flip, in-place-update, downstream-broadening]
requires:
  - 50-01-app-schema-foundation
provides:
  - packages.refresh emits kind='app' nodes for manifests with app signals
  - D-06 in-place UPDATE preserves row id across pkg <-> app flips
  - contains/used_by/declares_entry_point/belongs_to_domain edges use new_kind
  - Downstream emitters (structural_nodes, entry_points, test_suites, builtins,
    domains, derived_edges, import_scan) all treat App nodes as
    manifest-defined nodes
affects:
  - update.run preservation set includes 'app'
  - describe_entry_point queries (queries.py + cli/q_describe_entry_point.py)
    accept apps as declarers
  - All graph-io tests still green; ROADMAP SC #1, #4 wired
tech-stack:
  added: []
  patterns:
    - "kind-flip in-place UPDATE (D-06) — probe other-kind row, UPDATE not INSERT"
    - "manifest-kind side-table (pkg_name_to_kind / pkg_kind_map) — every emitter that hard-coded ('package', ...) tuples now resolves the real kind from a SELECT-pass side table before emitting edges"
key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/packages.py
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/src/graph_io/structural_nodes.py
    - packages/graph-io/src/graph_io/entry_points.py
    - packages/graph-io/src/graph_io/test_suites.py
    - packages/graph-io/src/graph_io/builtins.py
    - packages/graph-io/src/graph_io/domains.py
    - packages/graph-io/src/graph_io/derived_edges.py
    - packages/graph-io/src/graph_io/import_scan.py
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/src/graph_io/cli/q_describe_entry_point.py
    - packages/graph-io/tests/test_packages.py
    - packages/graph-io/tests/test_cli_anti_regression.py
    - packages/graph-io/tests/test_entry_points.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/test_test_suites.py
key-decisions:
  - "D-04 invariant flows all the way through: every site that previously emitted src=('package', ...) or dst=('package', ...) now looks up the actual stored kind so edge upsert resolves to the existing row instead of an _ensure_node stub"
  - "Downstream broadening to `kind IN ('package', 'app')` is a Rule 1+4 deviation from the plan — Plan 02 stopped at the emit loop, but the schema flip would have silently broken every consumer that filtered on kind='package'. Broadening is unavoidable to keep the phase coherent (ROADMAP SC #1 'domain projections can treat apps distinctly' is now actually true; without these changes apps would silently vanish from domain projections)"
  - "Three-row-existence invariant: even with the D-06 in-place UPDATE in place, FOUR independent downstream code paths could still insert a stub kind='package' row via upsert._ensure_node when emitting an edge to/from a hard-coded ('package', name, path) tuple. All four were located and patched (structural_nodes pkg_key, structural_nodes parent_src for orphan files, test_suites parent_src for testroot owner, derived_edges references-edge dst)"
requirements-completed:
  - APP-01
  - APP-02
  - APP-06
duration: "28 min"
completed: "2026-05-28"
---

# Phase 50 Plan 02: classify() wired into refresh + D-06 kind-flip Summary

`packages.refresh` now calls `classify(info, pkg_dir)` inline for every discovered manifest, branches `kind`/`uri`/`attrs` based on the result, and emits an `App` node (with `app_kind` and `app_signals`) when any signal fires. The D-06 in-place UPDATE preserves the SQLite row id across cross-run kind flips so every inbound edge FK survives without edge-table mutation. The `contains` and Python `used_by` dep-edge emissions both pick up the new kind. Nine integration tests cover every documented signal mapping and the multi-signal precedence rule. **Additionally**, a wider downstream broadening was required to keep the phase coherent — see "Deviations" below.

## Execution Times

- Start: 2026-05-28T02:05:10Z
- End:   2026-05-28T02:33:18Z
- Duration: 28 min
- Tasks: 3 (planned) + 1 downstream broadening (Rule 1+4 deviation)
- Files touched: 16 (11 src modified + 5 tests modified)

## Task-by-Task

### Task 1: Wire classify() into refresh emit loop with branched kind/uri/attrs

- **Commit** 48dbbe4 — added `from graph_io.classification import classify` and `from graph_io.uri import app_uri, ...` imports; replaced the body of the manifest loop in `packages.refresh` with the D-04/D-07 inline call site; updated `used_by_pairs` tuple to carry `consumer_kind`; emitted edges from the new tuple shape.
- Existing 22 test_packages.py + 8 test_classification.py tests all pass without modification (30 passed).

### Task 2: D-06 in-place UPDATE for cross-run kind flips

- **RED commit** 473023a — added four kind-flip integration tests (pkg→app flip, app→pkg revert, inbound-edge FK preservation, zero-signal no-flip)
- **GREEN commit** 5fbbdbc — inside the manifest loop, after computing new_kind/new_uri/attrs and BEFORE constructing the GraphNode, probe `upsert._node_id(conn, (other_kind, name, path))`; if non-None, issue `UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?` with the attrs payload minus the `"uri"` key. All four tests pass.

### Task 3: JS-signal and multi-signal integration tests

- **Commit** 04be99e — nine new integration tests using `packages.refresh` end-to-end: bin string → cli, bin dict → cli, next dep → nextjs, expo dep → expo, vite+index.html → spa, vite without index.html → stays package, multi-signal (bin+next) → nextjs with sorted signals, Python pure library → stays package, json_extract probe of app_kind/app_signals visibility. All 35 test_packages.py tests pass.

### Deviation: Downstream broadening (Rule 1+4 — bug from architectural plan gap)

- **Commit** c902c74 — broadened every `kind='package'` filter and every hard-coded `("package", name, path)` edge tuple in graph-io to treat App nodes as manifest-defined nodes:
  - `update.py` — preserve set now `kind NOT IN ('package', 'app', 'builtin')`
  - `structural_nodes.py` — `pkg_rows` SELECT broadens to both kinds; `pkg_index` + `pkg_name_to_kind` side table built so `pkg_key` tuples resolve to the real stored kind for both file-parent edges and SubPackage parent edges
  - `entry_points.py` — `pkg_rows` SELECT broadens; `_emit_pyproject_entries` and `_emit_packagejson_entries` accept `pkg_kind` parameter and build `pkg_key = (pkg_kind, ...)` so `declares_entry_point` and `implemented_by` edges resolve correctly
  - `test_suites.py` — `pkg_rows` SELECT broadens; `pkg_kind_map` side table feeds both the tests-edge dst and the testroot-owner physically_contains parent
  - `builtins.py` — `pkg_rows` SELECT broadens; `pkg_kind_map` feeds the `used_by` edge src
  - `domains.py` — `_known_packages` returns kind tuple; `known_name_to_kind` map feeds `belongs_to_domain` edge src
  - `derived_edges.py` — `pkg_rows` SELECT broadens; queries broaden `pkg.kind` filter to IN clause; `pkg_key_to_kind` map feeds derived `references`-edge dst
  - `import_scan.py` — `pkg_rows` SELECT broadens
  - `queries.py` — `describe_entry_point` query broadens `pkg.kind` filter to IN
  - `cli/q_describe_entry_point.py` — bare entry-name lookup query broadens `pkg.kind`
- Tests updated: `test_cli_anti_regression` fixture loses `[project.scripts]` (so `sample-pkg` stays as a package, matching the `describe-package` target the test exercises); `test_entry_points._declares_edge_exists` helper accepts both kinds; `test_queries.test_seeded_db_fixture_audit` cross-cutting + multi-domain audits broaden; `test_test_suites.test_anti_regression_describe_package_smoke` smoke accepts mypkg as either kind (it's an app post-Phase-50 because the fixture has `[project.scripts]`).

## Verification Results

- `uv run --package graph-io pytest packages/graph-io/tests/ -q` → **439 passed, 1 skipped, 1 xfailed**
- `uv run pytest -q --ignore=packages/graph-io --ignore=tests/test_integration_gate.py` → **1060 passed, 38 skipped, 1 xfailed** (no new failures elsewhere in the workspace)
- Manual smoke against the `sample_monorepo` fixture: `mypkg` (which has `[project.scripts]`) emits as a single `kind='app'` row with `app_kind='cli'` and survives `update.run(full=True)` without StrictTreeInvariantError
- Acceptance criteria: `grep -nE "UPDATE nodes SET kind=\?, uri=\?, attrs_json=\? WHERE id=\?" packages/graph-io/src/graph_io/packages.py` → 1 match (the D-06 UPDATE); `grep -n "upsert._node_id" packages/graph-io/src/graph_io/packages.py` → 1 match (the D-06 probe); `grep -n "import json" packages/graph-io/src/graph_io/packages.py` → 1 match

## Deviations from Plan

### [Rule 1 + Rule 4 — Architectural gap in plan] Downstream broadening to accept App nodes

- **Found during:** Task 3 → full-suite verification revealed 8 distinct downstream test failures (`test_cli_anti_regression`, `test_cli_describe_entry_point`, `test_seeded_db_fixture_audit`, `test_call_order_pitfall`, `test_anti_regression_describe_package_smoke`, `test_pyproject_scripts_emits_entry_point`, plus implicit ones via the `sample_monorepo` fixture path)
- **Issue:** Plan 02 specified the emit-loop change but did not extend the work to the downstream emitters and query helpers that still filtered strictly on `kind='package'`. Every emitter that hard-coded `("package", name, path)` edge tuples was silently creating a stub `kind='package'` row via `upsert._ensure_node` because the real row was now `kind='app'`. Eight downstream emitters / query helpers needed the same broadening, plus `update.run`'s incremental-delete preservation set needed to include `'app'`.
- **Fix:** Broadened every `kind='package'` SELECT to `kind IN ('package', 'app')` in graph-io emitters; replaced every hard-coded `("package", name, path)` edge-tuple with a kind-resolved tuple via a side-table built during the SELECT pass. Detailed file list in the "Deviation: Downstream broadening" task block above.
- **Files modified:** `update.py`, `structural_nodes.py`, `entry_points.py`, `test_suites.py`, `builtins.py`, `domains.py`, `derived_edges.py`, `import_scan.py`, `queries.py`, `cli/q_describe_entry_point.py`; plus 4 test files
- **Verification:** 439-test graph-io baseline now fully green
- **Commit hash:** c902c74

**Total deviations:** 1 (Rule 1+4 hybrid — architectural gap in plan).
**Impact:** Substantial — 11 source files and 4 test files changed beyond the plan's stated scope. However, the change is the architecturally correct interpretation of the phase goal (ROADMAP SC #1: "domain projections can treat apps distinctly"). Without it, App reclassification would silently break domain projections rather than enable them.

## Key Decisions

- **D-04 invariant cascades through every edge tuple.** Even with the D-06 in-place UPDATE in place inside `packages.refresh`, four independent downstream code paths could still insert a stub `kind='package'` row via `upsert._ensure_node` when emitting an edge whose endpoint was a hard-coded `("package", name, path)` tuple. All four were located via a duplicate-`physically_contains` debug session and patched: `structural_nodes.pkg_key`, `structural_nodes.parent_src` (orphan-file branch), `test_suites.parent_src` (testroot owner), `derived_edges.references-edge dst`.
- **The `_MANIFEST_KINDS = ("package", "app")` constant lives in `derived_edges.py`** but is currently only consulted via SQL `kind IN ('package', 'app')` literals. Future Phase 51 cleanup can promote this to a shared module-level helper if more callers emerge.
- **Downstream broadening was the only coherent path forward** for Phase 50. The alternative (rolling back Plan 02) would have left the schema layer in a half-applied state. The alternative-2 (skipping the broadening) would have created a "silent demotion": an app would still appear in `cg list-packages` but would have no domain memberships, no entry points, no test coverage — and the fixture-audit tests would catch this in a follow-up phase rather than now.

## Self-Check: PASSED

- [x] All 3 tasks executed
- [x] Each task committed atomically (RED test commits + GREEN code commits)
- [x] Plan-level verification (`<verification>` block) all green
- [x] All `<acceptance_criteria>` from every task verified
- [x] No regressions in 439-test graph-io baseline
- [x] No regressions in 1060-test non-graph-io workspace baseline
- [x] SCHEMA_VERSION unchanged at 2 (D-12 honored)

## Issues Encountered

The deviation work surfaced an architectural impact the plan didn't anticipate. The deviation is documented above with full traceability (commit c902c74, 14 files). Future Phase 50/51 plans should explicitly include "downstream filter audit" as a phase task when introducing a new admitted kind.

## Next Phase Readiness

Plan 03 (query layer + CLI handlers + end-to-end integration) is unblocked. The schema layer is fully consistent: every emitter and downstream query honors the package/app distinction. Plan 03's `describe_app` query and the `cg list-apps` / `cg describe-app` CLI handlers can now build on a stable foundation.

Ready for `50-03`.
