---
phase: 61-ts-type-node-kind
verified: 2026-05-30T00:00:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 61: TypeScript Type Node Kind Verification Report

**Phase Goal:** Surface TypeScript `interface` / `type alias` / `enum` declarations as a single new `type` node kind (sub-kind in the `ts_kind` attr) in source-parser + graph-io, fixing the projection bug that previously mislabeled exported types as `function`.
**Verified:** 2026-05-30T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TypeScript interface/type-alias/enum declarations emit `kind="type"` nodes with correct `ts_kind` attr | VERIFIED | `_build_type_node` in `_generic.py:154-171`; all 6 focused fixtures pass (`bare_interface`, `exported_interface`, `type_alias_bare`, `exported_type_alias`, `bare_enum`, `exported_enum`) |
| 2 | Exported type declarations produce `exports` edges whose dst kind is `type`, not `function` | VERIFIED | `graph.py:87` uses `ref.attrs.get("symbol_kind", "function")` for export dst; graph fixtures `exported_interface.graph.expected.json`, `exported_type_alias.graph.expected.json`, `exported_enum.graph.expected.json` all show `dst[0]="type"` |
| 3 | `export type { X }` re-export syntax stamps `symbol_kind="type"` on re-exported names | VERIFIED | `_generic.py:362-366,414` detects `type` keyword child; `type_reexport` fixture passes with `attrs={"symbol_kind": "type"}` |
| 4 | `cg find --kind type` does not raise ValueError | VERIFIED | `"type"` added to `_VALID_KINDS` in `queries.py:29`; `test_valid_kinds_includes_type` passes |
| 5 | A `type` placeholder export-edge resolves to a real `type` node via cross-kind sweep | VERIFIED | `_CROSS_KIND_RESOLVABLE` includes `"type"` (`resolve.py:22`); SQL at line 180 includes `'type'`; `test_sweep_type_placeholder_resolves_to_real_type_node` passes |
| 6 | A bare re-export placeholder (kind=function) resolves to a lone real `type` node via cross-kind fallback | VERIFIED | `test_sweep_function_placeholder_resolves_to_type_node_cross_kind` passes |
| 7 | DERIVER_VERSION bumped to 5; SCHEMA_VERSION unchanged at 2 | VERIFIED | `schema.py:13,16`: `SCHEMA_VERSION=2`, `DERIVER_VERSION=5` |
| 8 | Class and function extraction behavior is unchanged (no regression) | VERIFIED | `class` extracts as `kind="class"`, `function` as `kind="function"` in live parser probes; 92 source-parser tests pass including all existing class/function fixture tests |

**Score:** 8/8 truths verified

### Known Deviation Assessment

**APIGatewayProxyEvent has `kind=type` but no `ts_kind` in the rebuilt mono-repo-live graph.**

The SUMMARY documents this: `APIGatewayProxyEvent`'s real `interface` declaration lives in `node_modules/@types/aws-lambda`, which is in `skip_dirs` and is never parsed. The graph node is a placeholder created from the `export type { APIGatewayProxyEvent }` re-export edge — a path=None node that cannot carry `ts_kind` because `ts_kind` is only set by the parser when it processes the actual declaration.

