# Roadmap: agent-research / graph-wiki-agent

**Project:** agent-research (v1 = graph-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** v1.5 — Repo Rename & Foundational Package Additions (retroactive, complete)

---

## Milestones

- ✅ **v1.0 — graph-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (shipped 2026-05-19) — [archive](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 — Tooling Cleanup** — Phases 17-21 (shipped 2026-05-20) — [archive](milestones/v1.3-ROADMAP.md) · [audit](milestones/v1.3-MILESTONE-AUDIT.md)
- ✅ **v1.4 — Workspace Path Resolution Cleanup** — Phases 22-26 (shipped 2026-05-25) — [archive](milestones/v1.4-ROADMAP.md) · [audit](milestones/v1.4-MILESTONE-AUDIT.md)
- 🚧 **v1.5 — Repo Rename & Foundational Package Additions** — Phase 27 (retroactive, complete; awaiting close)

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

### 🚧 v1.5 Repo Rename & Foundational Package Additions (Phase 27) — RETROACTIVE

Goal: document the post-v1.4 unphased work that already shipped on `main` — repo rename `deep-agents → agent-research`, env var sweep `DEEP_AGENTS_ROOT → AGENT_RESEARCH_ROOT`, new packages `graph-io` + `source-parser`, package rename `vault-io → wiki-io`, doc cleanup.

- [x] **Phase 27: post-v1.4-foundation-changes** — Retroactive single-phase capture (REPO-01, REPO-02, PKG-01, PKG-02, RENAME-01, CLEANUP-01, CLEANUP-02). Evidence in commits `9b8ac87..f896d99`; canonical artifact is `27-SUMMARY.md` (no PLAN.md — work shipped before phase was created).

---

## Phase Details

### Phase 27: post-v1.4-foundation-changes

**Goal**: Capture and document the seven unphased commits that landed on `main` between v1.4 close and v1.5 scoping. Bring the workspace into a known, ROADMAP-tracked state ahead of v1.6+ integration work that will wire `graph-io` and `source-parser` into the agent loop.

**Mode**: Retroactive — all work is shipped. No PLAN.md, no execution, no verification beyond what landed in the original commits. SUMMARY.md is the canonical artifact.

**Depends on**: v1.4 (Phases 22-26 archived)

**Requirements**: REPO-01, REPO-02, PKG-01, PKG-02, RENAME-01, CLEANUP-01, CLEANUP-02

**Success Criteria** (what is TRUE):

  1. `git remote -v` and all docs refer to `agent-research`, not `deep-agents`
  2. `grep -rE "DEEP_AGENTS_ROOT" .` returns 0 hits outside this SUMMARY/history
  3. `packages/graph-io/` exists with `pyproject.toml` declaring workspace deps on `source-parser` + `workspace-io`
  4. `packages/source-parser/` exists with `pyproject.toml` declaring tree-sitter deps
  5. `packages/vault-io/` no longer exists; `packages/wiki-io/` is the canonical name; `uv run pytest` is green
  6. `grep -rE "lattice-wiki" README.md` and core docs returns 0 substantive hits (history references in `.planning/` excepted)
  7. `.planning/spikes/` and `.planning/sketches/` are removed

**Plans**: 0 plans (retroactive)

  - Canonical artifact: [`27-SUMMARY.md`](phases/27-post-v1.4-foundation-changes/27-SUMMARY.md)

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 graph-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 Graph-Wiki Port & Debt | 6 | 21/21 | ✅ Shipped | 2026-05-19 |
| v1.3 Tooling Cleanup | 5 | 25/25 | ✅ Shipped | 2026-05-20 |
| v1.4 Workspace Path Resolution Cleanup | 5 | 8/8 | ✅ Shipped | 2026-05-25 |
| v1.5 Repo Rename & Foundational Package Additions | 1 | 0/0 (retro) | 🚧 Retroactive, complete | 2026-05-25 |

---

*Last updated: 2026-05-25 — v1.4 closed minimally; v1.5 created retroactively for Phase 27 (post-v1.4 unphased work).*
