---
phase: quick-260530-pk3
plan: "01"
subsystem: source-parser
tags: [tdd, bug-fix, tree-sitter, arrow-function, export, javascript, typescript]
dependency_graph:
  requires: []
  provides: [arrow-const-function-nodes, tightened-export-extraction]
  affects: [packages/source-parser/src/source_parser/parsers/_generic.py]
tech_stack:
  added: []
  patterns: [_arrow_consts_in helper, lexical_declaration traversal, has_lexical_decl guard]
key_files:
  created: []
  modified:
    - packages/source-parser/src/source_parser/parsers/_generic.py
    - packages/source-parser/tests/test_generic_walker.py
decisions:
  - Used option (b) for name resolution — build via arrow node, patch .name/.span from declarator — keeps _resolve_name unchanged
  - Emit declarator name for ALL variable_declarator children in export const (not just fn_expr), fixing re_export_source fixture regression
  - has_lexical_decl flag prevents broad walk() fallback only when a lexical/variable declaration was present; export { a, b } clause path unchanged
metrics:
  duration: ~8 minutes
  completed: "2026-05-31T00:30:38Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase quick-260530-pk3 Plan 01: Fix source-parser Arrow-Function Const Handling Summary

**One-liner:** Arrow-function and function-expression consts now produce named function nodes in `_generic.py` via a `_arrow_consts_in` helper, and `_extract_exports` no longer leaks param/body identifiers for `export const NAME = (a, b) => ...` patterns.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Add failing-first tests for arrow consts and export-param leakage | a090144 | test_generic_walker.py |
| 2 (GREEN) | Handle arrow/function-expression consts and tighten export-name extraction | 57201ae | _generic.py |

## What Was Built

**`_arrow_consts_in()` helper** (new, in `_generic.py`):
- Takes a `lexical_declaration` or `variable_declaration` tree-sitter node
- Iterates `variable_declarator` children; for each whose `value` child is in `config.function_types` (arrow_function, function_expression), builds a named SourceNode
- Name comes from the declarator's `name` field; span covers the full declaration (start_line on the `const` line)
- Uses `_build_function_node` on the arrow/fn-expr node so body/calls/nested containers are extracted correctly, then patches `.name` and `.span`

**`_walk_container` extensions**:
- Added branch for top-level `lexical_declaration`/`variable_declaration` calling `_arrow_consts_in`
- Added same branch inside the `export_types` peek loop for `export const NAME = () => {}`

**`_extract_exports` tightening**:
- Detects `lexical_declaration`/`variable_declaration` children of export_statement
- For these, emits only declarator `name` field text(s) — covers both fn/arrow and plain-value exports (e.g. `export const thing = 1`)
- Sets `has_lexical_decl = True` to prevent the broad `walk()` descendant-identifier fallback that was leaking param/body identifiers
- All other paths (direct `export function`, `export class`, `export { a, b }`) unchanged

## Test Results

- 5 new tests added (RED in Task 1, GREEN in Task 2)
- 73 pre-existing tests unchanged
- **78 total tests pass** — zero regressions across Python/JS/TS parsers and projection/fixture tests

## Deviations from Plan

**1. [Rule 1 - Bug] `re_export_source` fixture regression caught and fixed mid-task**
- **Found during:** Task 2 first-run (78-3=75 before fix: 2 fixture failures)
- **Issue:** Initial `_extract_exports` fix only emitted names for `variable_declarator` children where value was in `function_types` or value was None — missing the case `export const thing = 1` where value is a number literal
- **Fix:** Emit declarator name for ALL `variable_declarator` children regardless of value type; the `has_lexical_decl` flag already prevents the leaking broad walk() fallback
- **Files modified:** `_generic.py` (same file, same task — single commit)
- Corrected before Task 2 commit

## TDD Gate Compliance

- RED gate: `a090144` — `test(quick-260530-pk3): add failing-first tests...`
- GREEN gate: `57201ae` — `feat(quick-260530-pk3): handle arrow/function-expression consts...`

Both gates present. No REFACTOR needed — implementation is minimal and clean.

## Self-Check: PASSED

- `packages/source-parser/src/source_parser/parsers/_generic.py` — exists, modified
- `packages/source-parser/tests/test_generic_walker.py` — exists, 5 new tests appended
- Commit `a090144` — exists (Task 1 RED)
- Commit `57201ae` — exists (Task 2 GREEN)
- Full suite: 78 passed, 0 failed
