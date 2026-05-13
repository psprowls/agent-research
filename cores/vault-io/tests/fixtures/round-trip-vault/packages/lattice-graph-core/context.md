---
title: lattice-graph-core — Context
category: package
summary: Concepts, decisions, sources, and history for lattice-graph-core
updated: 2026-05-11
tokens: 707
---

# lattice-graph-core — Context

## Concepts

- [[wiki/concepts/code-graph-schema]] — nodes / edges / metadata schema that `schema.py` implements
- [[wiki/concepts/code-graph-mcp-surface]] — MCP tool surface (deferred to v1.1; CLI is v1)
- [[wiki/concepts/language-parser-abstraction]] — per-language parsers live in `lattice-source-parser`; this library consumes their output
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — `update.py` implements the explicit user-initiated update; no FS watcher
- [[wiki/concepts/plugin-deployment-shapes]] — shape F: MCP server + CLI sharing this query library (CLI ships v1, MCP at v1.1)

## Decisions

- [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]] — SQLite at `<repo>/.lattice/graph/code.db`
- [[wiki/adrs/0002-explicit-graph-update-lifecycle]] — no auto-update, no FS watcher
- [[wiki/adrs/0007-cli-first-code-graph]] — v1 ships the `cg` console-script (only the CLI adapter); MCP slips to v1.1
- [[wiki/adrs/0008-single-writer-code-db]] — `cg update` is the only writer; consumers open `code.db` read-only
- [[wiki/adrs/0009-uv-ruff-python-tooling]] — workspace member under the root `uv.lock`; ruff config and `.python-version` are root-only

## Sources

- 2026-05-lattice-source-parser-readme — confirms `GraphRecords` (`.nodes` / `.edges`) is the upstream's public output that this library upserts into the SQLite store
- 2026-05-lattice-graph-plugin-design — package + plugin split; v1 CLI surface, deferred items, single-writer DB, single-transaction update, stable exit codes, pytest testing strategy
- 2026-05-uv-ruff-monorepo-design — uv workspace membership and ruff tooling for this package
- [[wiki/sources/2026-05-lattice-graph-core-documents-edge]] — adds `wiki_page` node kind and `documents` edge kind; `cg sync-wiki` resolves package→wiki overview links via three path conventions and emits a drift report
- [[wiki/sources/2026-05-lattice-graph-core-symmetric-commands]] — adds `cg imported-by` / `cg exports` / `cg exported-by` to complete the import-graph surface; three new query functions + CLI modules; no schema change. Shipped in v0.2.0.

## Belongs to domain

(none)

## Used by

- [[wiki/plugins/lattice-graph/lattice-graph]] — the Claude Code plugin shell; wraps this library via path-dep and shells out to `cg` for slash commands

## Related dependencies

- [[wiki/packages/lattice-source-parser/lattice-source-parser]] — parsing substrate; this library consumes `GraphRecords` produced by `parse_file` + `to_graph_records`
- [[wiki/packages/lattice-workspace/lattice-workspace]] — workspace-detection helpers
