---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Graph-Wiki Port & Debt Cleanup
status: executing
stopped_at: Phase 16 context gathered
last_updated: "2026-05-19T15:37:58.061Z"
last_activity: 2026-05-19 -- Phase 16 planning complete
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 20
  completed_plans: 19
  percent: 95
---

# Project State: deep-agents

**Last updated:** 2026-05-17
**Updated by:** gsd-roadmapper (milestone v1.2 roadmap created — Phases 11-16)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-17 after milestone v1.1 SHIPPED)

**Core Value:** Faithfully reproduce lattice-wiki's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 15 — wiki-self-update

**North Star:** `code-wiki-agent query "..."` returns answers as good as today's lattice-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: 15 — COMPLETE
Plan: 1 of 1 (complete)
Status: Ready to execute
Last activity: 2026-05-19 -- Phase 16 planning complete

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.0) | 5 |
| Phases complete (v1.0) | 5 |
| Phases total (v1.1) | 5 |
| Phases complete (v1.1) | 5 |
| Requirements total (v1.1) | 29 |
| Requirements complete (v1.1) | 29 |
| Plans written (v1.1) | 39 |
| Plans complete (v1.1) | 39 |
| Phases total (v1.2) | 6 |
| Phases complete (v1.2) | 0 |
| Requirements total (v1.2) | 30 |
| Requirements complete (v1.2) | 0 |
| Plans written (v1.2) | 0 |
| Plans complete (v1.2) | 0 |

---

## Accumulated Context

### Key Decisions

(Full log lives in `PROJECT.md → Key Decisions`. v1.0 outcomes:)

