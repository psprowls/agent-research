# Lattice Workspace

> **Workspace path:** `/Users/pat/Personal/deep-agents/lattice`
> **Initialized:** `2026-05-14`

This is a [Lattice](https://github.com/psprowls/lattice) workspace — a per-repo container for plugin-managed knowledge. The Obsidian vault opens here, so the sidebar shows every workspace-level directory side by side.

## Layout

- `wiki/` — code wiki (curated package/domain/concept pages, ADRs, architecture syntheses). Owned by `lattice-wiki`. See [`wiki/CLAUDE.md`](wiki/CLAUDE.md) when present.
- `raw/` — immutable ingested sources (specs, PRs, articles, transcripts). The LLM reads from here but never writes.
- `work/` — unified bug / tech-debt / feature / initiative / spike tracker. Owned by `lattice-workspace`; lifecycle lint and the work-index sidecar live in `lattice-work` (separate plugin).
- `knowledge/` — other plugin-managed knowledge stores.
- `.lattice.yaml` — workspace manifest. Lists registered plugins.
- `.lattice.local.yaml` — per-machine overrides (e.g. `lattice-directory:` to relocate the workspace). Gitignored.

## Plugins installed

<!-- lattice-workspace:auto:plugins:start -->
- `lattice-wiki` — see [`wiki/CLAUDE.md`](wiki/CLAUDE.md)
<!-- lattice-workspace:auto:plugins:end -->

The block above is auto-rendered from `.lattice.yaml` every time `lattice-workspace.init()` runs (i.e. whenever a plugin registers itself with the workspace). Hand-edit anything outside the markers; it will be preserved.

## Conventions for LLM agents

- Treat each plugin's own schema doc as authoritative for its directory. The pointers above lead to the canonical source.
- The `raw/` directory is read-only from the LLM's perspective.
- Cite work items from wiki pages as `[[../work/<slug>]]` (relative to a wiki page).
