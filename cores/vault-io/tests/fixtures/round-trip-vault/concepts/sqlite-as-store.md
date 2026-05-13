---
title: SQLite as store
category: concept
summary: SQLite is the lattice code graph's primary persistence layer — embedded, zero-dependency, gitignored machine state that enables fast local queries over the symbol and dependency graph.
tags: [sqlite, storage, lattice-graph, persistence, adr]
updated: 2026-05-09
tokens: 477
---

# SQLite as store

## Decision

[[wiki/adrs/0001-sqlite-primary-store-for-code-graph]] and [[wiki/adrs/0008-single-writer-code-db]] establish SQLite as the code graph's backing store. The database (`code.db`) lives at `<workspace>/.graph/` — gitignored machine state that is regenerated from source by `cg scan`.

## Why SQLite

| Reason | Detail |
|---|---|
| Zero server infra | Embedded library; no daemon, no network, no credentials |
| Zero Python deps for readers | `sqlite3` is stdlib; consumers can query without installing lattice packages |
| Fast local queries | Symbol lookup, dependency traversal, and graph analytics run in microseconds on a laptop |
| Single-file portability | `.graph/code.db` can be copied, diffed, or deleted and regenerated cleanly |

## Single-writer design

ADR-0008 mandates a single-writer model: only `cg scan` writes to `code.db`. Readers (lint scripts, CLI queries, the curator retriever) open the DB read-only. This avoids WAL contention and makes the DB safe to query while a scan is running.

## Where it appears

- [[wiki/packages/lattice-graph-core/lattice-graph-core]] — owns the schema, scan writer, and query surface
- [[wiki/plugins/lattice-graph/lattice-graph]] — ships the `cg` CLI; `cg scan` rebuilds the DB from the repo
- [[wiki/packages/lattice-source-parser/lattice-source-parser]] — feeds parsed symbols into the graph writer
- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — reads the graph DB via the `GraphSource` adapter for the two-pass retriever

## Related

- [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]]
- [[wiki/adrs/0007-cli-first-code-graph]]
- [[wiki/adrs/0008-single-writer-code-db]]
