---
phase: 29-structural-nodes-containment-tree
plan: 01
subsystem: source-parser
tags: [tree-sitter, python-ast, source-parser, sparser-01]

requires:
  - phase: 28-schema-v2-uri-foundation
    provides: nodes.attrs_json carries SourceNode.attrs verbatim
provides:
  - PythonParser writes `_has_main_block` and `_has_importable_symbols` to every file-level SourceNode.attrs
  - Three new fixture pairs covering positive + negative SPARSER-01 detection
affects: [29-03, 29-04]

tech-stack:
  added: []
  patterns: ["Source-parser AST attrs prefixed with `_` signal graph-io internal consumption"]

key-files:
  created:
    - packages/source-parser/fixtures/python/has_main_block.py
    - packages/source-parser/fixtures/python/has_main_block.expected.json
    - packages/source-parser/fixtures/python/importable_symbols.py
    - packages/source-parser/fixtures/python/importable_symbols.expected.json
    - packages/source-parser/fixtures/python/no_main_no_exports.py
    - packages/source-parser/fixtures/python/no_main_no_exports.expected.json
  modified:
    - packages/source-parser/src/source_parser/parsers/python.py
    - packages/source-parser/fixtures/python/async_methods.expected.json
    - packages/source-parser/fixtures/python/basic_function.expected.json
    - packages/source-parser/fixtures/python/basic_function.graph.expected.json
    - packages/source-parser/fixtures/python/class_with_decorator.expected.json
    - packages/source-parser/fixtures/python/class_with_decorator.graph.expected.json
    - packages/source-parser/fixtures/python/class_with_init.expected.json
    - packages/source-parser/fixtures/python/import_variants.expected.json
    - packages/source-parser/fixtures/python/module_init.expected.json
    - packages/source-parser/fixtures/python/multiple_inheritance.expected.json

key-decisions:
  - "Attrs are unconditionally written (not gated on truthiness) so downstream consumers can rely on key existence in nodes.attrs_json"

patterns-established:
  - "Pattern: file-scope-only AST detection helpers iterate `file_root.children` (no recursive descent) for bounded cost"

requirements-completed:
  - SPARSER-01

duration: 8min
completed: 2026-05-26
---

# Phase 29 / Plan 01: SPARSER-01 — Python file role-flag attrs

**`PythonParser.parse` now writes `_has_main_block` and `_has_importable_symbols` on every file-level SourceNode, ready for `structural_nodes.emit` (Plan 03) to lift them onto File nodes as `has_main` / `is_importable`.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-05-26
- **Tasks:** 2 completed
- **Files modified:** 6 (1 source + 5 expected.json) + 6 new (3 fixture pairs)

## Accomplishments
- Two module-level helpers (`_has_main_block`, `_has_importable_symbols`) added to `python.py`, each iterating `file_root.children` (one level, bounded)
- Attrs unconditionally written inside `PythonParser.parse` immediately after the existing `parse_errors` injection (line ~318)
- Three new fixture pairs cover all detection paths (main block + public def, public-only, both-negative)
- All 7 pre-existing python fixture `.expected.json` files updated to carry the new attrs on `file_node.attrs`
- `_has_main_block.graph.expected.json` + `class_with_decorator.graph.expected.json` updated for the graph-projection test
- Full `source-parser` test suite green: 73/73 (was 70/70)

## Task Commits

1. **Task 1 + Task 2 combined: helpers + attr writes + fixtures + expected-json updates** — `4d95d07` (feat)

(Combined because the helpers without expected-json updates would have broken 7 unrelated parser tests; splitting the commit would have left the suite red.)

## Files Created/Modified

See `key-files` in frontmatter.

## Decisions Made

- **Unconditional attr writes (not gated on `if value`)** — keeping the keys present even when both are False simplifies the SQL read in Plan 03: `attrs.get("_has_main_block", False)` always returns a real boolean, never the falsy default of a missing key fed through `json_extract`.
- **`__all__` does not count as an importable symbol** — its name starts with `_`, so the assignment-path rule rejects it. This matches D-19's intent that `_has_importable_symbols` reflect "what `from pkg import *` would surface to user code".

## Deviations from Plan

### Auto-fixed Issues

**1. Plan 01 referenced wrong fixture path**
- **Found during:** Task 2 (fixture creation)
- **Issue:** Plan listed `packages/source-parser/tests/fixtures/python/*.json` but the actual fixtures live at `packages/source-parser/fixtures/python/*.expected.json` (no `tests/` prefix; `.expected.json` not `.json`).
- **Fix:** Used the actual on-disk paths; `_fixture_loader.FIXTURES_ROOT` resolves to `packages/source-parser/fixtures/`, and `expected_path_for(fixture)` adds the `.expected.json` suffix.
- **Files modified:** new files placed at `packages/source-parser/fixtures/python/<name>.{py,expected.json}`
- **Verification:** `pytest tests/test_parser_python.py -q` picks up new fixtures via `fixtures_for("python", (".py",))` and all three pass.
- **Committed in:** `4d95d07`

**2. Existing fixtures had to be updated for the new attrs**
- **Found during:** Task 1 (initial run after edit)
- **Issue:** `_fixture_loader.diff` compares full dicts — any extra key in actual is flagged. Writing the new attrs to `file_node.attrs` broke 7 unrelated parser fixture tests.
- **Fix:** Updated all 7 `.expected.json` files to include `attrs: {"_has_main_block": false, "_has_importable_symbols": <correct value>}` on the file node. Also updated 2 `.graph.expected.json` files used by `test_projection_graph`.
- **Verification:** Full `source-parser` suite green (73/73).
- **Committed in:** `4d95d07`

---

**Total deviations:** 2 auto-fixed (both path/scope adjustments needed for plan accuracy).
**Impact on plan:** No scope creep — all changes are mechanical updates required by the same code edit.

## Issues Encountered
None — the AST patterns specified in 29-PATTERNS.md applied verbatim once the fixture-path adjustments were resolved.

## User Setup Required
None.

## Next Phase Readiness
- Plan 03 (`structural_nodes.emit`) can read `_has_main_block` and `_has_importable_symbols` out of `nodes.attrs_json` for every Python File node and write them as `has_main` / `is_importable` per D-20
- Wave ordering D-21 (SPARSER-01 in Wave 1, structural_nodes.emit in Wave 2) honored — this commit lands strictly before Plan 03

---
*Phase: 29-structural-nodes-containment-tree*
*Completed: 2026-05-26*
