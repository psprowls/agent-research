# Phase 61: TypeScript `type` Node Kind (source-parser + graph-io) — Context

**Milestone:** v1.11
**Status:** planned
**Created:** 2026-05-30

---

## Phase Boundary

TypeScript `interface` / `type alias` / `enum` declarations currently surface in the
code graph as `kind='function'` nodes (e.g. `APIGatewayProxyEvent`). This phase makes
them first-class **`type`** nodes end-to-end across `source-parser` (parse + projection)
and `graph-io` (cross-kind resolution + deriver bump).

Two root causes (already investigated and confirmed):

1. **Parse side** — `source-parser`'s TS config never extracts interface/type/enum as
   symbols; only class/function/method node types are in the `LanguageConfig` sets, so
   these declarations are never emitted as real nodes.
2. **Projection side** — `packages/source-parser/src/source_parser/projections/graph.py`
   (the `exports` edge branch) hardcodes the export-edge destination to
   `("function", ref.target_name, None)`, so the export stub node is mislabeled
   `function` regardless of the real symbol kind.

The work has two halves:
- **A = correctness fix** — exported types stop being mislabeled `function`.
- **B = feature** — interface/type-alias/enum become real `type` nodes with a sub-kind.

**In scope:**
- TypeScript (`.ts`/`.tsx`) interface / type-alias / enum extraction as `kind="type"`.
- Sub-kind stored in node `attrs` as `ts_kind` ∈ {`interface`, `type_alias`, `enum`}.
- Export-edge destination kind threaded through the `Reference.attrs` (`symbol_kind`).
- graph-io cross-kind resolution extended to include `type`.
- `DERIVER_VERSION` bump so existing graphs auto-rebuild.
- Fixtures + tests for both packages; verification rebuild of `mono-repo-live`.

**Out of scope (explicitly deferred):**
- Splitting `type` into separate `interface` / `enum` node kinds — **rejected**; single
  `type` kind with `ts_kind` attr is the locked design.
- Python type-alias / `Protocol` / `TypedDict` handling — **TS/JS only** this phase.
- Wiki page generation for `type` nodes — this is graph search/traversal value, not a
  new wiki page template.
- JavaScript type extraction — JS has no types; the JS `LanguageConfig` leaves
  `type_types` empty.

---

## Locked Decisions

These were made by the user and are **not** to be re-decided during planning/execution:

1. **Single `type` kind.** One new node `kind` value `type` covers interface + type
   alias + enum. Do NOT introduce separate `interface`/`enum` kinds.
2. **`ts_kind` attr for sub-kind.** Store the specific sub-kind in node
   `attrs={"ts_kind": <interface|type_alias|enum>}`, derived from the tree-sitter node
   type (`interface_declaration` → `interface`, `type_alias_declaration` → `type_alias`,
   `enum_declaration` → `enum`).
3. **Projection fix via `symbol_kind`.** Change the `exports` edge branch dst from the
   hardcoded `("function", ...)` to `(ref.attrs.get("symbol_kind", "function"), ...)`.
   LEAVE the `calls` edge branch hardcoded to `function` (calls only target
   functions/methods).
4. **Cross-kind resolution includes `type`.** Add `"type"` to `_CROSS_KIND_RESOLVABLE`
   AND to the cross-kind resolution SQL `kind IN (...)` clause in `graph-io/resolve.py`.
5. **DERIVER bump, not SCHEMA bump.** `DERIVER_VERSION` 4 → 5 (derivation logic changed,
   forces auto-rebuild). `SCHEMA_VERSION` stays unchanged — `kind` is an unconstrained
   TEXT column with no CHECK constraint.
6. **Bare re-export fallback.** Bare re-exports (`export { x }`) cannot know the symbol
   kind at parse time; default those export refs to a `function` placeholder and let the
   graph-io cross-kind sweep resolve them when exactly one real node of that name exists
   graph-wide.

### Known subtlety (must be honored)

The `Reference` dataclass in `packages/source-parser/src/source_parser/tree.py` carries
the **ref** kind (`call`/`import`/`export`), NOT the symbol kind. Threading
`symbol_kind` through export refs via `Reference.attrs` is therefore **required** for the
projection fix to work. Both `SourceNode` and `Reference` already expose an `attrs: dict`
field, so no dataclass changes are needed — `project_nodes` already passes `n.attrs`
through, so `ts_kind` flows automatically once `_build_type_node` sets it.

---

## Canonical References

