---
name: sketch-findings-agent-research
description: Validated design decisions for the /graph-wiki:refresh command (sweep + targeted modes, autonomous run with post-hoc review, diff doc to raw/ then dispatch ingest). Auto-loaded during plan-phase or implementation work on graph-wiki refresh.
---

<context>
## Project: agent-research

These findings cover the design of `/graph-wiki:refresh` — a command that fleshes out under-filled wiki package/domain pages (replacing `TODO` placeholders in `api.md`, `context.md`, `patterns.md`, and `overview.md` File maps) and re-syncs stale pages by writing a synthetic source to `raw/diffs/` then dispatching `/graph-wiki:ingest` on it.

Refresh fills the gap between `/graph-wiki:scan` (stubs pages, frontmatter-only updates) and `/graph-wiki:ingest` (source-driven page rewrites).

Sketch session wrapped: 2026-05-19.
</context>

<design_direction>
## Overall Direction

- **Both modes via arg.** Bare `/graph-wiki:refresh` sweeps the whole vault. `/graph-wiki:refresh <path>` targets one package/domain. Same report format for both.
- **Autonomous like `/graph-wiki:lint`.** No per-page prompts during the run. User reviews artifacts after. Pages drafted with low LLM confidence get marked `~` and explicitly re-listed in the closing block.
- **Persistent diff artifacts.** Stale-package diffs are written as durable files under `raw/diffs/<pkg>-<from>..<to>.md` before ingest is dispatched. Audit trail. Fits `raw/` immutability (refresh writes; the LLM inside refresh doesn't).
- **Aesthetic: warm dark terminal.** This is a writer's tool, not a CI dashboard. Streaming log, scrollback as audit trail.
- **Hybrid diff doc.** Machine-extracted structural sections (commits, stat, exports added/removed, surface-change diffs) give the ingestor verifiable file:line citations; LLM prose carries judgment (summary, decisions, contradictions). Two model passes per stale package (cheap synthesizer → ingestor); second pass reads ~6k tokens instead of ~18k of raw diff.
</design_direction>

<findings_index>
## Design Areas

| Area | Reference | Key Decision |
|------|-----------|--------------|
| Refresh command UX | `references/refresh-command-ux.md` | Streaming log + counted per-package summary + hybrid diff doc with inlined surface-change diffs |

## Theme

The terminal theme used for all sketches is at `sources/themes/default.css` — warm dark palette, JetBrains Mono, `pre-wrap` terminal frames with chrome dots and titles.

## Source Files

All three sketch HTML files preserved in `sources/` with every variant (not just the winners) so the rejected directions stay reachable:

- `sources/001-refresh-sweep-output/` — streaming log (winner) vs live status block vs quiet-then-report
- `sources/002-refresh-result-block/` — terse one-liner vs counted summary (winner) vs full wikilink dump
- `sources/003-refresh-diff-doc/` — raw git diff vs curated semantic delta vs hybrid (winner, with surface-change diffs tweak)
</findings_index>

<metadata>
## Processed Sketches

- 001-refresh-sweep-output
- 002-refresh-result-block
- 003-refresh-diff-doc
</metadata>
