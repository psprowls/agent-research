# Roadmap: deep-agents / code-wiki-agent

**Project:** deep-agents (v1 = code-wiki-agent)
**Created:** 2026-05-13

---

## Milestones

- ✅ **v1.0 — code-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- 📋 **v1.2 — TBD** — scope via `/gsd:new-milestone` (see PROJECT.md "Next Milestone Goals")

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

### 📋 v1.2 — TBD

Scope via `/gsd:new-milestone`. Carry-forward themes from v1.1 close:

- TRACE-FU-01 — fix production trace pipeline `usage_metadata` (today only sweep harness records token counts)
- SWEEP-FU-02/03/04 — wire DivergenceMetric through full matrix; re-tune code_reader cases; re-sweep scanner against fresh-package vault
- MODEL-FU-01 — fix `test_load_role_config_synthesizer_uses_sonnet` to match Qwen synthesizer reality
- MCP cancellation completion — real DA-CLI cancel verification (deferred from v1.1 SC#1 pending aioboto3 wire-level cancel)
- Nyquist compliance decision — 0/5 v1.1 phases reached `nyquist_compliant: true`; either retro-validate or disable the toggle
- Open-source release prep — README badges, contribution guide, public install instructions, PyPI publish dry-run

Backlog REQ-IDs in [`milestones/v1.1-REQUIREMENTS.md`](milestones/v1.1-REQUIREMENTS.md) under "v1.2 Backlog".

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 code-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 TBD | — | — | 📋 Awaiting scope | — |

---

*Last updated: 2026-05-17 — milestone v1.1 SHIPPED and archived. Awaiting v1.2 scoping via `/gsd:new-milestone`.*
