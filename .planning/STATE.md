---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Tooling Cleanup
status: planning
last_updated: "2026-05-19T19:54:08.365Z"
last_activity: 2026-05-19
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: deep-agents

**Last updated:** 2026-05-19
**Updated by:** gsd-complete-milestone (v1.2 SHIPPED)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-19 after milestone v1.2 SHIPPED)

**Core Value:** Faithfully reproduce the upstream graph-wiki (formerly lattice-wiki) wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Between milestones — v1.2 SHIPPED 2026-05-19. Run `/gsd:new-milestone` to scope v1.3.

**North Star:** `code-wiki-agent query "..."` returns answers as good as today's graph-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-19 — Milestone v1.3 started

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
| Phases complete (v1.2) | 6 |
| Requirements total (v1.2) | 30 |
| Requirements complete (v1.2) | 30 |
| Plans written (v1.2) | 21 |
| Plans complete (v1.2) | 21 |

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

- Run `/gsd:new-milestone` to scope v1.3 (carry-forward themes captured in `PROJECT.md → Next Milestone`)

### Blockers

(None.)

### Research Flags

(None — work is internal port/rebrand of known lattice code per thread `next-milestone-planning`; spike 002 already inventoried source modules.)

---

## Deferred Items

Items acknowledged and deferred at v1.2 milestone close on 2026-05-19:

| Category | Item | Status |
|----------|------|--------|
| todo | fix-bedrock-count-tokens-api-shape-in-update-tokens | deferred (v1.3 candidate; tooling) |
| todo | fix-workspace-repo-resolution-in-init-vault-and-detect-conta | deferred (v1.3 candidate; tooling) |
| todo | rename-graph-wiki-init-command-to-init-wiki | deferred (v1.3 candidate; tooling) |
| thread | next-milestone-planning | deferred (carry-forward through v1.0 → v1.1 → v1.2 → v1.3; close or convert to requirements when v1.3 is scoped) |
| review | Phase 16 code review | deferred (6 warnings + 9 info, 0 critical; v1.3 candidate) |
| uat_gap | Phase 14 SC#4 plugin smoke transcript | deferred (accepted on structural evidence; capture in v1.3) |
| nyquist | 0/5 v1.1 + 0/6 v1.2 phases compliant | deferred (v1.3 decision: retro-validate vs. disable toggle) |

Prior v1.1 deferred items (all addressed in v1.2 Phase 16):

| Category | Item | Status |
|----------|------|--------|
| uat_gap | Phase 06 06-UAT.md | resolved (metadata fixed) |
| uat_gap | Phase 08 08-HUMAN-UAT.md | resolved (MCP-CAN-01 closure in Phase 16) |
| verification_gap | Phase 08 08-VERIFICATION.md | resolved (cancel deferral re-anchored to event trigger, `docs/cancellation.md §5`) |

---

## Session Continuity

**Last session:** 2026-05-19T19:25:00.000Z
**Stopped at:** v1.2 SHIPPED — archives written, ROADMAP/PROJECT/STATE evolved, MILESTONES entry curated
**Resume file:** none — between milestones

**Critical context for next session:**

- v1.0 shipped: 5 phases, 25 plans, 67/67 requirements; v1.1 shipped: 5 phases, 39 plans, 29/29 requirements; v1.2 shipped: 6 phases, 21 plans, 30/30 requirements. Full retrospective in `.planning/RETROSPECTIVE.md`
- v1.2 deliverables: `packages/workspace-io/` + `.graph-wiki.yaml` manifest + `GRAPH_WIKI_WORKSPACE` env, full `lattice` → `graph-wiki` rebrand with `scripts/check-brand.sh` grep-gate, `plugins/graph-wiki/` Claude Code plugin (NOT a `code-wiki-agent` wrapper — runs on Claude Code inference; the two coexist), wiki self-update of `~/Personal/wiki/deep-agents`, all v1.1 carry-forward debt closed
- v1.3 candidate themes (see PROJECT.md → Next Milestone): pending tooling todos (CountTokens shape, workspace/repo resolution, command rename), Nyquist retro decision, Phase 16 review findings (6 warn + 9 info), Phase 14 SC#4 smoke transcript, `next-milestone-planning` thread closure
- Out of scope for v1.x: `work/` subsystem (GSD covers it), package-family monorepo support (different approach planned), OSS release prep (→ v2.0)
- Workspace renamed: `cores/` → `packages/` (v1.1 commit `c5a47ba`); brand renamed: `lattice` → `graph-wiki` (v1.2 Phase 12). Vault writes still go through `packages/vault-io/layout_io.py` — do not introduce `yaml.dump` anywhere in the write path
- MCP stdout discipline (`_StdoutGuard`) is non-negotiable; any new MCP tools must register *after* `mcp = FastMCP(...)` to preserve the guard invariant
- `models.toml` defaults are Qwen3-32B fan-out + Qwen3-80B synthesis (v1.1 Phase 7); divergence baselines pinned
- `vault-io` ↔ `workspace-io` boundary (v1.2): `vault_io._workspace.resolve_wiki_and_repo` is a 2-line delegation shim over `workspace_io.config.resolve()`; explicit-vault_path MCP boundary preserved
- Plugin contract (v1.2 Phase 13): plugins/graph-wiki/scripts/*.py shell out via `uv run --project "$DEEP_AGENTS_ROOT" python3 -m ...` (SO-01); backend selection per command via `[plugin]` block in `.graph-wiki.yaml` (SO-03); defaults to `claude`, `bedrock` is documented per-command opt-in
- MCP cancel deferral re-anchored to event trigger (v1.2 Phase 16 D-09): langchain-aws#663 OR aioboto3 GA/1.0; no calendar re-evaluation

---

*State initialized: 2026-05-13*
*v1.1 roadmap: 2026-05-15 — shipped 2026-05-17*
*v1.2 roadmap: 2026-05-17 — shipped 2026-05-19*

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
