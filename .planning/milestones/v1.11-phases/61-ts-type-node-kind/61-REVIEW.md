---
phase: 61-ts-type-node-kind
reviewed: 2026-05-30T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - packages/graph-io/src/graph_io/queries.py
  - packages/graph-io/src/graph_io/resolve.py
  - packages/graph-io/src/graph_io/schema.py
  - packages/graph-io/tests/test_queries.py
  - packages/graph-io/tests/test_resolve.py
  - packages/source-parser/src/source_parser/parsers/_config.py
  - packages/source-parser/src/source_parser/parsers/_generic.py
  - packages/source-parser/src/source_parser/parsers/typescript.py
  - packages/source-parser/src/source_parser/projections/graph.py
  - packages/source-parser/tests/test_projection_graph.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 61: Code Review Report

**Reviewed:** 2026-05-30
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

This phase adds a TypeScript `type` node kind (interface / type-alias / enum) end to
end: a new `type_types` field on `LanguageConfig`, `_build_type_node` + `_ts_kind_for`
in the generic walker, `symbol_kind` threading through `_extract_exports`, a projection
change that maps `symbol_kind` to the export-edge dst kind, admission of `type` to
`_VALID_KINDS`, and extension of the cross-kind resolution fallback to include `type`.
`DERIVER_VERSION` is bumped 4 → 5 to force a rebuild.

The core implementation is sound and well-tested. The full source-parser suite (92
tests) and the graph-io resolve/queries suites (109 tests) pass. Node emission, enum
member non-leakage, exact/ambiguous cross-kind resolution of `type` placeholders, and
the `export type { ... }` re-export path all behave correctly under direct probing.

No correctness or security defects were found. The findings below are robustness and
maintainability gaps: an inline `type`-modifier parsing limitation, a graph-wide
attrs-shape change with cross-package consumer risk, an inconsistent anonymous-name
fallback, and a few minor quality items. None block shipping, but the consumer-side
attrs change (WR-02) should be confirmed before release.

## Warnings

### WR-01: Inline `type` modifier on named re-exports is not detected; symbol mis-kinded as `function`

**File:** `packages/source-parser/src/source_parser/parsers/_generic.py:358-422`
**Issue:** `is_type_reexport` only fires for the whole-statement form `export type { X }`
(a `type` keyword that is a *direct child* of the `export_statement`). The inline
per-specifier form `export { type Foo, bar }` is not recognized. Probing confirms
`export { type Foo, bar } from 'm'` emits both `Foo` and `bar` with no `symbol_kind`,
so the projection defaults both dst kinds to `function`:

```
export { type Foo, bar } from 'm';
  -> export ('function', 'Foo', None) {}    # Foo is actually a type
  -> export ('function', 'bar', None) {}
```

A `Foo` that is genuinely a `type` is therefore mis-kinded at the export edge. The
cross-kind sweep fallback (now including `type`) will still repoint the edge to a real
`type` node *when exactly one graph-wide candidate exists*, so this is partially
self-correcting — but it silently degrades to a wrong kind whenever a same-named
function/type pair exists (the edge then stays unresolved instead of pointing at the
type). This is an accepted v1 gap for the whole-statement form's sibling, but it is
undocumented.

**Fix:** Either detect the inline modifier (check each `export_specifier` child for a
leading `type` keyword and stamp that specifier `symbol_kind="type"`), or add an
explicit code comment + a fixture documenting that inline `type` modifiers are out of
scope for v1 so the limitation is intentional and discoverable:

```python
# NOTE (v1 limitation): inline per-specifier `export { type Foo, bar }` modifiers
# are NOT detected here — only the whole-statement `export type { ... }` form sets
# symbol_kind="type". Inline-modified type re-exports fall back to symbol_kind=None
# and rely on the single-candidate cross-kind sweep to repoint correctly.
```

### WR-02: Every export edge now carries a `symbol_kind` attr — graph-wide attrs-shape change with cross-package consumers

**File:** `packages/source-parser/src/source_parser/parsers/_generic.py:399-403,423-435` and `packages/source-parser/src/source_parser/projections/graph.py:87,89`
**Issue:** Previously `export function foo` produced an export ref with `attrs={}`. The
new code stamps `symbol_kind="function"` (and `"class"` / `"type"`) on declaration
exports, and the projection copies the full ref attrs onto the edge
(`attrs=dict(ref.attrs)`). The fixture diffs confirm the shift — e.g. JS
`esm_module.graph.expected.json` export edge changed from `attrs: {}` to
`attrs: {"symbol_kind": "function"}`. This is a graph-wide attrs change affecting
**JavaScript** too (not just TS), even though JS gains no new behavior. Any downstream
consumer that does exact-dict matching on export-edge attrs, snapshots them, or
persists them will see a diff. The dst-kind itself is unchanged for functions/classes
(the `.get(..., "function")` default already matched), so only the redundant attr is
new noise.

The `DERIVER_VERSION` bump (4 → 5) correctly forces a graph rebuild, which covers
graph-io's stored data. The risk is in *other workspace packages* (e.g. `wiki-io`'s
entity/index writers) that read export edges and may assert on or render attrs.

