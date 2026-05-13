---
title: Code-graph schema (nodes / edges / metadata)
category: concept
summary: Two-table SQLite schema for lattice-graph — nodes, edges, metadata; recursive CTEs for bounded traversal; per-language detail in attrs_json.
tags: [schema, sqlite, code-graph, storage]
updated: 2026-05-11
tokens: 1057
---

# Code-graph schema (nodes / edges / metadata)

## Definition
The canonical SQLite schema backing [[wiki/plugins/lattice-graph/lattice-graph]]. Two tables (`nodes`, `edges`) plus `metadata`. Per-language detail lives in `attrs_json` blobs; the core graph stays language-agnostic.

## Shape

```sql
CREATE TABLE nodes (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,        -- file | package | class | function | method
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,        -- file path; null for package nodes
    line        INTEGER,              -- definition line; null where N/A
    attrs_json  TEXT                  -- kind-specific attrs (signature, visibility, etc.)
);
CREATE INDEX idx_nodes_kind_name ON nodes(kind, name);
CREATE INDEX idx_nodes_path      ON nodes(path);

CREATE TABLE edges (
    src         INTEGER NOT NULL REFERENCES nodes(id),
    dst         INTEGER NOT NULL REFERENCES nodes(id),
    kind        TEXT NOT NULL,        -- contains | imports | calls | exports
    attrs_json  TEXT,
    PRIMARY KEY (src, dst, kind)
);
CREATE INDEX idx_edges_dst_kind ON edges(dst, kind);
CREATE INDEX idx_edges_src_kind ON edges(src, kind);

CREATE TABLE metadata (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
-- rows: schema_version, last_indexed_commit, last_indexed_at, languages_indexed
```

## Node kinds
Core v1 set: `file | package | class | function | method`. v0.2.0 added `wiki_page` (workspace-relative path in `name`, no schema migration — the `kind` column is open) via [[wiki/sources/2026-05-lattice-graph-core-documents-edge]]. Adding a kind that requires new columns or indexes would bump `schema_version` and force a full rebuild; `wiki_page` did not because it reuses the existing columns.

## Edge kinds
Core v1 set: `contains | imports | calls | exports`. v0.2.0 added `documents` (package → `wiki_page`) via [[wiki/sources/2026-05-lattice-graph-core-documents-edge]]. The MCP tools surface exposes traversal tools for three of the v1 kinds; `contains` is consumed via `cg_describe_*` digests, not as standalone traversal.

## Recursive CTE example — transitive callers depth ≤ 3

```sql
WITH RECURSIVE callers(id, depth) AS (
    SELECT src, 1 FROM edges
        WHERE dst = (SELECT id FROM nodes WHERE kind = 'function' AND name = 'foo')
          AND kind = 'calls'
    UNION
    SELECT e.src, c.depth + 1 FROM edges e JOIN callers c ON e.dst = c.id
        WHERE e.kind = 'calls' AND c.depth < 3
)
SELECT n.kind, n.name, n.path, n.line, MIN(c.depth) AS depth
FROM callers c JOIN nodes n ON c.id = n.id
GROUP BY n.id;
```

## `attrs_json` convention
- Per-language detail lives here; consumers do `attrs.get("type_params", [])` rather than expecting universal fields.
- Schema migrations bump `metadata.schema_version`; full rebuild on bump (cheap at our cardinality).

## What the schema does NOT capture
- **No source text** — graph is an index; consumers read files for content.
- **No version history** — current/last-indexed commit only.
- **No similarity edges** — v2 deferred.
- **No write API for consumers** — graph is mechanically produced; single writer is `cg update` itself.

## Used in
- [[wiki/plugins/lattice-graph/lattice-graph]] — sole producer/owner

## Related patterns
- [[wiki/concepts/per-repo-layout]] — schema lives at `<workspace>/.graph/code.db` (default: `<repo>/lattice/.graph/code.db`)

## Schema fidelity is a hard goal of the parser package

The [[wiki/packages/lattice-source-parser/lattice-source-parser]] design treats this schema as a stable contract. `to_graph_records()` emits records whose shape (kind, name, path, attrs_json) maps 1:1 onto the table columns above. Identity inside the projection is `(kind, name, path)` tuples — integer `id`s are an implementation detail of the *store* and are allocated at upsert time by [[wiki/packages/lattice-graph-core/lattice-graph-core]].

The package never touches SQLite. The plugin owns ID allocation, transactions, manifest scanning into `kind: package` nodes, and cross-file resolution.

## Decisions
- [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]]
