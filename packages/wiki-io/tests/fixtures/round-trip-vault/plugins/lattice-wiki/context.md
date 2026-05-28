---
title: lattice-wiki (plugin) — Context
category: package
summary: Concepts, decisions, and ingested sources for lattice-wiki
updated: 2026-05-09
tokens: 1185
---

# lattice-wiki (plugin) — Context

## Concepts

- [[wiki/concepts/code-wiki-pattern]]
- [[wiki/concepts/lattice-naming-convention]]
- [[wiki/concepts/per-repo-layout]]
- [[wiki/concepts/lattice-work-namespace-schema]] — the unified `work/` schema, frontmatter, lifecycle, sidecar contract
- [[wiki/concepts/lattice-page-body-table-conventions]] — `## Plan` / `## Endpoints` / `## Fields` table grammar
- [[wiki/concepts/lattice-dependencies-tiering]] — `dependencies/index.md` regen + opt-in detail + `kind` discriminator
- [[wiki/concepts/lattice-vault-terminology]] — canonical glossary; pending renames (`domain`, `container` umbrella)
- wiki-cites-graph-not-duplicates — consumer-side relationship with [[wiki/plugins/lattice-graph/lattice-graph]]: graph-aware lint with filesystem fallback; wiki cites graph rather than duplicating it

## Decisions

- [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]] — renamed from `llm-code-wiki`
- [[wiki/adrs/0002-explicit-graph-update-lifecycle]] — graph stays a separate plugin; this plugin is consumer of its surface
- ADR-0004 (work-tracker-as-consumer-plugin) — work-tracker is a separate consumer plugin; this plugin owns the work schema, template, base lint, and the `migrate_to_work_namespace.py` migrator
- [[wiki/adrs/0005-sourcetree-sole-domain-model]] — owns `<repo>/wiki/`
- ADR-0008 (unified-work-namespace) — this plugin owns the unified `work/` schema, template, base lint, and migrator
- ADR-0010 (lint-dispatcher-split) — `lint_wiki.py` splits into a dispatcher + per-check-group modules under `scripts/lint/`

## Sources

- 2026-05-lattice-ecosystem-review — foundational review; diagnoses live-vault category asymmetry and prescribes the schema/topology direction
- 2026-05-lattice-ecosystem-architecture-refinements — establishes the `lattice-` prefix, per-repo layout, and ecosystem topology
- 2026-05-architecture-3.1-plugin-topology — confirms per-repo data tier classification; defers ownership of `work/` to §3.7
- 2026-05-architecture-3.6-wiki-graph-integration — integration with `lattice-graph`: frontmatter schema drops, graph-aware lint dispatch
- 2026-05-architecture-3.7-work-tracker-boundary — wiki owns the work schema + template + base lint + migration; work-tracker is downstream consumer
- 2026-05-architecture-3.8-contracts-between-layers — `init_vault.py` seeds `.gitignore` with `.lattice/graph/code.db*` entries; sets `${LATTICE_WIKI_ROOT}` on activation
- 2026-05-architecture-3.9-lattice-workflows-seam — wiki owns `ingest_work_item.py` as the cross-plugin entry point that workflow's `/lattice-workflows:file-work-item` calls into; status transitions skip ingest (direct frontmatter edits)
- 2026-05-lattice-ecosystem-schema-refinements — §2 schema work: unified `work/` namespace (this plugin owns the schema/template/migrator), dependencies tiering, terminology glossary
- 2026-05-lattice-wiki-schema-refinements-landing — implementation plan for the §2 landing in this plugin's code (init_vault, templates, lint split, index regen)
- 2026-04-lattice-workflows-per-package-sync-state — adds `last_sync_commit` + `last_sync_at` to package/app/source frontmatter; gated state writes; replaces `source_mtime` for in-repo doc sources
- 2026-05-wiki-workflows-seam-parity — wiki-side of the wiki↔workflows seam: `ingest_work_item.py` one-shot non-interactive script (cross-plugin entry point per §3.9 Pattern 3, exit codes per §3.8) + `LATTICE_WIKI_ROOT` env-var declaration on activation
- 2026-05-archive-resolved-work-items — establishes the `work/archived/` sub-namespace owned by [[wiki/plugins/lattice-work/lattice-work]]; this plugin's `lint_wiki.py` excludes that path from its work-namespace lint walks per the archive contract

## Belongs to domain

(none)

## Used by

- [[wiki/plugins/lattice-work/lattice-work]] — hard one-way dep; reads `<vault>/work/*.md`, writes `<vault>/work-index.json`. Schema and migration script live here.
- [[wiki/plugins/lattice-curator/lattice-curator]] — the curator's wiki `Source` adapter walks `<vaultDir>/**/*.md` and turns frontmatter into a flat catalog feeding the [[wiki/concepts/two-pass-context-curation|two-pass retriever]].

## Related dependencies

- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — shared pure-Python IO + analysis library backing this plugin (template assets, lint, scan, ingest, layout)
