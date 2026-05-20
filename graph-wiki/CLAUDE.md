# Graph-Wiki Workspace

> **Workspace path:** `/Users/pat/Personal/deep-agents/graph-wiki`
> **Initialized:** `2026-05-18`

This is a graph-wiki workspace — a per-repo container for plugin-managed knowledge. The Obsidian vault opens here, so the sidebar shows every workspace-level directory side by side.

## Layout

- `wiki/` — code wiki (curated package/domain/concept pages, ADRs, architecture syntheses). Owned by `code-wiki-agent`. See [`wiki/CLAUDE.md`](wiki/CLAUDE.md) when present.
- `raw/` — immutable ingested sources (specs, PRs, articles, transcripts). The LLM reads from here but never writes.
- `work/` — unified bug / tech-debt / feature / initiative / spike tracker. Schema owned by `workspace-io`; lifecycle (lint, sidecar, archive, status) owned by `code-wiki-agent`.
- `knowledge/` — other plugin-managed knowledge stores.
- `.graph-wiki.yaml` — workspace manifest. Lists registered plugins.
- `.graph-wiki.local.yaml` — per-machine overrides (e.g. `graph-wiki-directory:` to relocate the workspace). Gitignored.

## Plugins installed

<!-- workspace-io:auto:plugins:start -->
- `graph-wiki-agent` — see [`wiki/CLAUDE.md`](wiki/CLAUDE.md)
<!-- workspace-io:auto:plugins:end -->

The block above is auto-rendered from `.graph-wiki.yaml` every time `workspace-io.init()` runs (i.e. whenever a plugin registers itself with the workspace). Hand-edit anything outside the markers; it will be preserved.

## Conventions for LLM agents

- Treat each plugin's own schema doc as authoritative for its directory. The pointers above lead to the canonical source.
- The `raw/` directory is read-only from the LLM's perspective.
- Cite work items from wiki pages as `[[../work/<slug>]]` (relative to a wiki page).
