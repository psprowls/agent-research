---
title: lattice-graph-core
category: package
summary: SQLite-backed code-graph library for the lattice ecosystem — schema, upsert, manifest scanning, cross-file edge resolution, read-only query layer (including imports, exports, exported-by, imported-by), wiki sync, and the `cg` CLI.
status: active
package_path: packages/lattice-graph-core
package_type: library
domain:
language: Python
depends_on:
  - packages/lattice-source-parser/lattice-source-parser
  - packages/lattice-workspace/lattice-workspace
tags:
  - python
  - code-graph
  - sqlite
  - cli
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 2023
---

# lattice-graph-core

## Purpose

`lattice-graph-core` is the shareable Python library that builds and queries a SQLite-backed code graph for any git repo in the lattice ecosystem. It owns the `nodes`/`edges`/`metadata` schema (`schema.py`), the write path from `lattice-source-parser`'s `GraphRecords` through `upsert.py`, manifest scanning (`packages.py`), cross-file edge resolution (`resolve.py`), a read-only query layer (`queries.py`) including the new `exports`, `exported_by`, and `imported_by` functions, wiki-sync (`sync_wiki.py`), and the `cg` CLI with thirteen subcommands (v0.2.0). It is extracted as a standalone package so that the Claude Code plugin shell at `plugins/lattice-graph/` and any future consumers (MCP server, CI scripts) can depend on it without bundling the plugin layer.

## File map

Package root containing the hatchling build config, developer docs, and pytest root-level conftest.

- `CLAUDE.md` — Developer conventions: layout overview, testing conventions, and connection/transaction rules.
- `conftest.py` — Shared test fixtures and helpers.
- `pyproject.toml` — Declares the `lattice-graph-core` package, its `lattice-source-parser` and `lattice-workspace` deps, and the `cg` script entry point.
- `README.md` — User-facing overview of capabilities, exit-code table, and quick-start instructions.

### lattice-graph-core/src/graph_io/

Core library modules: schema, store, upsert, queries, packages, resolve, update, and the `cg` CLI sub-package.

- `__init__.py` — Declares the package version (`__version__`).
- `exit_codes.py` — Defines stable integer exit codes (`SUCCESS`, `STALE`, `NOT_INITIALIZED`, etc.) relied on by script consumers.
- `packages.py` — Scans `pyproject.toml` and `package.json` manifests under a repo root and upserts `kind:package` nodes with `contains` edges into the graph.
- `queries.py` — Read-only query functions (`find`, `callers`, `callees`, `imports`, `exports`, `exported_by`, `imported_by`, `describe_package`, `describe_path`) and their dataclass result types. `exports(conn, path)` returns all symbols exported from a file; `exported_by(conn, name)` finds which files export a given symbol name; `imported_by(conn, path)` finds symbols in other files that import from the given path.
- `resolve.py` — Post-upsert sweep that resolves placeholder-destination edges by matching `(kind, name)` to real nodes and tagging each edge with `exact`, `ambiguous`, or `unresolved`.
- `schema.py` — Defines the `nodes`, `edges`, and `metadata` DDL and applies it idempotently; owns `SCHEMA_VERSION`.
- `store.py` — SQLite connection helpers: `connect`, `read_only_connect`, `transaction` context manager, and `GraphNotInitializedError`.
- `sync_wiki.py` — **New in v0.2.0.** Walks the lattice wiki directory, resolves each package page, and writes `wiki_page` metadata edges from `kind:package` nodes to their wiki overview page paths.
- `update.py` — Update orchestrator: resolves changed files via `git diff`/`ls-files`, parses them with `lattice-source-parser`, upserts records, refreshes packages, runs the resolve sweep, and writes `last_indexed_commit` metadata.
- `upsert.py` — Idempotent upsert of `GraphRecords` (nodes and edges) into SQLite, keyed on `(kind, name, path)`.

#### lattice-graph-core/src/graph_io/cli/

Thirteen argparse subcommand modules wired together by the `cg` entry point (four new in v0.2.0).

