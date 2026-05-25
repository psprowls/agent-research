---
title: "ADR-0001: SQLite is the primary store for lattice-graph"
category: adr
summary: Use SQLite at `<workspace>/.graph/code.db` as the primary store for lattice-graph, with a two-table + metadata schema and recursive CTEs for traversal.
adr_id: "0001"
status: accepted
decision_date: 2026-05-03
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [architecture, code-graph, sqlite, storage]
updated: 2026-05-09
tokens: 1003
---

# ADR-0001: SQLite is the primary store for lattice-graph

**Status:** accepted (2026-05-03)

## Context
The code-graph layer needs persistent storage. The "graphs need graph databases" intuition is real but doesn't survive contact with our cardinality (10K–500K nodes) and access patterns (point lookups + bounded traversals at depth ≤ 3). Five storage options weighed in the storage and schema spec: SQLite, DuckDB, KuzuDB, Neo4j/Memgraph, GraphML+NetworkX.

## Decision
Use **SQLite** as the primary store for [[wiki/plugins/lattice-graph/lattice-graph]], with the canonical two-table + metadata schema documented in [[wiki/concepts/code-graph-schema]] and the database file at `<workspace>/.graph/code.db` (where workspace defaults to `<repo>/lattice/` — see [[wiki/packages/lattice-workspace/lattice-workspace]]).

Recursive CTEs handle the bounded traversal queries (depth ≤ 3) that constitute the hot path; per-language detail lives in `attrs_json` blobs to keep the core graph language-agnostic.

## Consequences

**Positive:**
- **Stdlib in Python.** No second binary dep beyond tree-sitter.
- **25-year file-format stability.** SQLite guarantees backwards compat; survives plugin upgrades without graph rebuilds (modulo schema migrations).
- **SQL is the universal query language.** Every agent and human already knows it; the `cg_query` raw-SQL escape hatch is a much stronger v2-tool incubator than Cypher would be.
- **WAL-mode concurrency** matches the MCP daemon shape (many readers + occasional writes) without configuration.
- **Mature operational tooling** (`sqlite3` CLI preinstalled on macOS; GUI tools, ORMs, replication tools all mature).
- **At our cardinality, joins are fine.** The "SQL is bad at graphs" trope is from 100M+ edge regimes.

**Negative:**
- Not a "native graph" engine; deeper traversals (>3 hops, complex pattern matches) are awkward in recursive CTEs vs. Cypher.
- No first-class vector type; if embedding-based similarity edges land later (v2), `sqlite-vec` is itself another binary dep.
- Cypher would be a more expressive escape hatch for graph specialists — but agents aren't Cypher specialists.

## Alternatives considered
- **KuzuDB** (the genuine native-graph candidate) — rejected at v1: file-format churn (~3 years old, on-disk format breaks across minor versions); thinner CLI/binding ecosystem; second binary dep; SQL escape hatch is much stronger than Cypher for agents.
- **DuckDB** — rejected: analytical-first scan-heavy engine; our workload is point-lookup + bounded-traversal (transactional-shaped). Single-process concurrency awkward for an MCP daemon.
- **Neo4j / Memgraph** — rejected: server install (JVM, etc.); overkill at this cardinality.
- **GraphML + NetworkX** — rejected: GraphML is a serialization format, not a query engine. Loading into NetworkX means deserialize-everything-on-startup, no incremental update, no concurrent reads, no ad-hoc query language. Fine as an *export* artifact for visualization only.

## Triggers to revisit (documented for future-us)

Move to KuzuDB (or DuckDB with property-graph extensions) at v2 if:
- Traversal queries deepen past ~3 hops routinely (full transitive closure across packages, cross-domain code-similarity walks).
- Embedding-based similarity edges land and we want vector + graph in one engine.
- *Measured* query latency on the hot path that recursive CTEs can't keep up with — measured, not feared.

None of these are true at v1.

## Impact
- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/concepts/code-graph-schema]]
- [[wiki/concepts/per-repo-layout]]

## Follow-ups
- v2 may add `cg_export_graphml` MCP tool for visualization snapshot from SQLite.
- Per-language `attrs_json` shape lands in a separate spec pass.
- MCP tool surface lands in a separate spec pass.
