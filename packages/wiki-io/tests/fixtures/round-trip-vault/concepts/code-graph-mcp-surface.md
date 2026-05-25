---
title: Code-graph MCP tool surface (12 tools + cg_query)
category: concept
summary: The 12 named MCP tools lattice-graph exposes, common conventions (envelopes, error codes, limits), and the library-boundary contract that makes the CLI a 1:1 mirror. MCP surface deferred to v1.1; CLI is v1.
tags: [mcp, code-graph, cli, tools]
sources: 2
updated: 2026-05-09
tokens: 1859
---

# Code-graph MCP tool surface (12 tools + `cg_query`)

> [!info] MCP surface deferred to v1.1
> Per 2026-05-lattice-graph-plugin-design §9.1, v1 ships **CLI-first** — the MCP server adapter slips to v1.1 once the library boundary stabilizes through real CLI use. v1 also trims five query commands (`cg describe-type`, `cg imported-by`, `cg exports`, `cg exported-by`, `cg query`) — see that source for the full deferred list. This page documents the eventual v1.1 surface; until then, only the v1 CLI commands listed in [[wiki/packages/lattice-graph-core/lattice-graph-core]] are available.

## Definition
[[wiki/plugins/lattice-graph/lattice-graph]] will expose its index through 12 named MCP tools plus `cg_query` (raw-SQL escape hatch) at v1.1. The Python CLI mirrors the surface 1:1; both adapters share one query library — at v1, that library lives in [[wiki/packages/lattice-graph-core/lattice-graph-core]] (`queries.py`) and only the CLI adapter ships.

## Tool list (v1)

| Tool | Purpose | Hot consumer |
|---|---|---|
| `cg_find` | Definitions matching a name (or pattern) + optional kind/package filters | every agent loop; lint resolution |
| `cg_callers` | Who calls this function/method, depth-bounded | agent code-comprehension |
| `cg_callees` | What this function/method calls, depth-bounded | agent code-comprehension |
| `cg_imports` | What this file/package imports | lint; impact analysis |
| `cg_imported_by` | Who imports this file/package | impact analysis |
| `cg_exports` | Full list of exports from a file/package (uncapped vs. the digest) | wiki public-API sweeps; refactoring |
| `cg_exported_by` | Where a symbol is publicly exported from — re-export resolution | "what's the canonical import path for X?" |
| `cg_describe_package` | Structured digest of a package (files, exports, deps, counts) | wiki citation verification; agent code-comprehension |
| `cg_describe_type` | Structured digest of a type/class (fields, methods, parents) | wiki data-model drift detection (§3.6) |
| `cg_describe_path` | Resolve a path (with or without `:line`) — exists, kind, contained symbols | lint citation verification |
| `cg_status` | Index freshness, counts, schema version | agents check before relying on stale data |
| `cg_query` | Raw SQL on read-only DB — escape hatch | agents and humans; v2 tool incubator |

`raw/specs/architecture/3.3-mcp-tools-surface.md:34-49`.

## Design principles

1. **Named tools for common questions; one raw-SQL escape hatch for everything else.**
2. **Tools track consumer questions, not schema edge kinds.** (Schema has 4 edge kinds; surface has 3 traversal pairs because `contains` is consumed via `cg_describe_*`.)
3. **Per-edge-direction tools, not direction-as-arg.** `cg_callers` and `cg_callees` are separate tools; agents pattern-match on names.
4. **`describe_*` returns a digest** suitable for narrative use.
5. **List-returning tools always return `{items: [...], truncated: bool, limit_used: int}`.** Never bare arrays.
6. **No write API for consumers.** Writes go through `/code-graph:update` slash command.
7. **Read-only enforcement at the connection layer.** Server opens SQLite with `mode=ro`.
8. **Disambiguation by returning, not erroring.** When a name resolves across multiple packages, return all matches; consumer narrows.

`raw/specs/architecture/3.3-mcp-tools-surface.md:22-30`.

## Common conventions

- **Limits.** Default `limit: 100`; hard ceiling 1000. `cg_query` ceiling 1000 rows + 5 s timeout.
- **Errors.** Stable codes across versions: `not_found`, `ambiguous`, `invalid_arg`, `query_timeout`, `query_too_complex`, `read_only_violation`.
- **Argument shapes.** `name` (exact), `name_pattern` (glob, or `re:` prefix for regex), `kind` (enum), `package` (disambiguator), `path` (relative or `path:line`), `depth` (1–5, default 1).
- **Disambiguation.** When `name` matches in multiple packages and `package:` isn't supplied, return all matches with package qualifiers.

## CLI mirror

| MCP tool | CLI command |
|---|---|
| `cg_find` | `cg find <name>` (with `--kind`, `--package`, `--pattern`, `--limit`) |
| `cg_callers` | `cg callers <name>` |
| `cg_callees` | `cg callees <name>` |
| `cg_imports` | `cg imports <target>` |
| `cg_imported_by` | `cg imported-by <target>` |
| `cg_exports` | `cg exports <target>` |
| `cg_exported_by` | `cg exported-by <name>` |
| `cg_describe_package` | `cg describe-package <name>` |
| `cg_describe_type` | `cg describe-type <name>` |
| `cg_describe_path` | `cg describe-path <path>` |
| `cg_status` | `cg status` |
| `cg_query` | `cg query "<sql>"` (multi-line via stdin: `cg query - < file.sql`) |

Default output: JSON to stdout. `--pretty` or TTY-detected: aligned table. `--json` forces JSON when stdout is a TTY. Exit codes: `0` success, `2` invalid args, `3` query error (timeout, syntax, read-only violation), `4` index missing or unreadable.

## Library boundary

```
plugins/lattice-graph/
├── lib/                          # the query library — source of truth
│   ├── __init__.py               #   public API: find(), callers(), describe_package(), ...
│   ├── schema.py                 #   SQLite schema + migrations
│   ├── queries.py                #   named query implementations
│   └── attrs.py                  #   per-language attrs_json shape
├── mcp/server.py                 # MCP adapter — tool registration → lib calls
└── cli/cg.py                     # CLI adapter — argparse → lib calls
```

The library is the unit of versioning. MCP and CLI bump together because they share the API contract; the library bumps when a query changes shape (a new field, a renamed argument).

## Used in
- [[wiki/plugins/lattice-graph/lattice-graph]] — exposes this surface
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — consumes via `cg_describe_package` (citation verification), `cg_describe_path` (lint), `cg_describe_type` (data-model drift) per §3.6
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — consumes `cg_callers`, `cg_callees`, `cg_find` as grep replacements per §3.9

## Related patterns
- [[wiki/concepts/code-graph-schema]] — what the tools query against
- [[wiki/concepts/plugin-deployment-shapes]] — shape F splits one surface across two adapters

## Sources
- 2026-05-architecture-3.3-mcp-tools-surface — original 12-tool surface and library-boundary contract
- 2026-05-lattice-graph-plugin-design — CLI-first decision; MCP and 5 query commands deferred to v1.1

## Open questions / gotchas
- `cg_describe_type` becomes list-returning (`{items, truncated}`) when ambiguous — exception to "single-record tools return a record." Documented per-tool.
- v2 candidates from `cg_query` promotion: streaming results, cross-file diff queries, type-shape comparison.
