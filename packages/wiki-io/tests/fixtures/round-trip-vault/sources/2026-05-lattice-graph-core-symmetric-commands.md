---
title: "lattice-graph-core: symmetric commands — imported-by, exports, exported-by"
category: source
summary: Design spec adding the three missing `cg` subcommands that complete the import-graph surface — `imported-by` (inverse of `imports`, supports `--symbol` and `--depth`), `exports` (forward `exports` edge), and `exported-by` (inverse of `exports`). New query functions `imported_by`, `exports`, `exported_by` in `queries.py`; new CLI modules following the `q_imports.py` pattern; no schema change. Shipped in lattice-graph v0.2.0.
source_path: lattice/specs/2026-05-11-lattice-graph-core-symmetric-commands-design.md
source_type: doc
source_date: 2026-05-11
authors: []
status: draft
ingested: 2026-05-11
updated: 2026-05-11
tags: [lattice-graph-core, lattice-graph, code-graph, imports, exports, cli]
tokens: 1907
---

# lattice-graph-core: symmetric commands — imported-by, exports, exported-by

## TL;DR

A design spec that closes the import-graph surface in [[wiki/packages/lattice-graph-core/lattice-graph-core]]. Before this work the call graph had symmetric pairs (`callers` / `callees`) but the import graph only exposed the forward direction (`imports`); the `exports` edge kind written by [[wiki/packages/lattice-source-parser/lattice-source-parser]] had no query or CLI surface at all. The spec adds three subcommands — `cg imported-by`, `cg exports`, `cg exported-by` — plus three query functions and three CLI modules following the existing `q_imports.py` pattern. No schema change (SCHEMA_VERSION stays at 1). Shipped in lattice-graph v0.2.0; the matching slash commands exist in [[wiki/plugins/lattice-graph/lattice-graph]] (`commands/imported-by.md`, `commands/exports.md`, `commands/exported-by.md`).

## Key claims