**Fix:** Confirm no consumer breaks on the added attr. If the attr is only needed to
drive the dst-kind in the projection, consider dropping it from the persisted edge
attrs after the dst-kind is computed, keeping the on-disk edge attrs minimal:

```python
elif ref.kind == "export":
    edge_attrs = {k: v for k, v in ref.attrs.items() if k != "symbol_kind"}
    edges.append(GraphEdge(
        src=parent_key,
        dst=(ref.attrs.get("symbol_kind", "function"), ref.target_name, None),
        kind="exports",
        attrs=edge_attrs,
    ))
```
Only do this if `symbol_kind` is not itself a wanted edge attribute downstream; if it
is wanted, keep it and just verify consumer tests cover the new shape.

### WR-03: `has_declaration` now set for class/function/type declarations changes the `walk()`-fallback guard semantics

**File:** `packages/source-parser/src/source_parser/parsers/_generic.py:373-422`
**Issue:** The old guard `if not names and not has_lexical_decl` only suppressed the
broad `walk()` fallback for lexical/variable declarations. The rename to
`has_declaration` now *also* sets the flag True for class/function/type declarations
(lines 394-408). In the normal path this is harmless because a successfully named
declaration also appends to `named`, so `not named` is already False. But the two
conditions are no longer independent: if `_resolve_name` ever returns falsy for a
declaration node (e.g. a malformed/anonymous `export default class {}` where name
resolution fails), `named` stays empty while `has_declaration` is now True — so the
`walk()` fallback that previously would have scraped an identifier is suppressed,
silently dropping the export. The old code would still attempt the `walk()` for the
class/function branch since it did not set `has_lexical_decl`.

**Fix:** Make the intent explicit — gate the fallback only on the declaration forms
that truly own their names, or guard the named-declaration branches so they only set
`has_declaration` when a name was actually resolved (they already only append to
`named` in that case, so move the flag inside the `if n:` block — it already is for
these branches; the concern is the *combined* guard). Minimal safe change: keep a
separate `has_lexical_decl` for the lexical/variable branch and leave the
class/function/type branches relying solely on `named` being populated:

```python
if not named and not has_lexical_decl:
    ... walk fallback ...
```
This restores the pre-change fallback reachability for declaration nodes whose name
fails to resolve.

## Info

### IN-01: `_build_type_node` anonymous fallback is inconsistent with class/function nodes

**File:** `packages/source-parser/src/source_parser/parsers/_generic.py:162`
**Issue:** `_build_type_node` uses `_resolve_name(...) or "<anonymous>"`, emitting a
node literally named `"<anonymous>"`. `_build_class_node` (line 182) and
`_build_function_node` (line 124) instead pass `name=None` through, and the projection
(`projections/graph.py:37,46`) substitutes `str(path)` for `None`. So a nameless type
node would be keyed/named `"<anonymous>"` while a nameless class would be keyed by its
path — divergent collision behavior. In practice `interface`/`type_alias`/`enum`
declarations always have names, so this fallback is effectively dead code, but the
inconsistency is a latent footgun if the type-node set ever broadens.

**Fix:** For consistency with the other builders, pass `name=_resolve_name(...)` (which
may be `None`) and let the projection apply the uniform path substitution, dropping the
`"<anonymous>"` literal.

### IN-02: `_ts_kind_for` falls back to the raw tree-sitter node type for unmapped nodes

**File:** `packages/source-parser/src/source_parser/parsers/_generic.py:150-151,170`
**Issue:** `_ts_kind_for` returns `_TS_KIND_MAP.get(node_type, node_type)` — for any
node type not in the 3-entry map it stamps the raw grammar node type string into
`ts_kind`. Since `_build_type_node` is only reached for `config.type_types` (exactly the
three mapped types), the fallback is unreachable today. But if `type_types` is later
extended without updating `_TS_KIND_MAP`, the attr silently leaks an internal grammar
identifier (e.g. `"internal_module"`) into the persisted graph rather than failing
loudly.

**Fix:** Either assert the node type is mapped, or keep the three sources of truth
(`type_types` in the TS config and `_TS_KIND_MAP`) in sync with a comment cross-
referencing each other so a future extension updates both.

### IN-03: `is_type_reexport` is computed for every export statement but only consumed in the fallback branch

**File:** `packages/source-parser/src/source_parser/parsers/_generic.py:362-366,414`
**Issue:** `is_type_reexport` is computed at the top of every export-statement iteration
(a full child scan with a `c.text` byte comparison) but is only read inside the
`if not named and not has_declaration:` fallback branch. For the common case
(`export function`, `export const`, `export class`, `export interface`) the value is
computed and discarded. Minor wasted work and slightly misleading placement; not a
correctness issue.

**Fix:** Move the `is_type_reexport` computation inside the fallback branch where it is
actually used, so it is only evaluated when reaching the `export { ... }` clause path.

---

_Reviewed: 2026-05-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
