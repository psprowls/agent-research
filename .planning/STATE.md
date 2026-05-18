---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Graph-Wiki Port & Debt Cleanup
status: planning
last_updated: "2026-05-18T03:45:45.168Z"
last_activity: 2026-05-18
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: deep-agents

**Last updated:** 2026-05-15
**Updated by:** gsd-roadmapper (milestone v1.1 roadmap created — Phases 6-9)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-17 after milestone v1.1 SHIPPED)

**Core Value:** Faithfully reproduce lattice-wiki's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Awaiting v1.2 scoping via `/gsd:new-milestone`

**North Star:** `code-wiki-agent query "..."` returns answers as good as today's lattice-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-18 — Milestone v1.2 started

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

### Active TODOs

- Scope v1.2 via `/gsd:new-milestone` — carry-forward themes captured in PROJECT.md "Next Milestone Goals" and `milestones/v1.1-REQUIREMENTS.md` v1.2 backlog

### Blockers

(None.)

### Research Flags

(None outstanding. v1.2 research flags will be added during `/gsd:new-milestone`.)

---

## Deferred Items

Items acknowledged and deferred at milestone close on 2026-05-17:

| Category | Item | Status |
|----------|------|--------|
| uat_gap | Phase 06 06-UAT.md | diagnosed (0 open scenarios — metadata only) |
| uat_gap | Phase 08 08-HUMAN-UAT.md | partial (2 pending scenarios — SC#1 + SC#2 sign-offs) |
| verification_gap | Phase 08 08-VERIFICATION.md | human_needed (2 documented scope narrowings) |
| thread | next-milestone-planning | open (intentional carry-forward to v1.2) |

Full context: `.planning/milestones/v1.1-MILESTONE-AUDIT.md`

---

## Session Continuity

**Last session:** 2026-05-17 — milestone v1.1 close
**Stopped at:** v1.1 archived; awaiting v1.2 scoping
**Resume file:** — (no in-progress phase)

**Critical context for next session:**

- v1.0 shipped: 5 phases, 25 plans, 67/67 requirements; v1.1 shipped: 5 phases, 39 plans, 29/29 requirements. Full retrospective in `.planning/RETROSPECTIVE.md`
- v1.2 not yet scoped. Run `/gsd:new-milestone` to define. Carry-forward themes:
  - TRACE-FU-01 (production trace pipeline missing `usage_metadata`)
  - SWEEP-FU-02/03/04 (sweep coverage gaps)
  - MODEL-FU-01 (synthesizer test drift to Qwen)
  - Phase 8 SC#1 closure (real DA-CLI cancel verification — blocked on aioboto3)
  - Nyquist compliance decision (0/5 v1.1 phases reached `nyquist_compliant: true`)
  - OSS release prep
- Workspace renamed: `cores/` → `packages/` (commit `c5a47ba`). Vault writes still go through `packages/vault-io/layout_io.py` — do not introduce `yaml.dump` anywhere in the write path
- MCP stdout discipline (`_StdoutGuard`) is non-negotiable; any new MCP tools must register *after* `mcp = FastMCP(...)` to preserve the guard invariant
- `models.toml` defaults are now Qwen3-32B fan-out + Qwen3-80B synthesis (changed in v1.1 Phase 7); divergence baselines pinned

---

*State initialized: 2026-05-13*
*v1.1 roadmap: 2026-05-15*

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
