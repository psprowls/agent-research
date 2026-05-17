---
title: lattice-work (plugin) — Context
category: package
summary: Concepts, decisions, and ingested sources for lattice-work
updated: 2026-05-09
tokens: 914
---

# lattice-work (plugin) — Context

## Concepts

- [[wiki/concepts/per-repo-layout]] — work items live inside the committed `<repo>/wiki/` vault.
- [[wiki/concepts/per-repo-data-vs-global-tooling-tier]] — per-repo data tier classification.
- [[wiki/concepts/lattice-work-namespace-schema]] — the schema this plugin's lifecycle lint and sidecar generator enforce.

## Decisions

- ADR 0004 — work-tracker-as-consumer-plugin: option 3 (tooling-split, data-shared); hard one-way dep on `lattice-wiki`
- ADR 0005 — per-repo-directory-layout
- ADR 0008 — unified-work-namespace: this plugin owns the 19-rule `work_layer` lifecycle lint and the `<workspace>/work-index.json` sidecar generator
- ADR 0016 — subprocess-cross-plugin-invocation: `regenerate_work_index.py` is invoked by other plugins as a subprocess, never imported
- ADR 0017 — stdlib-only-per-repo-tier: stdlib-only Python (no PyYAML, no pytest); shared per-repo-tier constraint
- [[wiki/adrs/0004-filesystem-affects-resolution-v1]] — v1 `affects:` matched by filesystem path prefix only; graph-aware resolution deferred

## Sources

- 2026-05-lattice-ecosystem-review — proposes the planning/intent surface; left "separate plugin or tightened wiki schema?" open (resolved as separate plugin in §3.7)
- 2026-05-lattice-ecosystem-architecture-refinements
- 2026-05-architecture-3.1-plugin-topology — per-repo data tier classification; ownership question deferred to §3.7
- 2026-05-architecture-3.7-work-tracker-boundary — option 3 resolution; schema-vs-tooling split; hard dep on wiki; v1 slash command surface
- 2026-05-architecture-3.8-contracts-between-layers — confirms hard dep is the only one in the ecosystem; `${LATTICE_WORK_ROOT}/scripts/regenerate_work_index.py` cross-plugin entry point; `sidecar-missing` first-lint behavior
- 2026-05-architecture-3.9-lattice-workflows-seam — `lattice-workflows` consumes the sidecar via `/lattice-workflows:next` (prioritization) and `:status` (rollup); workflow triggers `regenerate_work_index.py` after each work-page mutation
- 2026-05-lattice-ecosystem-schema-refinements — §2.4 unified `work/` namespace + 7-state lifecycle + 18-rule `work_layer` lint group; this plugin owns the lint and the sidecar generator
- 2026-05-work-tracker-v1-design — v1 surface (4 commands + skill); 18 lifecycle rules grouped six ways; deterministic sidecar properties; subprocess-not-import; stdlib-only; filesystem-only `affects:` resolution
- 2026-05-archive-resolved-work-items — `<workspace>/work/archived/` sub-namespace; `:archive` slash command (sweep + targeted modes); 19th `archive-eligible` info-severity lint rule; carve-out in `lattice-wiki` to exclude `archived/` from base structural lint walks

## Belongs to domain

(none)

## Used by

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — `/lattice-workflows:next` reads the sidecar for prioritization; `/lattice-workflows:status` for rollup; `/lattice-workflows:file-work-item` calls `regenerate_work_index.py` after the wiki's `ingest_work_item.py` succeeds. All gracefully degrade when this plugin is absent.

## Related dependencies

- [[wiki/plugins/lattice-wiki/lattice-wiki]] — hard one-way dependency; `lattice-work` reads/writes through the vault that `lattice-wiki` owns. `lattice-wiki` does not depend on `lattice-work`.
