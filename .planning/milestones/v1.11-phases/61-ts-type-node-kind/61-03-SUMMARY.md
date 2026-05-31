---
phase: 61
plan: "03"
subsystem: source-parser
tags: [typescript, type-fixtures, graph-io-resolve-test, mono-repo-verification, export-type-fix]
dependency_graph:
  requires: [61-01, 61-02]
  provides: [ts-type-fixtures-focused, graph-io-type-resolve-test, export-type-reexport-fix]
  affects: [source_parser.parsers._generic, source_parser.fixtures.typescript, graph_io.tests.test_resolve, graph_io.tests.test_queries]
tech_stack:
  added: []
  patterns: [fixture-driven-tests, parametrized-graph-projection-tests]
key_files:
  created:
    - packages/source-parser/fixtures/typescript/bare_interface.ts
    - packages/source-parser/fixtures/typescript/bare_interface.expected.json
    - packages/source-parser/fixtures/typescript/exported_interface.ts
    - packages/source-parser/fixtures/typescript/exported_interface.expected.json
    - packages/source-parser/fixtures/typescript/exported_interface.graph.expected.json
    - packages/source-parser/fixtures/typescript/type_alias_bare.ts
    - packages/source-parser/fixtures/typescript/type_alias_bare.expected.json
    - packages/source-parser/fixtures/typescript/exported_type_alias.ts
    - packages/source-parser/fixtures/typescript/exported_type_alias.expected.json
    - packages/source-parser/fixtures/typescript/exported_type_alias.graph.expected.json
    - packages/source-parser/fixtures/typescript/bare_enum.ts
    - packages/source-parser/fixtures/typescript/bare_enum.expected.json
    - packages/source-parser/fixtures/typescript/exported_enum.ts
    - packages/source-parser/fixtures/typescript/exported_enum.expected.json
    - packages/source-parser/fixtures/typescript/exported_enum.graph.expected.json
    - packages/source-parser/fixtures/typescript/type_reexport.ts
    - packages/source-parser/fixtures/typescript/type_reexport.expected.json
    - packages/source-parser/fixtures/typescript/type_reexport.graph.expected.json
  modified:
    - packages/source-parser/tests/test_projection_graph.py
    - packages/source-parser/src/source_parser/parsers/_generic.py
    - packages/graph-io/tests/test_resolve.py
    - packages/graph-io/tests/test_queries.py
decisions:
  - "export type { X } from 'module' stamps symbol_kind=type on re-exports — detects `type` keyword child of export_statement"
  - "APIGatewayProxyEvent shows as kind=type (not function) in rebuilt graph; ts_kind absent because declaration is in node_modules (intentionally skipped)"
metrics:
  duration: "~60 minutes"
  completed: "2026-05-31"
  tasks_completed: 4
  files_changed: 22
---

# Phase 61 Plan 03: tests + fixtures + mono-repo-live verification Summary

**One-liner:** Focused TS type fixtures (bare/exported interface, type-alias, enum), graph-io cross-kind resolve tests for type, and `export type { X }` re-export fix that makes APIGatewayProxyEvent appear as kind=type in the rebuilt mono-repo-live graph.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Confirmed fixture conventions — existing parametrized harness; no new scaffolding needed | (read-only) |
| 2 | Add focused TS type fixtures + type_reexport fixture | e28792b, 086fbd4 |
| 3 | graph-io cross-kind resolve test for type + _VALID_KINDS assertion | 67d3262 |
| 4 | Both package suites green; mono-repo-live rebuilt; APIGatewayProxyEvent = kind=type | 086fbd4 |

## What Was Built

### Task 1: Fixture Convention Confirmed
- `_fixture_loader.py` automatically discovers `fixtures/typescript/*.ts` with paired `*.expected.json`
- `test_projection_graph.py` uses a manual `GRAPH_FIXTURES` list for graph projection tests (explicit opt-in)
- No new test scaffolding needed; new fixtures slot into the existing harness automatically

### Task 2: Focused TypeScript Type Fixtures
Added 6 focused, single-declaration fixture files:

| Fixture | Declaration | ts_kind | Exports edge |
|---------|------------|---------|--------------|
| `bare_interface.ts` | `interface IFoo` | interface | none |
| `exported_interface.ts` | `export interface IBar` | interface | dst kind=type |
| `type_alias_bare.ts` | `type MyAlias = string` | type_alias | none |
| `exported_type_alias.ts` | `export type MyId = number` | type_alias | dst kind=type |
| `bare_enum.ts` | `enum Direction` | enum | none |
| `exported_enum.ts` | `export enum Role` | enum | dst kind=type |

Each has a paired `*.expected.json` (parser tree); exported variants also have `*.graph.expected.json` (projection output). Added `exported_interface`, `exported_type_alias`, `exported_enum`, and `type_reexport` to `GRAPH_FIXTURES` in `test_projection_graph.py`.

