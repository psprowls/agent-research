# Sketch Wrap-Up Summary

**Date:** 2026-05-19
**Sketches processed:** 3
**Design areas:** Refresh command UX
**Skill output:** `./.claude/skills/sketch-findings-deep-agents/`

## Included Sketches

| # | Name | Winner | Design Area |
|---|------|--------|-------------|
| 001 | refresh-sweep-output | A — Streaming log | Refresh command UX |
| 002 | refresh-result-block | B — Counted summary | Refresh command UX |
| 003 | refresh-diff-doc | C — Hybrid (with surface-change diffs tweak) | Refresh command UX |

## Excluded Sketches

None — all three sketches packaged.

## Design Direction

`/graph-wiki:refresh` is a new command that fills the gap between `/graph-wiki:scan` (stubs only) and `/graph-wiki:ingest` (source-driven rewrites): it fleshes out under-filled package/domain subpages and re-syncs stale ones via a synthetic diff source.

Two modes via arg (sweep / targeted). Autonomous run with post-hoc review. Persistent diff artifacts in `raw/diffs/` that the existing ingest pipeline consumes unchanged.

## Key Decisions

- **Output cadence** — streaming log; trust comes from watching it work. Scrollback is the audit trail.
- **Per-package reporting** — boxed block with structured counts (`filled`/`range`/`diff`/`ingest`/`flagged`) plus a brief prose hint. Middle density; scannable at 12 packages.
- **Diff doc shape** — hybrid markdown: machine-extracted structural sections (commits, stat, exports added/removed, surface-change diffs for top 1-3 files by `|adds|+|removes|`) anchor the ingestor with verifiable `file:line` citations; LLM prose carries summary/decisions/contradictions.
- **Cost story** — two model passes per stale package (cheap synthesizer → ingestor). Second pass reads ~6k tokens vs ~18k for raw diff. Net cheaper than the raw-diff path.
- **Sync-state semantics** — `last_sync_commit` bumps per-package on ingest success, gated on clean working tree + HEAD on `main` (same gate `/graph-wiki:scan` already enforces).
- **Aesthetic** — warm dark terminal palette. Writer's tool, not CI dashboard.

## Iron-rule alignment

- Rule 1 (code is source of truth) — machine sections of the diff doc are literally code; LLM prose only annotates.
- Rule 2 (LLM never writes to `raw/`) — refresh-the-tool writes; the synthesizer LLM runs inside refresh and returns prose, never touches the filesystem directly. Worth documenting explicitly in the command spec.
- Rule 5 (every claim cites a source or code path) — directly motivates the hybrid diff doc's structural sections.

## Open questions deferred to plan-phase

- Per-subpage fill strategy: `patterns.md` may always end up flagged for review (judgment-heavy).
- Targeted-mode format: assumed identical to sweep; validate during plan.
- `last_sync_commit` bump timing: per-package on success (simple) vs end-of-sweep transactional (rollback-safe).
