---
phase: 61
plan: "01"
subsystem: source-parser
tags: [typescript, type-extraction, graph-projection, fixtures]
dependency_graph:
  requires: []
  provides: [LanguageConfig.type_types, _build_type_node, symbol_kind-in-exports]
  affects: [source_parser.parsers._generic, source_parser.projections.graph, source_parser.parsers.typescript]
tech_stack:
  added: []
  patterns: [config-driven-generic-walker, fixture-driven-tests]
key_files:
  created:
    - packages/source-parser/fixtures/typescript/type_declarations.ts
    - packages/source-parser/fixtures/typescript/type_declarations.expected.json
    - packages/source-parser/fixtures/typescript/type_exports.ts
    - packages/source-parser/fixtures/typescript/type_exports.expected.json
    - packages/source-parser/fixtures/typescript/type_exports.graph.expected.json
  modified:
    - packages/source-parser/src/source_parser/parsers/_config.py
    - packages/source-parser/src/source_parser/parsers/typescript.py
    - packages/source-parser/src/source_parser/parsers/_generic.py
    - packages/source-parser/src/source_parser/projections/graph.py
    - packages/source-parser/tests/test_projection_graph.py
    - packages/source-parser/fixtures/typescript/interface_call.expected.json
    - packages/source-parser/fixtures/typescript/interface_call.graph.expected.json
    - packages/source-parser/fixtures/typescript/default_export.expected.json
    - packages/source-parser/fixtures/typescript/re_export_source.expected.json
    - packages/source-parser/fixtures/javascript/default_export.expected.json
    - packages/source-parser/fixtures/javascript/esm_module.expected.json
    - packages/source-parser/fixtures/javascript/esm_module.graph.expected.json
decisions:
  - "type_types as frozenset field on LanguageConfig, following existing class_types/function_types pattern"
  - "symbol_kind only stamped on function-valued const exports (arrow/fn-expr), not plain const assignments"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-30"
  tasks_completed: 4
  files_changed: 13
---

# Phase 61 Plan 01: source-parser TS `type` extraction + projection export-kind fix Summary

**One-liner:** TypeScript interface/type-alias/enum declarations extracted as `kind='type'` nodes with `ts_kind` attr; export refs stamped with `symbol_kind`; graph projection exports edge uses `symbol_kind` for dst kind.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add `type_types` to LanguageConfig; TS config sets it; JS config leaves empty | f3a882e |
| 2 | Emit `type` nodes from generic walker (`_build_type_node`, `_ts_kind_for`, `_walk_container`) | e1c5740 |
| 3 | Thread `symbol_kind` through export References in `_extract_exports` | e789450 |
| 4 | Fix projection export-edge dst kind to use `symbol_kind`; add graph fixture | 51aa8df |

## What Was Built

### Task 1: `LanguageConfig.type_types` field
- Added `type_types: frozenset[str] = frozenset()` to `LanguageConfig` after `function_types`
- `TYPESCRIPT_CONFIG` sets it to `{"interface_declaration", "type_alias_declaration", "enum_declaration"}`
- `JAVASCRIPT_CONFIG` leaves it empty (JS has no types by design)

### Task 2: Generic walker emits `type` nodes
- `_ts_kind_for(node_type)` maps tree-sitter node type to `ts_kind` string: `interface_declaration` → `"interface"`, `type_alias_declaration` → `"type_alias"`, `enum_declaration` → `"enum"`
- `_build_type_node()` creates `SourceNode(kind="type", attrs={"ts_kind": ...})`
- `_walk_container` gains a `type_types` branch for bare declarations AND inside the `export_statement` peek for exported declarations
- Updated `interface_call` fixture: `IFoo` is now `kind='type'` not buried
- New fixtures: `type_declarations.ts` (bare interface/type-alias/enum) and `type_exports.ts` (exported variants)

### Task 3: `symbol_kind` on export References
- `_extract_exports` now distinguishes declaration exports by kind:
  - `config.class_types` → `symbol_kind="class"`
  - `config.function_types` → `symbol_kind="function"`
  - `config.type_types` → `symbol_kind="type"`
  - `lexical_declaration` with arrow/fn-expr value → `symbol_kind="function"`; plain const → no symbol_kind
  - Bare re-exports (`export { x }`) → no `symbol_kind` (unknown at parse time)
- Updated 6 existing fixture expected.json files to include `symbol_kind` on declared exports

### Task 4: Graph projection export-edge dst kind
- `graph.py` exports branch: `dst=("function", ...)` → `dst=(ref.attrs.get("symbol_kind", "function"), ...)`
- `calls` branch unchanged (hardcoded `"function"`)
- `_emit_node` already copies `dict(node.attrs)` so `ts_kind` flows to `GraphNode.attrs` automatically
- Added `type_exports.graph.expected.json` with `dst[0]="type"` on all 3 exports edges
- Added `type_exports.ts` to `GRAPH_FIXTURES` in `test_projection_graph.py`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plain const exports shouldn't get `symbol_kind="function"`**
- **Found during:** Task 3 implementation
- **Issue:** Initial implementation stamped ALL `lexical_declaration` exports as `symbol_kind="function"`. But `export const thing = 1` is not a function, so it should have no symbol_kind.
- **Fix:** Check `value.type in config.function_types` before stamping; plain const assignments get `symbol_kind=None` (omitted from attrs).
- **Files modified:** `packages/source-parser/src/source_parser/parsers/_generic.py`
- **Commit:** e789450

## Test Results

- **Before:** 78 tests passing
- **After:** 81 tests passing (+3 new fixture tests)
- All new fixtures are green under the parametrized `test_fixture` and `test_graph_projection` harnesses

## Known Stubs

None.

## Threat Flags

None. This is a pure parse/projection change with no network, auth, or storage surface.

## Self-Check: PASSED

- [x] `packages/source-parser/src/source_parser/parsers/_config.py` — modified (type_types field)
- [x] `packages/source-parser/src/source_parser/parsers/typescript.py` — modified (type_types set)
- [x] `packages/source-parser/src/source_parser/parsers/_generic.py` — modified (_build_type_node, _extract_exports)
- [x] `packages/source-parser/src/source_parser/projections/graph.py` — modified (exports dst kind)
- [x] All 4 task commits exist: f3a882e, e1c5740, e789450, 51aa8df
- [x] `uv run pytest -q` → 81 passed
