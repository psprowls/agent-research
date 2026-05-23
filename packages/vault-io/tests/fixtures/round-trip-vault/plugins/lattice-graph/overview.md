---
title: lattice-graph
category: package
summary: Claude Code plugin shell for the per-repo code graph. Thin shell over `lattice-graph-core` — 13 slash commands wrapping `cg` plus a SessionStart staleness hook (hook config in hooks/hooks.json since v0.2.1). MCP server adapter deferred to v1.1.
status: active
package_path: plugins/lattice-graph
package_type: plugin
domain:
language: Python
version: 0.3.0
depends_on:
  - packages/lattice-graph-core/lattice-graph-core
tags: [plugin, code-graph, cli, sqlite, tree-sitter]
updated: 2026-05-11
last_sync_commit: 97a27ff7e874647009710d9a9aee18be97bc924c
last_sync_at: 2026-05-11
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 1119
---

# lattice-graph

## Purpose

The Claude Code plugin tier of the lattice code-graph stack. A thin shell — manifest, slash-command wrappers, and a SessionStart hook — sitting on top of [[wiki/packages/lattice-graph-core/lattice-graph-core]], which owns all Python logic (schema, SQLite store, upsert, manifest scan, cross-file edge resolve, queries, and the `cg` console-script). v0.2.0 is CLI-first per ADR-0007-cli-first-code-graph: every slash command shells to `cg`; the MCP server adapter slips to v1.1. The graph itself is a per-repo SQLite database at `<repo>/lattice/.graph/code.db` parsed by [[wiki/packages/lattice-source-parser/lattice-source-parser]] (tree-sitter). Designed for tools and agents — not humans — at cardinalities (10K–500K nodes) and access patterns (point lookups + bounded traversals) where a relational store outperforms a native graph database.

## File map

- `.claude-plugin/plugin.json` — manifest (v0.3.0): declares `license: MIT`, `keywords`, and `env.LATTICE_GRAPH_ROOT`. No `commands` array — commands are auto-discovered from the `commands/` directory (Claude Code plugin schema rejects the `commands` field). Hook config in `hooks/hooks.json` since v0.2.1.
- `commands/` — one markdown file per slash command; each shells to `cg` via `{{args}}` passthrough.
  - `init.md` — installs `cg` via `uv tool install` (marketplace placeholders `{{REPO_URL}}` / `{{VERSION}}` filled at install time).
  - `update.md` — wraps `cg update {{args}}`; forwards `--full` for a full rebuild.
  - `status.md` — wraps `cg status {{args}}`.
  - `dump.md` — wraps `cg dump`.
  - `find.md`, `callers.md`, `callees.md`, `imports.md`, `describe.md` — query subcommands; each includes a fast-fail guard before invoking `cg`.
  - `imported-by.md` — wraps `cg imported-by <path>`; returns symbols in other files that import from the given path.
  - `exports.md` — wraps `cg exports <path>`; lists all symbols exported by the given file.
  - `exported-by.md` — wraps `cg exported-by <name>`; finds which files export the given symbol name.
  - `sync-wiki.md` — wraps `cg sync-wiki`; links package nodes in the code graph to their wiki overview pages.
- `hooks/hooks.json` — hook configuration (added v0.2.1); declares the `SessionStart` hook pointing to `session-start.py`. Separated from `plugin.json` to follow the standard hooks convention used by `lattice-workflows` and `lattice-curator`.
- `hooks/session-start.py` — 33-line stdlib-only script; calls `cg --fmt json status`, prints a one-line banner on exit code 2 (stale), silent otherwise. Always returns 0.
- `pyproject.toml` — declares `lattice-graph-core` as a workspace dep so `uv sync` puts `cg` on `PATH`.
- `README.md` — surface summary and reserved exit codes (4 / 6).
- `CLAUDE.md` — contributor notes; codifies "logic in core, not here; tests in core, not here." Adding a new slash command: (1) add markdown file under `commands/`, (2) body shells to `cg <subcommand>`, (3) tests in `lattice-graph-core`. No `commands` array entry needed.

## Sub-pages

- [[wiki/plugins/lattice-graph/api]] — slash commands with full signatures, SessionStart hook contract, exit codes
- [[wiki/plugins/lattice-graph/patterns]] — thin-shell pattern, single-writer rule, staleness banner, command composition
- [[wiki/plugins/lattice-graph/work]] — open follow-ons, code drift, open questions
- [[wiki/plugins/lattice-graph/context]] — concepts, ADRs, scope boundaries, why CLI-first
