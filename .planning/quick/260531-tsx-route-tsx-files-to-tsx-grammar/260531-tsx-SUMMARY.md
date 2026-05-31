---
status: complete
phase: quick-260531-tsx
plan: "01"
subsystem: source-parser
tags: [tdd, bug-fix, tree-sitter, tsx, jsx, typescript]
dependency_graph:
  requires: []
  provides: [tsx-grammar-routing, jsx-component-extraction]
  affects:
    - packages/source-parser/src/source_parser/grammars.py
    - packages/source-parser/src/source_parser/parsers/typescript.py
tech_stack:
  added: [tsx tree-sitter grammar]
  patterns: [extension-based grammar selection, TSX_CONFIG via dataclasses.replace]
key_files:
  created: []
  modified:
    - packages/source-parser/src/source_parser/grammars.py
    - packages/source-parser/src/source_parser/parsers/typescript.py
    - packages/source-parser/tests/test_grammars.py
    - packages/source-parser/tests/test_parser_typescript.py
decisions:
  - Route only .tsx to the tsx grammar; .jsx is left on the javascript grammar (tree-sitter-javascript already handles JSX — verified has_error=False).
  - Keep logical `language` = "typescript" on emitted nodes so downstream consumers (graph-io) are unchanged; only the parse grammar differs.
  - Corrected the misleadingly-named test_typescript_loads_and_parses_tsx (it only checked root_node is not None, which is true even for error trees) into test_typescript_grammar_cannot_parse_jsx documenting the real limitation.
  - Executed directly in an isolated worktree (not via gsd-executor) per user instruction; branch left unmerged for later manual merge.
  - STATE.md intentionally not modified to avoid merge conflicts with the concurrently-changing main; tracking lives on the branch.
metrics:
  completed: "2026-05-31"
  tasks_completed: 1
  files_modified: 4
---

# Quick Task 260531-tsx: Route .tsx files to the tsx grammar — Summary

**One-liner:** `.tsx` files now parse with the JSX-capable `tsx` tree-sitter grammar instead of the JSX-blind `typescript` grammar, so React component definitions are extracted instead of being dropped as pathless stubs.

## Root cause

`TypeScriptParser.parse` used `generic_walk(TYPESCRIPT_CONFIG, ...)` with `grammar_name="typescript"` for every extension. The `typescript` grammar has no JSX support (that lives in the separate `tsx` grammar), so `.tsx` files produced error-laden trees: exported `function`/`const` component declarations were shredded into loose tokens and dropped, while nested arrow-consts were ejected to file scope. Those dropped definitions then appeared only as pathless `function`/`type` reference stubs created from `.ts` barrel `export { X } from "./X"` edges.

## Change

| File | Change |
|------|--------|
| `grammars.py` | Add `"tsx"` to `_KNOWN`. |
| `parsers/typescript.py` | Add `TSX_CONFIG = replace(TYPESCRIPT_CONFIG, grammar_name="tsx")`; route `.tsx` → `TSX_CONFIG`, `.ts` → `TYPESCRIPT_CONFIG`. |
| `tests/test_grammars.py` | `test_tsx_grammar_parses_jsx_without_errors`; corrected `test_typescript_grammar_cannot_parse_jsx`. |
| `tests/test_parser_typescript.py` | `test_tsx_jsx_component_emits_exported_function`; `test_ts_file_still_uses_plain_typescript_grammar`. |

Commit: `1007ef0`.

## Verification

- `pytest packages/source-parser` → 95 passed (baseline 92 + 3 net new).
- `pytest packages/source-parser packages/graph-io` → 606 passed, 3 skipped, 1 xfailed.
- Real mono-repo `.tsx`: `BottomSheet`, `ActivityCard`, `Card` now emitted with export refs and no parse errors; **220/222 (99%)** `.tsx` files parse error-free (was 8/222).
- Full workspace suite: 1659 passed, 7 failed — the 7 failures (`model-adapter`/`eval-harness` `models.toml` role config) are **pre-existing on the base** (reproduced with this change stashed), unrelated to the grammar fix.

## Follow-ups (not in this task)

- A full graph rebuild against the mono-repo workspace is needed to realize the node-count improvement (the live `.graph/code.db` was intentionally not rebuilt). Expect the ~989 path/uri-less nodes to drop toward the external-reference floor.
- Two `.tsx` files still have localized in-body JSX parse errors under the `tsx` grammar (`matcher-editor-modal.tsx`, `web-next-ts/page.tsx`) but still emit all top-level definitions — minor grammar-version tail, not a declaration drop.
- Remaining non-tsx contributors to pathless nodes (value-const exports not modeled; resolver kind-key miss; external refs) are separate from this fix.