- ✓ SubagentPool over deepagents SubAgentMiddleware — validated Phase 2 (deepagents #694/#1698 confirmed; raw asyncio path shipped)
- ✓ Vault round-trip golden test gates write code — validated Phase 1 (148-page real-vault fixture passes byte-identical)
- ✓ Hybrid search via BM25 + Titan v2 embeddings + RRF — validated Phase 3
- ✓ Eval harness ships before swap (Phase 4 before sweep) — validated; sweep deferred to v1.1
- ✓ python-frontmatter read-only; writes via ported layout_io.py — validated Phase 1
- ✓ Single `wiki_ingest` MCP tool with discriminator (not two) — validated Phase 5

v1.1 roadmap decisions:

- PORT + EVAL-Q (Phase 6) grouped together: divergence eval is the completion gate for the port; splitting would leave Phase 6 with no observable signal
- SWEEP (Phase 7) blocked on Phase 6: sweep must measure the post-port agent, not the v1.0 baseline — hard constraint
- MCP-CAN + DACLI (Phase 8) grouped together: both are host-reliability work, both independent of PORT/SWEEP — can start in parallel with Phase 6
- OBS (Phase 9) stands alone: trace/observability is a distinct domain from reliability; small but coherent deliverable

v1.2 roadmap decisions:

- Phase 11 (workspace-io port) ships first because every later phase writes into or rebrands the new package layout — porting first avoids merging into a name about to change
- Phase 12 bundles drift backport + rebrand (BACKPORT-01..04, BRAND-01/02/04) because both edit the same vault-io surface; splitting would cause merge friction
- BRAND-03 (wiki self-update) deferred to its own Phase 15 — it must run AFTER the plugin port lands so the wiki captures the full rebrand surface; scanning mid-milestone would re-trigger after plugin work
- Phase 13 is a spec-only phase for plugin scoping (PLUGIN-01) — the "what do slash commands shell out to?" question must be answered before any plugin code is moved (Phase 14)
- Carry-forward debt (TRACE-FU/SWEEP-FU/MCP-CAN/MODEL-FU) bundled into Phase 16 — most items are independent of port work and could parallel, but SWEEP-FU-04 needs the fresh-package vault from Phase 12, so the bundle slots after port/rebrand cleanly

Phase 15 execution outcomes (2026-05-19):

- BRAND-03 closed: vault `~/Personal/wiki/deep-agents` re-scanned + OTel re-ingested + librarian query run via Bedrock CLI with Claude profile (Haiku 4.5 fan-out + Sonnet 4.6 reasoning). SC#1/#2/#3 evidence in `15-VERIFICATION.md`.
- 3 operational deviations encountered and auto-fixed inline (Rule 1): `--config` does not propagate `vault_path` to subcommands (always pass `--vault` explicitly); wiki CLAUDE.md layout block had stale `cores/` container name (fixed to `packages/`); BM25 index requires manual rebuild after scan. Documented in `15-VERIFICATION.md` Deviation section.

### Active TODOs

- Run `/gsd:verify-phase 15` to confirm Phase 15 closure and produce phase audit
- Run `/gsd:plan-phase 16` for carry-forward debt cleanup (Phase 16 is the only remaining v1.2 phase)

### Blockers

(None.)

### Research Flags

(None — work is internal port/rebrand of known lattice code per thread `next-milestone-planning`; spike 002 already inventoried source modules.)

---

## Deferred Items

Items acknowledged and deferred at v1.1 milestone close on 2026-05-17 (some re-addressed by v1.2 Phase 16):

| Category | Item | Status |
|----------|------|--------|
| uat_gap | Phase 06 06-UAT.md | diagnosed (0 open scenarios — metadata only) |
| uat_gap | Phase 08 08-HUMAN-UAT.md | partial (2 pending scenarios — SC#1 + SC#2 sign-offs) |
| verification_gap | Phase 08 08-VERIFICATION.md | human_needed (2 documented scope narrowings — addressed by MCP-CAN-01 in Phase 16) |
| thread | next-milestone-planning | closed (promoted into v1.2 roadmap) |

Full context: `.planning/milestones/v1.1-MILESTONE-AUDIT.md`

---

## Session Continuity

**Last session:** 2026-05-19T14:47:14.323Z
**Stopped at:** Phase 16 context gathered
**Resume file:** .planning/phases/16-carry-forward-debt-cleanup/16-CONTEXT.md

**Critical context for next session:**

- v1.0 shipped: 5 phases, 25 plans, 67/67 requirements; v1.1 shipped: 5 phases, 39 plans, 29/29 requirements. Full retrospective in `.planning/RETROSPECTIVE.md`
- v1.2 scope: workspace-io port (M1) + drift backport + rebrand (M2) + plugin port (M3) + carry-forward debt; 30 requirements across 6 phases (11-16)
- Source code for port work lives in `/Users/pat/Personal/lattice/packages/{lattice-workspace,lattice-wiki-core}/` and `/Users/pat/Personal/lattice/plugins/lattice-wiki/`
- Spike 002 (validated) is the drift map: `.planning/spikes/002-*` — leave-alone decisions for `git_state`, `append_log`, `update_index`, `update_tokens`, `ingest_work_item`, `layout_io`, `detect_containers`, `scan_monorepo`, `ingest_source`
- Out of scope for v1.2: `work/` subsystem (GSD covers it), package-family monorepo support (different approach planned), OSS release prep (→ v2.0), Nyquist retro (→ v1.3)
- Workspace renamed: `cores/` → `packages/` (commit `c5a47ba`). Vault writes still go through `packages/vault-io/layout_io.py` — do not introduce `yaml.dump` anywhere in the write path
- MCP stdout discipline (`_StdoutGuard`) is non-negotiable; any new MCP tools must register *after* `mcp = FastMCP(...)` to preserve the guard invariant
- `models.toml` defaults are Qwen3-32B fan-out + Qwen3-80B synthesis (changed in v1.1 Phase 7); divergence baselines pinned. MODEL-FU-01 fixes the synthesizer test that still asserts the old Sonnet default.
- Phase dependency floor: 11 → 12 → 13 → 14 → 15; Phase 16 depends on Phase 12 (SWEEP-FU-04 needs fresh-package vault); other Phase 16 items are independent

---

*State initialized: 2026-05-13*
*v1.1 roadmap: 2026-05-15*
*v1.2 roadmap: 2026-05-17*

## Operator Next Steps

- Run `/gsd:plan-phase 11` to decompose the workspace-io port into executable plans
