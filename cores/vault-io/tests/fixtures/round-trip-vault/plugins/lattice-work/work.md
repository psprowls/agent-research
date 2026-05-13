---
title: lattice-work (plugin) — Work
category: package
summary: Open questions and deferred work for lattice-work
updated: 2026-05-09
tokens: 465
---

# lattice-work (plugin) — Work

## Bugs

(none tracked)

## Tech debt

- [[work/2026-05-09-adjust-linter-for-work-sibling-to-vault]] — linter path assumptions need updating for work/ as workspace sibling rather than vault subdir

## Features

- [[work/2026-05-04-implement-work-status-transitions]] — status transition support
- [[work/2026-05-04-plugin-aware-semantic-processing]] — plugin-aware semantic processing

## Open questions

- Whether work-tracker also queries [[wiki/plugins/lattice-graph/lattice-graph]] for `affects:` resolution against the graph (instead of filesystem) — v1 cuts this (filesystem-only). Re-open when the graph plugin exists; lift to a wiki ADR when the fallback lands.
- Whether to wire `archive-eligible` lint findings into `:status`'s "stuck" section, or keep them lint-only. Default: lint-only.
- Whether to add `closed_at:` frontmatter — rejected for v1 in favor of reusing `updated:`. Revisit if the typo-resets-the-clock failure mode bites.
- Naming for `--min-age-days` vs `--age-days` vs `--older-than-days` on `:archive`.

### Deferred commands

- `/lattice-work:next` — prioritization belongs to `lattice-workflows`. Lands as `/lattice-workflows:next`.
- `/lattice-work:create` — conflicts with `lattice-wiki:ingest` and Obsidian; skip until friction shows.
- `/lattice-work:transition` — workflows owns transitions.
- `/lattice-work:init` — first `:lint` covers bootstrap via `sidecar-missing` warning.
- `/lattice-work:restore` — manual recipe in v1 (`git mv` + `:regen-index`); promote to a command if friction shows.
- Graph-aware `affects:` resolution — filesystem-only in v1; lift to a wiki ADR when the graph fallback lands.