1. **Three commands close the import-graph asymmetry.** `cg imported-by <path>` is the inverse of `cg imports` and supports `--symbol <name>` (narrow to importers of a specific symbol) and `--depth N` (default 1; transitive walk like `callers`/`callees`). `cg exports <path>` lists the symbols a file declares as exported (single-hop — exports don't chain). `cg exported-by <symbol>` answers "which file owns this name?" — a navigation shortcut to the definition site. See the spec's "Commands" table.
2. **No schema migration.** The `exports` edge kind was already being written by `lattice-source-parser`; it just had no reader. SCHEMA_VERSION stays at 1. Code paths: edges live in `packages/lattice-graph-core/src/graph_io/schema.py` (existing `nodes`/`edges` tables).
3. **Three new dataclasses + three new query functions in `queries.py`.** `ImporterRecord(path, symbols, depth)`, `ExportRecord(name, kind, line)`, `ExporterRecord(path, name)`. Functions: `imported_by(conn, *, path, symbol=None, depth=1)` — single-hop SQL when `depth=1`, recursive CTE walking backwards through `imports` edges when `depth>1` (modelled after `callers`); `exports(conn, *, path)` — single-hop on `kind='exports'` filtered by `src.path`; `exported_by(conn, *, name)` — single-hop on `kind='exports'` filtered by `dst.name`. Unresolved edges excluded via `_RESOLVED_FILTER`. See `packages/lattice-graph-core/src/graph_io/queries.py`.
4. **Three new CLI modules following the `q_imports.py` pattern.** `cli/q_imported_by.py` registers `path`, `--symbol`, `--depth` (int, default 1); `cli/q_exports.py` registers `path`; `cli/q_exported_by.py` registers `name`. All three wired into `_SUBCOMMANDS` in `cli/main.py` as `"imported-by"`, `"exports"`, `"exported-by"`. Exit code conventions match existing query commands (exit 3 on `NOT_INITIALIZED`, empty results print nothing and return `SUCCESS`).
5. **`_format.py` dispatches on the three new record types.** Human format: `ImporterRecord` → one line per path with symbols collapsed into `(a, b)` parenthetical; `ExportRecord` → `name  kind  line` table; `ExporterRecord` → one path per line. JSON format: per-edge `{path, symbol, depth}` objects for importers, `{name, kind, line}` for exports, `{path, name}` for exporters. Consistent with the `[json] -> [aligned columns]` formatter discipline noted in [[wiki/packages/lattice-graph-core/patterns]].
6. **Existing source-parser quirk surfaces in `exports` output.** The parser currently emits export dst nodes with `kind="function"` regardless of whether the symbol is a class or function; the query returns whatever is stored, so output accuracy improves automatically as the parser is refined (no query change required). Noted in the spec's `exports` description.
7. **Out of scope.** No changes to `lattice-source-parser` (export edges are already written), no schema change, no modifications to existing query functions, no `--depth` flag on `exports` or `exported-by` (exports don't chain meaningfully).

## Proposed changes (as shipped)

- `packages/lattice-graph-core/src/graph_io/queries.py` — three new frozen dataclasses (`ImporterRecord`, `ExportRecord`, `ExporterRecord`) and three new query functions (`imported_by`, `exports`, `exported_by`).
- `packages/lattice-graph-core/src/graph_io/cli/q_imported_by.py` — new CLI module; registers `path`, `--symbol`, `--depth` and dispatches to `queries.imported_by`.
- `packages/lattice-graph-core/src/graph_io/cli/q_exports.py` — new CLI module; registers `path` and dispatches to `queries.exports`.
- `packages/lattice-graph-core/src/graph_io/cli/q_exported_by.py` — new CLI module; registers `name` and dispatches to `queries.exported_by`.
- `packages/lattice-graph-core/src/graph_io/cli/main.py` — three new entries in `_SUBCOMMANDS`.
- `packages/lattice-graph-core/src/graph_io/cli/_format.py` — extended `render()` dispatch for the three new record types.
- `plugins/lattice-graph/commands/imported-by.md`, `commands/exports.md`, `commands/exported-by.md` — slash-command wrappers shelling to `cg`.
- `packages/lattice-graph-core/tests/test_queries.py` and `tests/test_cli_*.py` — unit + CLI subprocess coverage (multiple importers / dedup grouping; `--symbol` narrows; `--depth 2` transitive; unresolved edges excluded; uninitialized DB → exit 3).

## Surprises / contradictions

- None against the code. The spec matches the shipped v0.2.0 implementation: `q_imported_by.py`, `q_exports.py`, `q_exported_by.py` exist in `packages/lattice-graph-core/src/graph_io/cli/`; the matching slash commands exist at `plugins/lattice-graph/commands/imported-by.md`, `exports.md`, `exported-by.md`. [[wiki/packages/lattice-graph-core/api]] already lists all three subcommands and the new `cli/q_*` modules.
- Notable boundary: the spec correctly identifies that `exports` from the parser is currently kind-imprecise (`kind="function"` for non-functions too). The query layer faithfully passes this through rather than guessing — the right place to fix it is `lattice-source-parser`, not `lattice-graph-core`.

## Touches

- [[wiki/packages/lattice-graph-core/lattice-graph-core]]
- [[wiki/packages/lattice-graph-core/api]]
- [[wiki/packages/lattice-graph-core/context]]
- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/plugins/lattice-graph/api]]

## Decisions triggered

None new. The spec is a forward-looking implementation plan that aligns with existing decisions:

- [[wiki/adrs/0007-cli-first-code-graph]] — three more CLI subcommands; no MCP surface added.
- [[wiki/adrs/0008-single-writer-code-db]] — all three new queries open `code.db` read-only, consistent with the rule.

## Related sources

- [[wiki/sources/2026-05-lattice-graph-core-documents-edge]] — companion spec from the same date adding the `documents` edge / `cg sync-wiki` command. Together these two specs define the full v0.2.0 query-surface expansion.
