# Roadmap: agent-research / graph-wiki-agent

**Project:** agent-research (v1 = graph-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** v1.5 — TBD (next milestone to be scoped)

---

## Milestones

- ✅ **v1.0 — graph-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (shipped 2026-05-19) — [archive](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 — Tooling Cleanup** — Phases 17-21 (shipped 2026-05-20) — [archive](milestones/v1.3-ROADMAP.md) · [audit](milestones/v1.3-MILESTONE-AUDIT.md)
- ✅ **v1.4 — Workspace Path Resolution Cleanup** — Phases 22-26 (shipped 2026-05-25) — [archive](milestones/v1.4-ROADMAP.md) · [audit](milestones/v1.4-MILESTONE-AUDIT.md)
- 📋 **v1.5 — TBD** — to be scoped via `/gsd-new-milestone`

---

## Phases

<details>
<summary>✅ v1.0 graph-wiki-agent parity (Phases 1-5) — SHIPPED 2026-05-15</summary>

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

<details>
<summary>✅ v1.3 Tooling Cleanup (Phases 17-21) — SHIPPED 2026-05-20</summary>

- [x] Phase 17: wiki-io Bug Fixes (5/5 plans) — completed 2026-05-20
- [x] Phase 18: Plugin Command Rename (6/6 plans) — completed 2026-05-20
- [x] Phase 20: Workspace Manifest Model Config (4/4 plans) — completed 2026-05-20
- [x] Phase 21: Rename graph-wiki-agent → graph-wiki-agent (5/5 plans) — completed 2026-05-20
- [x] Phase 19: Phase 16 Code Review Burndown (5/5 plans) — completed 2026-05-20

Full detail: [`milestones/v1.3-ROADMAP.md`](milestones/v1.3-ROADMAP.md)
Audit: [`milestones/v1.3-MILESTONE-AUDIT.md`](milestones/v1.3-MILESTONE-AUDIT.md)

</details>

<details>
<summary>✅ v1.4 Workspace Path Resolution Cleanup (Phases 22-26) — SHIPPED 2026-05-25</summary>

- [x] Phase 22: workspace-api-internal-rename (1/1 plan) — completed 2026-05-20
- [x] Phase 23: workspace-api-external-rename (1/1 plan) — completed 2026-05-20
- [x] Phase 24: eval-harness-workspace-rename (1/1 plan) — completed 2026-05-21
- [x] Phase 25: packages-dir-misclassification-fix (1/1 plan) — completed 2026-05-21
- [x] Phase 26: plugin-prompt-source-mirror-sync (4/4 plans) — completed 2026-05-23

Full detail: [`milestones/v1.4-ROADMAP.md`](milestones/v1.4-ROADMAP.md)
Audit: [`milestones/v1.4-MILESTONE-AUDIT.md`](milestones/v1.4-MILESTONE-AUDIT.md)

</details>

### v1.5 — TBD

To be scoped via `/gsd-new-milestone`. Expected first phase: retroactive capture of the post-v1.4 unphased work (repo rename `deep-agents → agent-research`, new packages `graph-io` and `source-parser`, package rename `vault-io → wiki-io`, doc/spike cleanup).

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 graph-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 Graph-Wiki Port & Debt | 6 | 21/21 | ✅ Shipped | 2026-05-19 |
| v1.3 Tooling Cleanup | 5 | 25/25 | ✅ Shipped | 2026-05-20 |
| v1.4 Workspace Path Resolution Cleanup | 5 | 8/8 | ✅ Shipped | 2026-05-25 |
| v1.5 TBD | - | - | 📋 To scope | - |

---

*Last updated: 2026-05-25 — v1.4 closed (minimal close, audit skipped per user direction).*