Assessment: **This satisfies the phase goal.** The goal's core requirement is that exported types are NOT mislabeled as `function`. The rebuilt graph shows `kind='type'` (not `kind='function'`), which is the primary correction. The `ts_kind` attribute requires an in-tree declaration; types sourced from `node_modules` are correctly excluded from parsing by design. Local in-tree types (e.g. `ActiveWindowApp`, `ActivityCardProps`) carry `ts_kind=interface` as expected. No deviation is required from the phase goal.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/source-parser/src/source_parser/parsers/_config.py` | `type_types: frozenset[str] = frozenset()` field on `LanguageConfig` | VERIFIED | Field present at line 24 with docstring |
| `packages/source-parser/src/source_parser/parsers/typescript.py` | `TYPESCRIPT_CONFIG` sets `type_types` to `{interface_declaration, type_alias_declaration, enum_declaration}` | VERIFIED | Line 21: `type_types=frozenset({"interface_declaration", "type_alias_declaration", "enum_declaration"})` |
| `packages/source-parser/src/source_parser/parsers/_generic.py` | `_ts_kind_for`, `_build_type_node`, `_walk_container` type branch, `_extract_exports` symbol_kind threading, `export type { X }` detection | VERIFIED | All present at lines 143-151, 154-171, 289-290, 311-312, 362-366, 404-408, 414 |
| `packages/source-parser/src/source_parser/projections/graph.py` | `exports` dst uses `symbol_kind` not hardcoded `function` | VERIFIED | Line 87: `dst=(ref.attrs.get("symbol_kind", "function"), ref.target_name, None)` |
| `packages/graph-io/src/graph_io/resolve.py` | `_CROSS_KIND_RESOLVABLE` includes `type`; SQL includes `'type'` | VERIFIED | Line 22 (Python set), line 180 (SQL) |
| `packages/graph-io/src/graph_io/schema.py` | `DERIVER_VERSION=5`, `SCHEMA_VERSION=2` | VERIFIED | Lines 13 and 16 |
| `packages/graph-io/src/graph_io/queries.py` | `"type"` in `_VALID_KINDS` | VERIFIED | Line 29, with Phase 61 comment |
| `packages/source-parser/fixtures/typescript/bare_interface.*` | Bare interface fixture with paired expected.json | VERIFIED | Files exist; `kind="type"`, `ts_kind="interface"` |
| `packages/source-parser/fixtures/typescript/exported_interface.*` | Exported interface fixture with parser + graph expected.json | VERIFIED | Files exist; exports edge `dst[0]="type"` |
| `packages/source-parser/fixtures/typescript/type_alias_bare.*` | Bare type alias fixture | VERIFIED | Files exist; `ts_kind="type_alias"` |
| `packages/source-parser/fixtures/typescript/exported_type_alias.*` | Exported type alias with graph fixture | VERIFIED | Files exist; exports edge `dst[0]="type"` |
| `packages/source-parser/fixtures/typescript/bare_enum.*` | Bare enum fixture | VERIFIED | Files exist; `ts_kind="enum"` |
| `packages/source-parser/fixtures/typescript/exported_enum.*` | Exported enum with graph fixture | VERIFIED | Files exist; exports edge `dst[0]="type"` |
| `packages/source-parser/fixtures/typescript/type_reexport.*` | `export type { X }` re-export fixture | VERIFIED | Files exist; `attrs={"symbol_kind": "type"}` |
| `packages/graph-io/tests/test_resolve.py` | Two new cross-kind resolution tests for `type` | VERIFIED | `test_sweep_type_placeholder_resolves_to_real_type_node` and `test_sweep_function_placeholder_resolves_to_type_node_cross_kind` |
| `packages/graph-io/tests/test_queries.py` | `_VALID_KINDS` assertion for `type` | VERIFIED | `test_valid_kinds_includes_type` at line 1154 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `TYPESCRIPT_CONFIG.type_types` | `_walk_container` | `child.type in config.type_types` | VERIFIED | `_generic.py:289`; emit branch fires for all 3 declared types |
| `_walk_container` export peek | `_build_type_node` | `inner.type in config.type_types` | VERIFIED | `_generic.py:311-312`; `export interface` / `export type` / `export enum` emit type node |
| `_extract_exports` | `Reference.attrs["symbol_kind"]` | Declaration-kind detection | VERIFIED | `_generic.py:394-408`; class→class, function→function, type→type |
| `_extract_exports` | `Reference.attrs["symbol_kind"]` | `export type { X }` detection | VERIFIED | `_generic.py:362-366,414`; `is_type_reexport` → `reexport_kind="type"` |
| `to_graph_records` export branch | `GraphEdge.dst[0]` | `ref.attrs.get("symbol_kind", "function")` | VERIFIED | `graph.py:87`; tested by `exported_interface.graph.expected.json` |
| `_CROSS_KIND_RESOLVABLE` | `resolve.sweep` SQL | `"type" in _CROSS_KIND_RESOLVABLE` + SQL `kind IN (...)` | VERIFIED | `resolve.py:22,180`; both the Python set and SQL include `type` |
| `_VALID_KINDS` | `queries.find()` | kind allowlist check | VERIFIED | `queries.py:29`; `find(kind="type")` does not raise |

### Data-Flow Trace (Level 4)

