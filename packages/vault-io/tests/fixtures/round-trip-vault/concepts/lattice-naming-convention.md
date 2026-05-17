---
title: lattice-* naming convention
category: concept
summary: All plugins in the ecosystem ship under the `lattice-` prefix. Lineage to upstream forks is preserved through attribution, not the plugin name.
tags: [naming, ecosystem, conventions]
updated: 2026-05-04
tokens: 616
---

# lattice-* naming convention

## Definition
Every Claude Code plugin in this ecosystem is named `lattice-<concern>` — for example `lattice-wiki`, `lattice-workflows`, `lattice-graph`. The prefix groups the plugins under one ecosystem identity in the marketplace and at install time, and gives each plugin's slash-commands and subagents a predictable namespace (`/lattice-wiki:<command>`, `lattice-experts:<agent>`).

## Motivation
- A single, recognizable prefix makes the ecosystem discoverable in plugin marketplaces.
- Claude Code automatically namespaces slash-commands and subagents by plugin name; sharing a prefix groups them visually.
- Upstream forks (notably [`obra/superpowers`](https://github.com/obra/superpowers) → `lattice-workflows`) keep lineage in the README and LICENSE — not the name — so the new identity is unambiguous.

## Shape

| Old name | New name | Status |
|---|---|---|
| `llm-code-wiki` | `lattice-wiki` | rename complete |
| `claude-superpowers` | `lattice-workflows` | rename complete |
| _(formerly `claude-superpowers-knowledge`)_ | `lattice-experts` | rename complete (working name) |
| _(new)_ | `lattice-graph` | shipped |
| _(new)_ | `lattice-work` | shipped |

## Used in
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — renamed from `llm-code-wiki`
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — renamed from `claude-superpowers`; drops the "superpowers" word
- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/plugins/lattice-work/lattice-work]]

## Related patterns
- [[wiki/concepts/per-repo-layout]] — naming applies to plugins; per-repo dirs (`wiki/`, `.lattice/`) are a separate convention.
- [[wiki/concepts/lattice-workflows-observability-gate]] — extends the `lattice-` prefix to env-vars: `LATTICE_<PLUGIN_UPPER>_OBSERVABILITY` aligns with the `${LATTICE_<NAME>_ROOT}` discovery shape from [[wiki/concepts/lattice-cross-plugin-contract]].

## Open questions / gotchas
- The `lattice-experts` name is still a working name — final scope and identity may shift.
- Bare "superpowers" references inside `lattice-workflows/` are being audited; only true upstream attribution to `obra/superpowers` keeps the word.
