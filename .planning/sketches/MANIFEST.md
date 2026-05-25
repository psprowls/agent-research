# Sketch Manifest

## Design Direction

`/graph-wiki:refresh` — a new command that fleshes out under-filled wiki package/domain pages (replaces `TODO` placeholders in `api.md`, `context.md`, `patterns.md`, and `overview.md` File maps), and re-syncs stale pages by writing a diff doc to `raw/diffs/` then dispatching `/graph-wiki:ingest` on it. **Both modes via arg** (sweep vs single-target), **autonomous like /lint** (no per-page prompts, user reviews after), **persistent diff artifacts** (raw/diffs/, audit trail, fits raw/ immutability).

Aesthetic: warm dark terminal — Pat watches the run, so it should feel like a writer's tool, not a CI dashboard.

## Reference Points

- Existing graph-wiki commands: `/graph-wiki:scan` (per-package interactive review), `/graph-wiki:ingest` (source-driven page updates), `/graph-wiki:lint` (autonomous health report)
- Existing page templates in `packages/wiki-io/src/wiki_io/assets/page-templates/package/`: overview.md, api.md, context.md, patterns.md, work.md
- `last_sync_commit` frontmatter convention already on package overview pages
- Iron rule #2: LLM never writes to `<workspace>/raw/` — but refresh, as the tool, may

## Sketches

| # | Name | Design Question | Winner | Tags |
|---|------|----------------|--------|------|
| 001 | refresh-sweep-output | What does `/graph-wiki:refresh` look like top-to-bottom in a terminal? | **A — streaming log** | cli, refresh, output, terminal |
| 002 | refresh-result-block | What does each package's result look like in the refresh final report? | **B — counted summary** | cli, refresh, report, density |
| 003 | refresh-diff-doc | What does `raw/diffs/<pkg>-<from>..<to>.md` contain when refresh writes it for ingest? | **C — hybrid** (tweak: drop Pointers section, inline diff for 1-3 surface-change files) | refresh, diff, raw, ingest, format |

## Key decisions

- **Output cadence:** streaming log over dashboard/quiet-then-report. Trust comes from watching it work; scrollback is the audit trail.
- **Report density:** boxed per-package block with structured counts (filled/diff/ingest/flagged). Names of touched pages reachable via Obsidian, not enumerated in terminal.
- **Diff doc shape:** hybrid — machine-extracted structural sections (commits, stat, exports added/removed, surface-change diffs) anchor the ingestor with verifiable facts; LLM prose (summary, decisions, contradictions) carries the judgment. Ingestor gets accurate `file:line` citations for free.
- **Cost story:** two model passes per stale package (synthesizer → ingestor), but the second pass reads ~6k tokens instead of ~18k of raw diff. Net cheaper than raw-diff path.

## Open questions

- Single-target mode (`/graph-wiki:refresh packages/wiki-io`) — same output format as sweep, just one block. Not separately sketched; revisit during plan-phase if affordances diverge.
- Per-subpage fill strategy (what gets autonomously filled in `api.md` vs `patterns.md` vs `context.md`) — implicitly "do what's mechanically possible." Worth nailing down in plan-phase: `patterns.md` is the hardest and may always end up flagged for review.
- Where in the lifecycle does `last_sync_commit` get bumped — at end of sweep, or per-package as ingest succeeds? Sketches assume per-package on success.
