---
title: lattice-graph (plugin) — Context
category: package
summary: Concepts, decisions, ingested sources, and v1 / v1.1 scope boundary for the lattice-graph plugin.
updated: 2026-05-11
tokens: 2089
---

# lattice-graph — Context

## Concepts

- [[wiki/concepts/per-repo-layout]] — owns `<repo>/lattice/.graph/code.db`.
- [[wiki/concepts/code-graph-schema]] — two-table (`nodes`, `edges`) + `metadata` schema.
- [[wiki/concepts/code-graph-mcp-surface]] — the deferred-to-v1.1 12-tool MCP surface; CLI mirrors the same library boundary.
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — the principle behind the SessionStart staleness banner and the absence of an FS watcher.
- [[wiki/concepts/plugin-deployment-shapes]] — shape F (library + plugin shell). v1 ships partial F (CLI only); v1.1 fills in the MCP adapter.
- [[wiki/concepts/per-repo-data-vs-global-tooling-tier]] — this plugin sits in the per-repo data tier.
- [[wiki/concepts/language-parser-abstraction]] — the `LanguageParser` interface in the parser, which the core package's update lifecycle consumes.
- [[wiki/concepts/source-tree-model]] — the source-tree model that underpins what the graph indexes.

### v1 scope

- **9 slash commands**: `init`, `update`, `status`, `dump` (4 ops) + `find`, `callers`, `callees`, `imports`, `describe` (5 queries). All shell to `cg`.
- **1 SessionStart hook**: silent staleness banner (`hooks/session-start.py`).
- **5 wired exit codes** (`0`/`1`/`2`/`3`/`5`); 2 reserved (`4`/`6`).
- **Languages**: TypeScript / JavaScript / Python via [[wiki/packages/lattice-source-parser/lattice-source-parser]].
- **Storage**: per-repo SQLite at `<repo>/lattice/.graph/code.db`.
- **Tests**: live in [[wiki/packages/lattice-graph-core/lattice-graph-core]]; the plugin tree has none.

### v1.1 scope (deferred)

- **MCP server adapter** — 12 named MCP tools + `cg_query` raw-SQL escape hatch. Forms shape F's second adapter alongside the CLI.
- **Two additional query commands**: `cg describe-type` (needs `extends` / `inherits` edge kind; bumps `schema_version`), `cg query` (raw SQL, lands with MCP). The other three symmetric-counterpart commands (`cg imported-by`, `cg exports`, `cg exported-by`) originally listed here as v1.1 deferred have already shipped in v0.2.0 — see [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]].
- **C# parser** — committed for v1.1 in the design spec.
- **Wired exit codes 4 and 6** — see [[work/2026-05-06-lattice-code-graph-wire-exit-codes-4-and-6]].

### Why CLI-first (not MCP-first)

The architecture spec originally called for v1 to ship MCP-only with the CLI as a follow-on. The plugin design inverted this. Rationale (captured in ADR-0007-cli-first-code-graph):

> Exercise the library boundary by use through a thin testable adapter (the CLI) before adding a second adapter (MCP). The CLI is small, scriptable, and trivially testable; if the library shape is wrong, it shows up in CLI ergonomics first and gets fixed cheaply.

Concrete benefits realised in v1:

- `cg` works from Bash, scripts, CI, and agent shells without an MCP host.
- Stable exit-code contract (`exit_codes.py`) gives downstream tools (SessionStart hook, `prefer-graph-over-grep`, CI checks) a clean integration point.
- The MCP adapter, when it lands, sits on a library boundary that has actually been used — not guessed.

### Why single-writer SQLite

The architecture spec chose SQLite over KuzuDB / DuckDB / GraphML for the v1 store. The plugin design then layered a single-writer rule on top — captured in ADR-0008-single-writer-code-db because consumer plugins (`prefer-graph-over-grep`, future MCP server, wiki lint) all key off it:

- Trivially-reasonable concurrency: N readers, at most one writer, mediated by the SQLite write-lock.
- WAL-mode readers don't block updates and updates don't block readers.
- All reads use `mode=ro` URI flag — no writer can sneak in by accident.

## Decisions

