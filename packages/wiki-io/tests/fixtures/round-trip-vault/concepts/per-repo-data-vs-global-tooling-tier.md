---
title: Per-repo data tier vs. global tooling tier
category: concept
summary: The five lattice plugins split into two operational tiers — per-repo data (vault, graph, work tracker) and global tooling (workflows, experts).
tags: [architecture, ecosystem, lattice, tiering]
sources: 1
updated: 2026-05-09
tokens: 844
---

# Per-repo data tier vs. global tooling tier

## Definition
The five `lattice-*` plugins split cleanly into two tiers based on where their data and content live, and what their cardinality + cadence look like.

| Tier | Plugins | Data location | Cardinality / cadence |
|---|---|---|---|
| **Per-repo data** | [[wiki/plugins/lattice-wiki/lattice-wiki]], [[wiki/plugins/lattice-graph/lattice-graph]], [[wiki/plugins/lattice-work/lattice-work]] | inside the consumer repo (`<repo>/lattice/` workspace root; wiki at `lattice/wiki/`, graph at `lattice/.graph/`) | per-repo; cadence varies (per-commit graph, per-ingest wiki, per-planning-session work) |
| **Global tooling** | [[wiki/plugins/lattice-workflows/lattice-workflows]], lattice-experts | installed at user-level; applies across all repos | global; configuration cadence (rare) |

## Motivation
- The data plugins read/write per-repo paths and need explicit path ownership to avoid collisions (path table in §3.8). They are mutually optional but compose by design.
- The global tooling plugins ship skills/hooks/subagent definitions consumed across every project; they don't carry per-repo data and don't require any peer plugin to be installed.

## Shape

```
~/.claude/plugins/                 ← global tooling tier installs here
├── lattice-workflows/
└── lattice-experts/

<repo>/                            ← per-repo data tier writes here
└── lattice/                       ← single workspace root (DEFAULT_WORKSPACE_NAME)
    ├── wiki/                      ←   lattice-wiki + work-tracker substrate
    ├── work/                      ←   work items
    └── .graph/
        └── code.db                ←   lattice-graph SQLite store
```

Per-repo data tier paths are governed by `raw/specs/architecture/3.8-contracts-between-layers.md`. Global tooling tier consumption seam is governed by `raw/specs/architecture/3.9-lattice-workflows-seam.md` and `raw/specs/architecture/3.10-lattice-experts-design.md`.

## Composition

A user can install plugins in any order; layered opt-in:

1. `lattice-workflows` alone → engineering-discipline framework on every project.
2. + `lattice-wiki` → per-repo knowledge substrate on top.
3. + `lattice-graph` → graph queries available; wiki integrates if both installed.
4. + `lattice-work` → planning surface; consumes wiki vault for storage.
5. + `lattice-experts` → role-aware knowledge skills slot into workflow's dispatch templates.

Each layer degrades gracefully when its consumers are absent — the contract is detailed in [[wiki/concepts/lattice-cross-plugin-contract]].

## Used in
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — per-repo data
- [[wiki/plugins/lattice-graph/lattice-graph]] — per-repo data
- [[wiki/plugins/lattice-work/lattice-work]] — per-repo data
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — global tooling
- lattice-experts — global tooling

## Related patterns
- [[wiki/concepts/per-repo-layout]] — what per-repo data tier writes inside the repo
- [[wiki/concepts/plugin-deployment-shapes]] — shape F is the canonical per-repo data deployment

## Sources
- 2026-05-architecture-3.1-plugin-topology