| What | Where |
|------|-------|
| `LanguageConfig` dataclass (add `type_types` field) | `packages/source-parser/src/source_parser/parsers/_config.py` |
| TS config (set `type_types`) | `packages/source-parser/src/source_parser/parsers/typescript.py` |
| JS config (leave `type_types` empty) | `packages/source-parser/src/source_parser/parsers/javascript.py` |
| Generic walker (`_build_type_node`, `_walk_container`, `_handle_export`, `_extract_exports`) | `packages/source-parser/src/source_parser/parsers/_generic.py` |
| `SourceNode` / `Reference` dataclasses (`attrs` already present) | `packages/source-parser/src/source_parser/tree.py` |
| Graph projection (`exports` edge dst fix) | `packages/source-parser/src/source_parser/projections/graph.py` |
| Cross-kind resolution | `packages/graph-io/src/graph_io/resolve.py` (`_CROSS_KIND_RESOLVABLE`, inline `kind IN (...)` SQL) |
| Schema/version constants | `packages/graph-io/src/graph_io/schema.py` (`DERIVER_VERSION`, `SCHEMA_VERSION`) |
| Verification workspace | `~/Personal/graph-wiki/mono-repo-live` |

### Render / queries kind-allowlist investigation (resolved)

The locked brief asked the planner to confirm whether `graph-io/render.py` or
`queries.py` carry a kind-based labeling or valid-kinds allowlist needing a `type` entry.
**Finding: neither file exists** in this checkout. The current `graph-io` package is a
minimal stub (`__init__.py`, `classify.py`, `resolve.py`, `schema.py` only) — there is no
`render.py`, `queries.py`, or `cli/` directory anywhere under `packages/`. `schema.py`
explicitly documents `kind` as an unconstrained TEXT column with no CHECK constraint.
**No render/queries allowlist task is needed.** Should `render.py`/`queries.py` be
introduced later, re-check for a kind allowlist at that time.

> **Scaffold note:** Several paths described in the project CLAUDE.md (richer `graph-io`
> with `cli/`, `render.py`, `queries.py`; source-parser `fixtures/<lang>/` + tests) do
> NOT yet exist on disk — the packages are early stubs. The fixtures and test files this
> phase calls for will be **created**, and the test/fixture conventions are followed as
> documented (paired `*.expected.json` + `*.graph.expected.json`, parametrized).

---

## Success Criteria

- [ ] `LanguageConfig` has a `type_types: frozenset[str] = frozenset()` field; TS config
      sets it to `{interface_declaration, type_alias_declaration, enum_declaration}`;
      JS config leaves it empty.
- [ ] `_build_type_node` emits `SourceNode(kind="type", ..., attrs={"ts_kind": ...})`
      with `ts_kind` correctly derived from the tree-sitter node type.
- [ ] `_walk_container` emits a `type` child for both `interface Foo` and
      `export interface Foo` (the `export_statement` peek branch handles `type_types`).
- [ ] `_extract_exports` resolves type-declaration names and stamps
      `attrs={"symbol_kind": "type"}` (or `class`/`function` as appropriate) onto the
      export `Reference`.
- [ ] `projections/graph.py` `exports` branch uses
      `ref.attrs.get("symbol_kind", "function")` for the dst kind; `calls` branch
      unchanged.
- [ ] `graph-io/resolve.py` includes `type` in both `_CROSS_KIND_RESOLVABLE` and the
      cross-kind resolution SQL.
- [ ] `graph-io/schema.py` `DERIVER_VERSION == 5`; `SCHEMA_VERSION` unchanged.
- [ ] source-parser TS fixtures added (bare interface, exported interface, type alias,
      enum; exported + non-exported variants) with paired `*.expected.json` and
      `*.graph.expected.json`, green under parametrized tests.
- [ ] graph-io resolve test asserts a `type` placeholder export edge resolves to a real
      `type` node via the cross-kind fallback.
- [ ] Verification: rebuilding the `mono-repo-live` code graph shows
      `APIGatewayProxyEvent` as `kind=type` with `ts_kind=interface` (NOT `function`).
- [ ] `uv run pytest` green for both `source-parser` and `graph-io`.

---

## Deferred / Notes

- Splitting `type` into per-construct kinds (`interface`/`enum`) — deferred (rejected by
  design).
- Python type-alias / `Protocol` / `TypedDict` — deferred (TS/JS only this phase).
- `type` node wiki page templates — deferred (graph value only).
- A render/queries kind allowlist — N/A (files do not exist; revisit if added later).
