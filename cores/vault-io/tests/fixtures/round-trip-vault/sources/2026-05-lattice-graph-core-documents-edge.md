---
title: "lattice-graph-core: documents edge — linking package nodes to wiki pages"
category: source
summary: Design spec adding a `documents` edge kind and `wiki_page` node kind to the code graph, plus the `cg sync-wiki` subcommand that resolves package→wiki overview links by trying three path conventions (packages, apps, domain-scoped). Shipped in lattice-graph v0.2.0.
source_path: lattice/specs/2026-05-11-lattice-graph-core-documents-edge-design.md
source_type: spec
source_date: 2026-05-11
authors: []
ingested: 2026-05-11
updated: 2026-05-11
tags: [lattice-graph-core, lattice-graph, code-graph, sync-wiki, wiki-page, documents-edge]
tokens: 1581
---

# lattice-graph-core: documents edge — linking package nodes to wiki pages

## TL;DR

A design spec that makes the wiki addressable from the code graph. [[wiki/packages/lattice-graph-core/lattice-graph-core]] gains a new `wiki_page` node kind and a `documents` edge kind connecting `kind="package"` nodes to their wiki overview pages. A new `cg sync-wiki` subcommand resolves the link by trying three path conventions in order and emits a drift report (undocumented / newly linked / stale). All shipped in v0.2.0 — see [[wiki/plugins/lattice-graph/lattice-graph]] for the slash-command wrapper.

## Key claims

1. **No schema migration.** The existing `nodes`/`edges` tables already support arbitrary `kind` values, so the new `wiki_page` node kind and `documents` edge kind require no DDL change. `wiki_page` nodes carry the workspace-relative path in `name` (e.g. `wiki/packages/lattice-graph-core/lattice-graph-core.md`). Source: `packages/lattice-graph-core/src/lattice_graph_core/schema.py` and the spec's "Data Model" section.
2. **Three path conventions, tried in order.** For each `kind="package"` node, `sync_wiki.py` checks `wiki/packages/<name>/<name>.md`, then `wiki/apps/<name>/<name>.md`, then `wiki/domains/*/packages/<name>/<name>.md` (glob). First match wins; on a glob collision, emit a warning and skip. See `packages/lattice-graph-core/src/lattice_graph_core/sync_wiki.py`.
3. **Cleanup pass closes the drift loop.** `wiki_page` nodes whose file no longer exists on disk are removed along with their incoming `documents` edges. This handles renames and deletions; without it, the graph would accumulate orphans whenever a wiki page moves.
4. **Drift report classifies three buckets.** `cg sync-wiki` prints **undocumented** (package nodes with no outgoing `documents` edge), **newly linked** (edges added this run), and **stale** (`wiki_page` nodes removed because their file vanished). This is the inverse-direction complement to [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]'s code-drift lint.
5. **Three explicit non-goals.** The spec rules out (a) ingesting wiki sub-pages, ADRs, or concept pages — only package overviews; (b) making `lattice-graph-core` depend on `lattice-wiki-core` — the boundary stays one-way through the filesystem; (c) running wiki sync as part of `cg update` — it's an explicit, separate subcommand. See [[wiki/concepts/explicit-not-magic-update-lifecycle]] for the pattern.
6. **New files (as shipped).** `packages/lattice-graph-core/src/lattice_graph_core/sync_wiki.py`, `packages/lattice-graph-core/src/lattice_graph_core/cli/ops_sync_wiki.py`, registered as `"sync-wiki": ops_sync_wiki` in `cli/main.py`. Test coverage in `tests/test_sync_wiki.py` and `tests/test_cli_sync_wiki.py`.

## Queries enabled

The `documents` edge set makes three graph queries trivial:

- **"What are the docs for package X?"** — outgoing `documents` edges from X's node.
- **"Which packages have no docs?"** — package nodes with no outgoing `documents` edge.
- **"Which wiki pages are orphaned?"** — `wiki_page` nodes with no incoming `documents` edge (these are the stale-file deletions caught by the cleanup pass).

## Proposed changes (as shipped)

- `packages/lattice-graph-core/src/lattice_graph_core/sync_wiki.py` — new module: workspace resolution, package-node load, three-convention path resolver, glob walk for domain-scoped packages, upsert + cleanup, drift-report printer.
- `packages/lattice-graph-core/src/lattice_graph_core/cli/ops_sync_wiki.py` — new thin CLI dispatch following the `ops_update.py` pattern.
- `packages/lattice-graph-core/src/lattice_graph_core/cli/main.py` — register `"sync-wiki": ops_sync_wiki`.
- `plugins/lattice-graph/commands/sync-wiki.md` — slash-command wrapper shelling to `cg sync-wiki`.
- `packages/lattice-graph-core/tests/test_sync_wiki.py`, `tests/test_cli_sync_wiki.py` — unit + CLI smoke tests.

## Surprises / contradictions

- None against the code. The spec matches the shipped v0.2.0 implementation: `sync_wiki.py` and `ops_sync_wiki.py` exist (`packages/lattice-graph-core/src/lattice_graph_core/sync_wiki.py`, `cli/ops_sync_wiki.py`), the slash command is wired (`plugins/lattice-graph/commands/sync-wiki.md`), and the wiki overview pages already reference both.
- Subtle: the `cg sync-wiki` slash command guards on graph existence at `lattice/.graph/` (the path used by other `/lattice-graph:*` query commands per [[wiki/plugins/lattice-graph/api]]), so running `sync-wiki` before `/lattice-graph:init` + `/lattice-graph:update` returns the cosmetic guard error rather than `cg`'s exit 3. Not a contradiction — same plugin-wide pattern.

## Touches

- [[wiki/packages/lattice-graph-core/lattice-graph-core]]
- [[wiki/packages/lattice-graph-core/api]]
- [[wiki/packages/lattice-graph-core/context]]
- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/plugins/lattice-graph/api]]

## Decisions triggered

None new. The spec is a forward-looking implementation plan that aligns with existing decisions:

- [[wiki/adrs/0007-cli-first-code-graph]] — `cg sync-wiki` is another CLI subcommand; no MCP surface added.
- [[wiki/adrs/0008-single-writer-code-db]] — `cg sync-wiki` writes to `code.db`, so it falls under the single-writer rule alongside `cg update`.

The two extensions sketched in "Future Directions" (walking full `wiki/packages/<name>/` subtrees; dedicated `concept`/`work` node kinds for graph-wide wiki topology) are explicitly deferred — candidates for future work items, not ADRs yet.

## Related sources

- [[wiki/sources/2026-05-lattice-wiki-core-lint-code-drift-slug-normalization]] — the wiki-side companion that detects code drift; `cg sync-wiki` is the graph-side inverse.