- `main.py` — CLI entry point: builds the argparse parser, registers all thirteen subcommands, and dispatches to each module's `run()`.
- `_format.py` — Renders lists of dataclass records as aligned-column human text or JSON.
- `ops_dump.py` — Implements `cg dump` — prints a raw SQL dump of the graph DB for debugging.
- `ops_status.py` — Implements `cg status` — reports schema version, `last_indexed_commit` vs HEAD, node/edge counts, and languages; exits `STALE` (2) when the graph is behind.
- `ops_sync_wiki.py` — **New in v0.2.0.** Implements `cg sync-wiki` — walks the lattice wiki, resolves each package page, and writes `wiki_page` metadata edges from package nodes to their overview pages.
- `ops_update.py` — Implements `cg update [--full]` — delegates to `update.run()` and maps exceptions to stable exit codes.
- `q_callees.py` — Implements `cg callees <name> [--depth N]` — returns symbols transitively called by the named symbol.
- `q_callers.py` — Implements `cg callers <name> [--depth N]` — returns symbols that transitively call the named symbol.
- `q_describe_package.py` — Implements `cg describe-package <name>` — prints or JSON-encodes a `PackageDescription`.
- `q_describe_path.py` — Implements `cg describe-path <path>` — prints or JSON-encodes a `PathDescription`.
- `q_exported_by.py` — **New in v0.2.0.** Implements `cg exported-by <name>` — finds which files export the given symbol name.
- `q_exports.py` — **New in v0.2.0.** Implements `cg exports <path>` — lists all symbols exported by the given file.
- `q_find.py` — Implements `cg find <name> [--kind KIND]` — looks up nodes by name and optional kind.
- `q_imported_by.py` — **New in v0.2.0.** Implements `cg imported-by <path>` — returns symbols in other files that import from the given path.
- `q_imports.py` — Implements `cg imports <path>` — returns the resolved import targets for a given file path.

### lattice-graph-core/tests/

pytest suite covering unit, integration, and CLI subprocess scenarios.

- `_git_repo.py` — Shared test fixtures and helpers (git repo scaffolding for tests).
- `test_cli_exit_codes.py` — Unit tests for `exit_codes.py`.
- `test_cli_format.py` — Unit tests for `_format.py`.
- `test_cli_smoke.py` — Smoke tests for the `cg` CLI subcommands.
- `test_cli_status_staleness.py` — Unit tests for `cg status` staleness detection.
- `test_cli_sync_wiki.py` — **New in v0.2.0.** Unit tests for `cg sync-wiki`.
- `test_e2e.py` — End-to-end tests exercising the full update-then-query cycle.
- `test_packages.py` — Unit tests for `packages.py`.
- `test_queries.py` — Unit tests for `queries.py`.
- `test_resolve.py` — Unit tests for `resolve.py`.
- `test_schema.py` — Unit tests for `schema.py`.
- `test_smoke.py` — Broad smoke tests for the library surface.
- `test_store.py` — Unit tests for `store.py`.
- `test_sync_wiki.py` — **New in v0.2.0.** Unit tests for `sync_wiki.py`.
- `test_update_full.py` — Unit tests for `update.py` full-rebuild mode.
- `test_update_idempotent.py` — Unit tests for `update.py` idempotency guarantees.
- `test_update_incremental.py` — Unit tests for `update.py` incremental (diff-based) mode.
- `test_update_interrupt.py` — Unit tests for `update.py` behaviour under interrupted writes.
- `test_upsert.py` — Unit tests for `upsert.py`.

## Sub-pages

- [[wiki/packages/lattice-graph-core/api]]      — public API, CLI surface, exit codes, module layout
- [[wiki/packages/lattice-graph-core/patterns]] — key patterns, conventions, tooling, dependencies
- [[wiki/packages/lattice-graph-core/work]]     — bugs, tech debt, features, open questions
- [[wiki/packages/lattice-graph-core/context]]  — concepts, decisions, ADRs, sources
