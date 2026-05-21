---
created: 2026-05-21
resolved: 2026-05-21
phase: 26
status: resolved
---

# Phase 26 — packages/prompt-sources/ deletion

The `packages/prompt-sources/` upstream-snapshot tree is removed. All anchor pointers
(provenance comments, source_anchor literals, rubric headers, prose Anchors lines)
re-pointed to canonical surfaces:
- `plugins/graph-wiki/` (most pointers)
- `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` (log_format, style_rules)
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/` (code_reader, synthesizer)

Brand-gate CHECK 6 blocks reintroduction of the literal `packages/prompt-sources`
under agents/, packages/, plugins/, scripts/, tests/.

Resolved by Phase 26 (PLANs 01-04). See `.planning/phases/26-plugin-prompt-source-mirror-sync/`.
