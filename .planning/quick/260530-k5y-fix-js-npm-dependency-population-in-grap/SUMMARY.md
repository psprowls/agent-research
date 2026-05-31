---
status: complete
phase: quick-260530-k5y
plan: "01"
one_liner: "JS npm dependency emission in graph_io refresh() — npm nodes, used_by edges, dev marker, internal workspace routing, DERIVER_VERSION=3"
subsystem: graph-io
tags: [graph-io, packages, npm, javascript, dependencies, tdd]
dependency_graph:
  requires: [260530-gqp]
  provides: [npm-dependency-nodes, used_by-edges-js, dev-marker, depends_on-package-js]
  affects: [graph-io.packages, graph-io.schema]
tech_stack:
  added: []
  patterns:
    - "dep_specs dict in _read_package_json: name->raw-spec with runtime-wins semantics"
    - "is_dev flag threaded through used_by_pairs tuple (extended to 5-tuple)"
    - "JS dep collection branch mirrors Python branch feeding same shared accumulators"
    - "used_by edge attrs: {} for runtime, {dev: True} for dev-only JS deps"
key_files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/packages.py
    - packages/graph-io/src/graph_io/schema.py
    - packages/graph-io/tests/test_packages.py
decisions:
  - "dev marker on used_by edges: omit key for non-dev (attrs={} preserved for Python compatibility), add dev=True only for dev-origin JS deps — keeps all existing Python assertions green"
  - "_runtime_dep_names added to _read_package_json return dict so refresh() can compute is_dev without re-parsing the raw JSON"
  - "runtime-wins for dep_specs: dev entries written first, then runtime entries overwrite on collision — consistent with existing dev_dependencies semantics (raw devDeps keys, not filtered)"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-30"
  tasks_completed: 3
  files_modified: 3
---

# Quick 260530-k5y: Fix JS/npm Dependency Population in graph_io Summary

JS dependency nodes and edges were completely absent from graph topology because
`packages.refresh()` gated the entire dependency-accumulation block on
`if info["language"] == "python":`. This fix threads JS manifests through the
shared `dep_acc` / `used_by_pairs` / `internal_pkg_edges` accumulators with
ecosystem `npm`, populated `versions_in_use`, and a `dev` marker on edges from
`devDependencies`-only deps.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| T1 RED | Failing tests for _read_package_json dep_specs | 31d20e3 | test_packages.py |
| T1 GREEN | Add dep_specs name->spec map to _read_package_json | c4e0b82 | packages.py, test_packages.py |
| T2 RED | Failing tests for JS npm dependency emission | 213ba16 | test_packages.py |
| T2 GREEN | Run npm dep emission for JS; bump DERIVER_VERSION=3 | 54ac4fe | packages.py, schema.py |
| T3 | JS npm dependency-parity integration tests | f70fd22 | test_packages.py |

## What Was Built

**`_read_package_json` changes (packages.py):**
- Added `dep_specs: dict[str, str]` — maps each declared dep name (runtime + dev) to its raw version-spec string; runtime entries overwrite dev entries on name collision (runtime wins)
- Added `_runtime_dep_names: set[str]` — the set of names from `dependencies` map, used by `refresh()` to compute `is_dev` without re-parsing JSON
- All existing fields (`dependencies`, `dev_dependencies`, shape) unchanged

**`refresh()` changes (packages.py):**
- Extracted consumer variables (`consumer_name`, `consumer_rel_path`, `consumer_kind`, `consumer_norm`) before the language branch
- Extended `used_by_pairs` tuple to 5-element form: `(consumer_name, consumer_rel_path, consumer_kind, dep_name, is_dev: bool)`
- Python branch: identical behavior; passes `is_dev=False` to all `used_by_pairs` entries
- Added JavaScript branch: iterates `info["dep_specs"]`, routes workspace-matching names to `internal_pkg_edges` (existing CLASS-01 suppression), external names to `dep_acc` with key `("npm", dep_name)`, appends to `used_by_pairs` with `is_dev = dep_name in dev_set and dep_name not in runtime_set`
- Updated `used_by` edge emission to: emit `attrs={"dev": True}` for `is_dev=True`; `attrs={}` for `is_dev=False` (preserving Python edge byte-identity)

**`schema.py`:**
- `DERIVER_VERSION` bumped 2 → 3 (iqo mechanism triggers auto-rebuild on next `cg update`)

## Tests Added (8 new tests)

| Test | What it proves |
|------|---------------|
| `test_read_package_json_dep_specs_runtime_and_dev` | dep_specs covers all names; runtime version wins on collision |
| `test_read_package_json_dep_specs_empty_when_no_deps` | empty dict when no deps declared |
| `test_read_package_json_dep_specs_coerces_non_string_spec` | non-string specs coerced to "" |
| `test_js_runtime_dep_emits_npm_dependency_node` | runtime dep → npm dependency node + used_by edge + versions_in_use |
| `test_js_dev_dep_edge_carries_dev_marker` | dev-only dep → edge with dev=True; runtime dep → edge without |
| `test_js_internal_workspace_dep_becomes_depends_on_package` | internal workspace dep → depends_on_package, no dependency node |
| `test_js_npm_dependency_parity_full_monorepo` | comprehensive integration: full monorepo with runtime+dev+internal |
| `test_js_versions_in_use_aggregates_across_consumers` | multi-consumer version collection |

## Verification

```
uv run --package graph-io pytest packages/graph-io/tests/ -q
# 495 passed, 3 skipped, 1 xfailed (was 487 before this task)

grep -n 'DERIVER_VERSION' packages/graph-io/src/graph_io/schema.py
# 16: DERIVER_VERSION = 3
```

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed dev_dependencies test expectation for name collision case**
- Found during: Task 1 GREEN
- Issue: Test asserted `dev_dependencies == ["vitest"]` when `react` appeared in both maps, but the existing `dev_dependencies` field (GQP-01) stores ALL devDeps keys regardless of runtime overlap — so `react` also appears in dev_dependencies
- Fix: Updated test to assert `"vitest" in dev_dependencies` and `"react" in dev_dependencies` rather than exact equality, matching the existing field semantics
- Files modified: test_packages.py

**2. [Rule 2 - Missing critical field] Added `_runtime_dep_names` to `_read_package_json` return**
- Found during: Task 2 GREEN implementation
- Issue: `refresh()` needed the set of runtime-only dep names to compute `is_dev`, but `deps` (the raw map) was only available inside `_read_package_json`; the merged `info["dependencies"]` + `info["dev_dependencies"]` fields don't let you reconstruct it unambiguously when a name appears in both
- Fix: Added `_runtime_dep_names: set[str]` to the return dict (prefixed `_` to signal it's internal plumbing not for external consumers)
- Files modified: packages.py

## Known Stubs

None — all 4 success criteria fully implemented and verified.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. The T-k5y-01 threat (malformed package.json) is mitigated by the existing `isinstance(..., dict)` guards (carried through to `_runtime_dep_names` construction) and the non-string spec coercion in `dep_specs`. T-k5y-02 accepted as planned.

## Self-Check: PASSED

Files exist:
- packages/graph-io/src/graph_io/packages.py — FOUND
- packages/graph-io/src/graph_io/schema.py — FOUND
- packages/graph-io/tests/test_packages.py — FOUND

Commits exist:
- 31d20e3 — FOUND (test RED T1)
- c4e0b82 — FOUND (feat GREEN T1)
- 213ba16 — FOUND (test RED T2)
- 54ac4fe — FOUND (feat GREEN T2)
- f70fd22 — FOUND (feat T3)
