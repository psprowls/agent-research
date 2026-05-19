# Roadmap: deep-agents / code-wiki-agent

**Project:** deep-agents (v1 = code-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** _none — v1.2 shipped 2026-05-19; run `/gsd:new-milestone` to scope v1.3_

---

## Milestones

- ✅ **v1.0 — code-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (shipped 2026-05-19) — [archive](milestones/v1.2-ROADMAP.md)

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

### 📋 v1.3 (Not Yet Scoped)

Run `/gsd:new-milestone` to scope v1.3. Carry-forward themes from v1.2 close:

- Pending tooling todos (Bedrock CountTokens shape, workspace/repo resolution in init_vault + detect_containers, rename `/graph-wiki:init` → `/graph-wiki:init-wiki`)
- Nyquist compliance retro decision (0/5 v1.1 + 0/6 v1.2 phases reached compliance)
- Phase 16 code review findings (6 warnings + 9 info, 0 critical)
- Phase 14 SC#4 plugin smoke transcript capture
- `next-milestone-planning` thread (carry-forward)

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 code-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 Graph-Wiki Port & Debt | 6 | 21/21 | ✅ Shipped | 2026-05-19 |

---

*Last updated: 2026-05-19 — v1.2 milestone shipped (6 phases, 21 plans, 30/30 requirements). Next: `/gsd:new-milestone` to scope v1.3.*