Also added `type_reexport.ts` (`export type { APIGatewayProxyEvent } from 'aws-lambda'`) fixture as part of the auto-fix below.

### Task 3: graph-io Resolve Tests for Type
Added to `tests/test_resolve.py`:
- `test_sweep_type_placeholder_resolves_to_real_type_node`: seeds a real `type` node and a `type` placeholder export edge; after sweep, edge repoints to real node with `resolution="exact"`
- `test_sweep_function_placeholder_resolves_to_type_node_cross_kind`: bare re-export placeholder (kind=function) resolves to lone real `type` node via cross-kind single-candidate fallback

Added to `tests/test_queries.py`:
- `test_valid_kinds_includes_type`: asserts `"type" in queries._VALID_KINDS`; `find(kind="type")` does not raise ValueError

### Task 4: Verification
- `source-parser`: 92 tests pass (+11 new)
- `graph-io`: 511 tests pass, 3 skipped, 1 xfailed (+3 new)
- Mono-repo-live full rebuild: 6106 nodes, `APIGatewayProxyEvent` = `kind='type'` (verified with direct sqlite3 query)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `export type { X }` re-exports not stamping symbol_kind="type"**
- **Found during:** Task 4 — mono-repo-live verification
- **Issue:** After full rebuild, `APIGatewayProxyEvent` appeared as BOTH `kind='function'` (from the bare re-export path) and `kind='type'`. Investigation revealed that `export type { X } from 'module'` — TypeScript's explicit type-only re-export syntax — was not being detected. The `type` keyword child of `export_statement` indicates all re-exported names are types, but `_extract_exports` fell through to the bare `walk()` which assigns no `symbol_kind`.
- **Fix:** In `_extract_exports`, detect the `type` keyword child of `export_statement` when `config.type_types` is non-empty (TypeScript only). Pass `symbol_kind="type"` through the walk() fallback path for these re-exports.
- **Files modified:** `packages/source-parser/src/source_parser/parsers/_generic.py`
- **Commit:** 086fbd4

### Partial Success: ts_kind on APIGatewayProxyEvent
- **Expected:** `APIGatewayProxyEvent` has `kind=type`, `ts_kind=interface`
- **Actual:** `APIGatewayProxyEvent` has `kind=type`, no `ts_kind` (attrs=None)
- **Reason:** The real `interface APIGatewayProxyEvent` declaration lives in `node_modules/@types/aws-lambda`. Since `node_modules` is in `skip_dirs`, it is never parsed — the node is a placeholder (path=None) created from the export edge. Placeholders cannot carry `ts_kind` since that attribute is set only by the parser when it processes the actual declaration node.
- **Impact:** The critical fix IS working: `APIGatewayProxyEvent` is `kind='type'`, NOT `kind='function'`. Local project interfaces/types (e.g., `ActiveWindowApp`, `ActivityCardProps`) correctly have `ts_kind=interface`. Only externally-sourced types imported from `node_modules` lack `ts_kind`.
- **Assessment:** Not a bug — this is expected behavior for types declared in skipped directories.

## Test Results

- **source-parser before:** 81 tests passing
- **source-parser after:** 92 tests passing (+11 new fixture tests)
- **graph-io before:** 508 passed, 3 skipped, 1 xfailed
- **graph-io after:** 511 passed, 3 skipped, 1 xfailed (+3 new tests)

## Mono-repo-live Verification

```
APIGatewayProxyEvent in rebuilt graph:
  kind='type', attrs=None   ← placeholder from export type { } re-export
  (NOT kind='function')     ← key improvement: no longer mislabeled function
```

Full rebuild command used (per plan note on repo≠workspace):
```python
update.run(
    Path.home() / 'Personal/mono-repo',
    workspace=Path.home() / 'Personal/graph-wiki/mono-repo-live',
    full=True
)
```

Note: The .graph-wiki/ directory in the workspace is an OLD folder structure; the current code uses `.graph/` (returned by `workspace_io.paths.graph_dir`). All queries ran against the correct path `~/.../mono-repo-live/.graph/code.db`.

## Known Stubs

None. All fixture expected.json files are authored from actual parser output and hand-verified.

## Threat Flags

None. Pure parser/test changes with no network, auth, or storage surface.

## Self-Check: PASSED

- [x] All 18 new fixture files created in `packages/source-parser/fixtures/typescript/`
- [x] `test_projection_graph.py` updated with 4 new entries in GRAPH_FIXTURES
- [x] `_generic.py` updated with `export type { }` detection fix
- [x] `test_resolve.py` has 2 new cross-kind type tests
- [x] `test_queries.py` has 1 new `_VALID_KINDS` includes type assertion
- [x] Task commits: e28792b, 67d3262, 086fbd4
- [x] `source-parser` suite: 92 passed
- [x] `graph-io` suite: 511 passed, 3 skipped, 1 xfailed
- [x] Mono-repo-live rebuilt: 6106 nodes, APIGatewayProxyEvent = kind=type
