---
title: lattice-wiki (plugin) — Patterns
category: package
summary: Key patterns and conventions for lattice-wiki
updated: 2026-05-09
tokens: 1038
---

# lattice-wiki (plugin) — Patterns

## Key patterns

- **Three-layer architecture** — `<repo>/` is the source of truth; `<wiki>/raw/` holds immutable ingested sources; `<wiki>/<vault>/` is the LLM-curated Obsidian vault. The plugin only writes to the vault. See [[wiki/concepts/code-wiki-pattern]] and [[wiki/concepts/per-repo-layout]].
- **Adaptive container detection** — `detect_containers.py` classifies top-level repo dirs as `app` / `package` / `domain` / `docs` / `skip` and pins the result in `<wiki>/CLAUDE.md` and `<wiki>/AGENTS.md`. Single-package repos skip `apps/` / `packages/` / `domains/` entirely.
- **Pure-stdlib invariant** — every script under `scripts/` runs on the Python standard library. The pure-stdlib invariant is local to this plugin and preserved even though [[wiki/plugins/lattice-graph/lattice-graph]] takes a binary tree-sitter dep.
- **Cross-plugin entry points** — `ingest_work_item.py` is the strict, non-interactive entry point lattice-workflows calls into per §3.9 Pattern 3. Exit codes follow the §3.8 contract: 0 success, 2 schema rejection, 3 runtime/IO failure.
- **Sync-state gating** — package, app, and `source_type: doc` pages carry `last_sync_commit` + `last_sync_at` so `/lattice-wiki:lint` can flag drift. Writes are gated on a clean working tree on `main` (`git_state.py`); other branches/dirty trees skip the field. `source_type: example` pages explicitly disallow these fields.
- **Lint dispatcher split** — `lint_wiki.py` is a dispatcher; checks live as small modules under `scripts/lint/` (`container.py`, `package_sync.py`, `source_sync.py`, `data_model.py`, `dependency.py`, `domain.py`, `endpoint.py`, `file_map.py`, `example_page.py`, `inspiration_mirror.py`). Adding a check group is a one-file addition.
- **`work/archived/` carve-out** — `lint_wiki.py` walks `<vault>/work/*.md` for the work-namespace lint group but excludes the `<vault>/work/archived/` sub-namespace per the [[wiki/plugins/lattice-work/lattice-work]] archive contract. Archived work items are owned and rendered by `lattice-work:archive`; the wiki's structural lint must not flag them as orphans or miswired.
- **Scan idempotence** — `scan_monorepo.py` compares rendered content against what's on disk and skips writes when only the timestamp would change, keeping re-runs noise-free in git. Dependency-name aggregation includes `external_deps` so the dependency lint layer sees the full set.
- **Templates as canonical schema** — `assets/page-templates/` (13 templates: `app`, `package`, `domain`, `concept`, `concept-pattern`, `dependency`, `endpoint`, `data-model`, `work`, `source`, `source-example`, `architecture`, `adr`) define the body shape for each category and are the single source of truth referenced from `page-formats.md` and the per-category lint modules.
- **Example / Inspirations flow** — `source_type: example` is a separate ingest flow for code samples staged under `raw/examples/`. Instead of `## Appears in sources` bullets on package/domain pages, the ingestor adds bullets under `## Inspirations` and does not bump the `sources:` counter. Each `[[wiki/packages/X]]` / `[[wiki/domains/X]]` bullet on the source's `## Where this could apply` section is mirrored as a bullet under that target's `## Inspirations`. `/lattice-wiki:lint`'s `inspiration_mirror` check enforces both directions.

## Conventions

- Slash commands are thin wrappers that dispatch to a sub-agent or script — business logic stays in the scripts.
- Skills ship as `SKILL.md` + `references/` pairs; the skill body is the primary instructions and references are loaded on demand.
- Plugin assets (bootstrap templates, page templates) live under `skills/lattice-wiki/assets/` and are not distributed separately.
- Test fixtures belong outside the plugin dir (e.g. repo-root `fixtures/`), not inside the plugin tree — they would otherwise ship to users.
- When an example demonstrates a reusable pattern, the ingestor proposes a `concepts/<topic>-pattern.md` page. The `pattern` tag and the `-pattern.md` filename suffix must agree — enforced by `lint/example_page.py`.
