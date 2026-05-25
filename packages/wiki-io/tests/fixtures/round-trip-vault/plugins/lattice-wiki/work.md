---
title: lattice-wiki (plugin) — Work
category: package
summary: Bugs, tech debt, features, and open questions for lattice-wiki
updated: 2026-05-09
tokens: 337
---

# lattice-wiki (plugin) — Work

## Bugs

- [[work/2026-05-04-state-gate-self-inflicted-closure]] — `open` — `compute_state_gate` runs after the dependencies/endpoints index regens in `scan_monorepo.py`, so the gate observes the scanner's own pre-write artifacts as a dirty tree and reports `allowed: false` even on otherwise-clean repos.
- scanner-file-map-renderer-omits-scripts-in-lattice-wiki-package-page — `open` — auto-generated `## File map` block on this page omits `ingest_work_item.py`, `update_index.py`, `wiki_search.py`; surfaced by `/lattice-wiki:lint` 2026-05-05.

## Tech debt

- migrate-wiki-scripts-to-top-level-layout — `open` — move `plugins/lattice-wiki/skills/lattice-wiki/scripts/` → `plugins/lattice-wiki/scripts/` as one transaction; align with §3.8 predictable directory layout.

## Features

- [[work/2026-05-04-plugin-aware-semantic-processing]] — `open` — teach `_collect_claude_plugin` in `scan_monorepo.py` (and the package template) to surface plugin slash commands, subagents, and skills the way Node packages get their `dependencies` extracted.

## Open questions

- (none currently)
