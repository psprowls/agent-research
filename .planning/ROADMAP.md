# Roadmap: deep-agents / code-wiki-agent

**Project:** deep-agents (v1 = code-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** v1.3 Tooling Cleanup (Phases 17-19)

---

## Milestones

- ✅ **v1.0 — code-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (shipped 2026-05-19) — [archive](milestones/v1.2-ROADMAP.md)
- 🚧 **v1.3 — Tooling Cleanup** — Phases 17-19 (in progress)

---

## Phases

<details>
<summary>✅ v1.0 code-wiki-agent parity (Phases 1-5) — SHIPPED 2026-05-15</summary>

- [x] Phase 1: Infrastructure, Vault IO, and MCP Skeleton (5/5 plans) — completed 2026-05-13
- [x] Phase 2: Subagent Fan-Out Runtime (4/4 plans) — completed 2026-05-13
- [x] Phase 3: Query Vertical Slice + Hybrid Search (6/6 plans) — completed 2026-05-14
- [x] Phase 4: Eval Harness (4/4 plans) — completed 2026-05-14
- [x] Phase 5: Remaining Commands (6/6 plans) — completed 2026-05-14

Full detail: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Quality Improvements (Phases 6-10) — SHIPPED 2026-05-17</summary>

- [x] Phase 6: Prompt Content Port + Divergence Eval (16/16 plans) — completed 2026-05-17
- [x] Phase 7: Cost-Frontier Sweep (7/7 plans) — completed 2026-05-17
- [x] Phase 8: Host Reliability (3/3 plans) — completed 2026-05-17
- [x] Phase 9: Trace/Observability Polish (6/6 plans) — completed 2026-05-17
- [x] Phase 10: Subagent Context Completion (7/7 plans) — completed 2026-05-17

Full detail: [`milestones/v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md)
Audit: [`milestones/v1.1-MILESTONE-AUDIT.md`](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.2 Graph-Wiki Port & Debt Cleanup (Phases 11-16) — SHIPPED 2026-05-19</summary>

- [x] Phase 11: workspace-io Port (M1) (6/6 plans) — completed 2026-05-18
- [x] Phase 12: Drift Backport + Ecosystem Rebrand (M2) (4/4 plans) — completed 2026-05-18
- [x] Phase 13: Plugin Spec (M3a) (5/5 plans) — completed 2026-05-18
- [x] Phase 14: Plugin Port (M3b) (3/3 plans) — completed 2026-05-19
- [x] Phase 15: Wiki Self-Update (1/1 plan) — completed 2026-05-19
- [x] Phase 16: Carry-Forward Debt Cleanup (2/2 plans) — completed 2026-05-19

Full detail: [`milestones/v1.2-ROADMAP.md`](milestones/v1.2-ROADMAP.md)

</details>

### 🚧 v1.3 Tooling Cleanup (In Progress)

**Milestone Goal:** Burn down the v1.2 carry-forward bug list in `vault-io` and the `/init` plugin command shadow, and address the Phase 16 code review findings.

- [ ] **Phase 17: vault-io Bug Fixes** - Fix scan companion-page diff, Bedrock CountTokens API shape, and workspace/repo resolution
- [ ] **Phase 18: Plugin Command Rename** - Rename `/graph-wiki:init` → `/graph-wiki:init-wiki` to restore Claude Code's native `/init`
- [ ] **Phase 19: Phase 16 Code Review Burndown** - Triage and resolve all 6 warnings + 9 info findings from the trace pipeline + eval harness review

---

## Phase Details

### Phase 17: vault-io Bug Fixes
**Goal**: All three vault-io behavioral bugs are fixed so scan reports accurate diffs, token counts are stamped correctly, and repo/container resolution works at the v2 workspace layout
**Depends on**: Phase 16 (prior milestone)
**Requirements**: SCAN-01, SCAN-02, TOK-01, TOK-02, TOK-03, WSRES-01, WSRES-02, WSRES-03
**Success Criteria** (what must be TRUE):
  1. `/graph-wiki:scan` on a healthy 7-package vault reports 0 deleted entries for the four companion pages per package (was 28)
  2. After scan, all 35 wiki pages previously at `tokens: 0` show a non-zero token count in their frontmatter
  3. `detect_containers --json` returns the repo-root containers (not an empty list) when the wiki lives at `<workspace>/wiki/`
  4. The workspace directory itself does not appear in its own layout block as a `docs` container
  5. Unit and integration tests for scan companion folding and CountTokens API shape pass under `uv run --package vault-io pytest`
**Plans**: TBD

### Phase 18: Plugin Command Rename
**Goal**: Claude Code's built-in `/init` command is reachable again by renaming the conflicting plugin command to `/init-wiki` with all references updated
**Depends on**: Phase 17
**Requirements**: CMD-01, CMD-02, CMD-03
**Success Criteria** (what must be TRUE):
  1. `plugins/graph-wiki/commands/init-wiki.md` exists; `init.md` is gone from that directory
  2. All internal plugin references (`marketplace.json`, `SKILL.md`, command bodies, READMEs) use `/init-wiki` / `graph-wiki:init-wiki` — no stale `/graph-wiki:init` references remain
  3. With the plugin installed, typing `/init` in Claude Code invokes the native "initialize CLAUDE.md" workflow, not the graph-wiki command
**Plans**: TBD

### Phase 19: Phase 16 Code Review Burndown
**Goal**: Every Phase 16 code review finding has a documented disposition (fixed, dismissed with rationale, or converted to a follow-up todo) so the trace pipeline + eval harness refactor lands without carried-forward debt
**Depends on**: Phase 17
**Requirements**: REVIEW-01, REVIEW-02
**Success Criteria** (what must be TRUE):
  1. All 6 warning-level findings are triaged — each has one of: a code fix committed, a written rationale for dismissal, or a filed follow-up todo
  2. All 9 info-level findings are triaged with the same fix / dismiss / follow-up disposition
  3. Triage outcomes are recorded in the phase REVIEW.md so future code review can verify the debt is not re-accumulating
**Plans**: TBD

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 code-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 Graph-Wiki Port & Debt | 6 | 21/21 | ✅ Shipped | 2026-05-19 |
| v1.3 Tooling Cleanup | 3 | 0/TBD | 🚧 In progress | - |

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 17. vault-io Bug Fixes | 0/TBD | Not started | - |
| 18. Plugin Command Rename | 0/TBD | Not started | - |
| 19. Phase 16 Code Review Burndown | 0/TBD | Not started | - |

---

*Last updated: 2026-05-19 — v1.3 roadmap created (3 phases, 13/13 requirements mapped). Continues from Phase 16 (v1.2).*
