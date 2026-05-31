---
status: complete
phase: quick-260531-tsx
subsystem: source-parser
tags: [bug-fix, tree-sitter, tsx, jsx, typescript]
---

# Quick Task 260531-tsx: Route .tsx files to the tsx grammar

## Problem

`TypeScriptParser` parses both `.ts` and `.tsx` with the plain `typescript`
tree-sitter grammar, which cannot parse JSX. On the mono-repo this corrupts
214/222 (96%) of `.tsx` files into error-laden trees that drop most React
component definitions — the dominant root cause of graph nodes with no
path/uri (they survive only as pathless reference stubs from barrel
re-exports).

## Plan

1. (RED) Tests: `tsx` grammar parses JSX without errors; the `typescript`
   grammar cannot; a JSX component with a nested arrow const must yield the
   exported function with the const nested (not hoisted). `.ts` unaffected.
2. (GREEN) Register `tsx` in `grammars.py` `_KNOWN`; route `.tsx` to a
   `TSX_CONFIG` (grammar_name="tsx") in `TypeScriptParser.parse`; keep `.ts`
   on the `typescript` grammar and the logical `language` as "typescript".

## Verify

- `pytest packages/source-parser packages/graph-io` green.
- Real mono-repo `.tsx`: previously-dropped components emitted; 220/222 (99%)
  parse error-free.
