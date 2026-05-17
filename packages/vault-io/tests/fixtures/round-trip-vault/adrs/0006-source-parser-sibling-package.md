---
title: "ADR-0006: lattice-source-parser ships as a sibling Python package free of storage and transport concerns"
category: adr
summary: The parser lives at packages/lattice-source-parser/, depends only on tree-sitter + tree-sitter-language-pack, and has no knowledge of SQLite, MCP, Claude Code plugins, or ${LATTICE_*} env vars; any Python project can depend on it standalone.
adr_id: "0006"
status: accepted
decision_date: 2026-05-07
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [adr, lattice-source-parser, lattice-graph, packages, distribution, separation-of-concerns]
updated: 2026-05-07
tokens: 596
---

# ADR-0006: lattice-source-parser ships as a sibling Python package free of storage and transport concerns

**Status:** accepted (2026-05-07)

## Context

The original spec called for a parser tier inside [[wiki/plugins/lattice-graph/lattice-graph]]. Bundling the parser inside the plugin would couple it to SQLite, MCP, the Claude Code plugin loader, and `${LATTICE_*}` env vars — none of which other potential consumers (chunkers, RAG indexers, eval harnesses, ad-hoc scripts) need.

## Decision

[[wiki/packages/lattice-source-parser/lattice-source-parser]] ships as a **sibling Python package** at `packages/lattice-source-parser/`. It depends only on `tree-sitter` and `tree-sitter-language-pack`. It has **no knowledge** of SQLite, MCP, Claude Code plugins, or `${LATTICE_*}` env vars. Any Python project — not just `lattice-graph` — can `pip install lattice-source-parser` and use it standalone.

The seam between package and plugin sits between the package's `GraphRecords` projection and the plugin's SQLite upsert.

## Consequences

- The parser is reusable across any consumer that needs tree-sitter-backed parsing — RAG indexers, chunkers, evals, future plugins.
- The package boundary forces clean separation: storage, transport, and lifecycle concerns cannot leak into parsing code.
- `lattice-graph` becomes a thin consumer of the package — its own code stays focused on storage, lifecycle, and adapters.
- The pure-stdlib invariant is **not** preserved here — the package takes a binary tree-sitter dep. The break is intentional and confined (see ADR-0017 on stdlib-only tiers).
- Two package codebases to maintain (parser + graph-core) instead of one. Acceptable; the boundary repays the cost.

## Related

- [[wiki/packages/lattice-source-parser/lattice-source-parser]]
- [[wiki/packages/lattice-graph-core/lattice-graph-core]]
- [[wiki/adrs/0005-sourcetree-sole-domain-model]]