Phase 61 does not produce components that render dynamic data — it modifies a parser library and a graph-io library. Data-flow trace not applicable.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Bare `interface Foo {}` → `kind="type"`, `ts_kind="interface"` | `uv run python -c "... TypeScriptParser().parse(...)"` | kind=type, ts_kind=interface | PASS |
| `export interface Bar {}` → type node + exports edge dst kind=type | Live parser probe | Exports ref carries `symbol_kind="type"`; graph projection dst[0]="type" | PASS |
| `type Bar = string` → `ts_kind="type_alias"` | Live parser probe | ts_kind=type_alias | PASS |
| `enum E { A }` → `ts_kind="enum"` | Live parser probe | ts_kind=enum | PASS |
| `export type { X }` → `symbol_kind="type"` on re-export | Live parser probe | attrs={"symbol_kind": "type"} | PASS |
| `export { foo }` bare re-export → no `symbol_kind` | Live parser probe | attrs={} (no symbol_kind) | PASS |
| `find(kind="type")` does not raise | Live import probe | Returns [] without ValueError | PASS |
| `"type" in _CROSS_KIND_RESOLVABLE` | Live import probe | True | PASS |
| `DERIVER_VERSION == 5` | Live import probe | 5 | PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` files declared or exist for this phase. Step 7c: SKIPPED (no probes defined).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REQ-01 | 61-01 | `LanguageConfig.type_types` field; TS config set, JS config empty | SATISFIED | `_config.py:24`; `typescript.py:21`; JS config leaves default `frozenset()` |
| REQ-02 | 61-01 | interface/type-alias/enum (bare + exported) emit `kind="type"` with correct `ts_kind` | SATISFIED | `_generic.py:289-290,311-312,154-171`; 7 parser fixtures verify all variants |
| REQ-03 | 61-01 | Export References carry `symbol_kind`; projection `exports` dst uses it; `calls` unchanged | SATISFIED | `_generic.py:394-408,362-366,414`; `graph.py:65-91`; spot-checks and fixture tests |
| REQ-04 | 61-02 | `_CROSS_KIND_RESOLVABLE` and SQL both include `type` | SATISFIED | `resolve.py:22,180`; confirmed via import probe |
| REQ-05 | 61-02 | `DERIVER_VERSION` bumped 4→5; `SCHEMA_VERSION` unchanged | SATISFIED | `schema.py:13,16` |
| REQ-06 | 61-02/61-03 | `type` in `queries._VALID_KINDS`; `cg find --kind type` does not raise | SATISFIED | `queries.py:29`; `test_valid_kinds_includes_type` passes |
| REQ-07 | 61-03 | source-parser fixture-driven TS tests covering bare/exported interface, type-alias, enum (parametrized) | SATISFIED | 7 parser fixtures + 4 graph projection fixtures; 11 new parametrized test cases green |
| REQ-08 | 61-03 | graph-io resolve test for `type` cross-kind fallback | SATISFIED | `test_resolve.py`: 2 new tests (exact type→type and cross-kind function→type); both pass |

Note: REQ-08 in 61-03 also covers the mono-repo-live verification. The SUMMARY documents a full rebuild was performed with `update.run(..., full=True)` and `APIGatewayProxyEvent` confirmed as `kind='type'` in the rebuilt graph. The ts_kind-absent deviation for node_modules types is assessed as non-blocking (see Known Deviation Assessment above).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | No TBD/FIXME/XXX/TODO/HACK/placeholder markers in any modified file | — | — |

Review findings (from 61-REVIEW.md): 0 blockers, 3 warnings (WR-01 inline per-specifier `export { type Foo }` not detected; WR-02 `symbol_kind` attr now carried on all declaration export edges; WR-03 `has_declaration` guard semantics change), 3 info items. WR-02 confirmed harmless per problem statement: `symbol_kind` is only referenced within source-parser + graph-io; wiki-io (385) and workspace-io (87) suites pass without modification.

### Human Verification Required

None. All behavioral correctness is verifiable programmatically through the fixture-driven test suite and the parser spot-checks above. The mono-repo-live verification was performed by the executor with direct sqlite3 inspection of the rebuilt graph.

### Test Suite Results

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| source-parser | 81 passed | 92 passed | +11 new fixture tests |
| graph-io | 508 passed, 3 skipped, 1 xfailed | 511 passed, 3 skipped, 1 xfailed | +3 new tests |

Both suites green as of verification run (2026-05-30).

### Gaps Summary

No gaps. All 8 must-haves verified. Both package suites are green. All REQ-01 through REQ-08 are satisfied by implemented code confirmed against actual source files.

---

_Verified: 2026-05-30T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