- ADR-0001-sqlite-primary-store-for-code-graph — SQLite over KuzuDB / DuckDB / GraphML at v1.
- ADR-0002-explicit-graph-update-lifecycle — explicit user-initiated updates; SessionStart hook surfaces staleness; no FS watcher.
- ADR-0006-source-parser-sibling-package — `lattice-source-parser` as a sibling package providing tree-sitter parsing.
- ADR-0007-cli-first-code-graph — v1 ships `cg` + slash commands; MCP slips to v1.1 so the library boundary is exercised through a thin testable adapter first.
- ADR-0008-single-writer-code-db — only `cg update` writes to `code.db`; consumers open `mode=ro`; enforced via SQLite write-lock + reserved exit code 6.
- ADR-0011-single-workspace-root — `<repo>/lattice/` workspace root convention; graph lives at `lattice/.graph/code.db`.

## Sources

(All `[[wiki/sources/...]]` links are dead — stripped. Source titles preserved for reference.)

- 2026-05-lattice-graph-plugin-design — the canonical v1 plugin design: package + plugin split, 9 slash commands + SessionStart hook, CLI-first, MCP and 5 query commands deferred to v1.1.
- 2026-05-lattice-ecosystem-review — origin of the separate-plugin recommendation (different cardinality / cadence / consumer); originally proposed a single `query(...)` MCP tool, refined to 12 named tools.
- 2026-05-lattice-ecosystem-architecture-refinements — schema and naming refinements.
- 2026-05-architecture-3.1-plugin-topology — confirms shape F deployment, separate-plugin decision, cardinality framing. v1 CLI-first inverts this section's MCP-first ordering.
- 2026-05-architecture-3.2-storage-and-schema — SQLite store; nodes / edges / metadata schema; recursive-CTE traversal.
- 2026-05-architecture-3.3-mcp-tools-surface — 12 MCP tools + `cg_query`; CLI 1:1 mirror; library-boundary contract (MCP deferred to v1.1).
- 2026-05-architecture-3.4-update-lifecycle — `git diff`-driven incremental updates; SessionStart hook for staleness; no auto-update; no FS watcher.
- 2026-05-architecture-3.5-language-support — TS / JS / Python at v1; C# at v1.1; `LanguageParser` interface; tree-sitter binary distribution.
- 2026-05-architecture-3.6-wiki-graph-integration — `lattice-wiki` consumes via `cg_describe_package` / `cg_describe_path` / `cg_describe_type` / `cg_status`; CLI fallback.
- 2026-05-architecture-3.8-contracts-between-layers — confirms `<repo>/lattice/.graph/code.db` location; `${LATTICE_GRAPH_ROOT}` env-var convention; `.gitignore` entries for `code.db` / `-wal` / `-shm`.
- [[wiki/sources/2026-05-lattice-graph-core-documents-edge]] — design for `wiki_page` node kind and `documents` edge kind, and the `cg sync-wiki` subcommand that resolves package→wiki overview links (shipped in v0.2.0).
- [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]] — design for `cg imported-by` / `cg exports` / `cg exported-by` — closes the import-graph surface (shipped in v0.2.0).

## Belongs to domain

(none) — the code graph cuts across every package in the repo; it is its own per-repo data tier rather than a domain.

## Used by

- [[wiki/packages/lattice-graph-core/lattice-graph-core]] — the Python package this plugin shells. Owns the SQLite schema, store, upsert, manifest scan, cross-file edge resolve, queries, and the `cg` console-script. All real logic lives there; this plugin is a manifest + 9 markdown files + 1 Python hook.
- [[wiki/packages/lattice-source-parser/lattice-source-parser]] — the tree-sitter wrapper the core package consumes for parsing. Pulls `tree-sitter` + `tree-sitter-language-pack` binary deps that transitively land in this plugin's install graph.
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — wiki lint consumer of `cg describe` / `cg find`.
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — hosts the `prefer-graph-over-grep` skill that calls into this plugin's CLI surface.

## Related dependencies

- [[wiki/packages/lattice-graph-core/lattice-graph-core]] — workspace path-dep; provides the `cg` console-script.
- [[wiki/packages/lattice-source-parser/lattice-source-parser]] — tree-sitter wrapper; pulled transitively.
- `uv` — required at install time by `/lattice-graph:init`.
