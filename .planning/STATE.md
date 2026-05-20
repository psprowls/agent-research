---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Workspace Path Resolution Cleanup
status: planning
last_updated: "2026-05-20T19:23:50.124Z"
last_activity: 2026-05-20
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: deep-agents

**Last updated:** 2026-05-19
**Updated by:** gsd-roadmapper (v1.3 roadmap created)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-19 after milestone v1.2 SHIPPED)

**Core Value:** Faithfully reproduce the upstream graph-wiki wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 19 — phase-16-code-review-burndown

**North Star:** `graph-wiki-agent query "..."` returns answers as good as today's graph-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-20 — Milestone v1.4 started

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
| Phases total (v1.3) | 4 |
| Phases complete (v1.3) | 1 |
| Requirements total (v1.3) | 13 (+ Phase 20/21 TBD) |
| Phases total (v1.3) | 5 |
| Phases complete (v1.3) | 2 |

---

## Accumulated Context

### Key Decisions

(Full log lives in `PROJECT.md → Key Decisions`. Recent decisions affecting v1.3:)

- v1.2 Phase 16: MCP cancel deferral re-anchored to event trigger (langchain-aws#663 OR aioboto3 GA/1.0)
- v1.3 scope: SCAN + TOK + WSRES grouped into Phase 17 (all in packages/vault-io/, shared fixture territory); CMD isolated in Phase 18 (plugins/graph-wiki/ only, no Python); REVIEW in Phase 19

### Roadmap Evolution

- Phase 20 added (2026-05-19): Workspace Manifest Model Config — move wiki model overrides into `<workspace>/.graph-wiki.yaml` `plugins[].roles[]`; delete the orphan `wiki-config.toml` pathway (`WikiConfig.models_path`, `set_models_path()`, `--config`, `GRAPH_WIKI_CONFIG`); packaged `model-adapter/models.toml` becomes per-role fallback. Triggered by discovering `wiki-config.toml` had no source-code references and the user's direction that all config should live in the `.graph-wiki.yaml` family.
- Phase 20 completed (2026-05-20): 4 plans shipped across 3 waves; verifier 5/5 SCs PASS; checkpoint smoke checks confirmed workspace manifest is live source of truth and falls back to packaged `models.toml` per-role.
- Phase 21 added to v1.3 (2026-05-20): graph-wiki-agent → graph-wiki-agent mechanical rename. CONTEXT.md already gathered in `.planning/phases/21-rename-graph-wiki-agent-...`; awaiting planning. Next-up after Phase 18.
- Phase 19 reordered (2026-05-20): code review burndown moved to end of v1.3 execution queue; now depends on Phase 21 so the rename ships before triage. Numbers unchanged (display order: 17, 18, 20, 21, 19).
- Phase 21 added (2026-05-19): Rename graph-wiki-agent to graph-wiki-agent — update all code references (excluding wiki content) so the agent package name aligns with the `graph-wiki` plugin port.

### Active TODOs

- `.planning/todos/pending/2026-05-19-fix-bedrock-count-tokens-api-shape-in-update-tokens.md` → Phase 17
- `.planning/todos/pending/2026-05-19-fix-workspace-repo-resolution-in-init-vault-and-detect-conta.md` → Phase 17
- `.planning/todos/pending/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` → Phase 18
- `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` → unassigned (graph-wiki / vault-io)

### Blockers

(None.)

---

## Quick Tasks Completed

| Quick ID | Description | Commit |
|----------|-------------|--------|
| 260519-k9t-preflight-role | Preflight role refactor — confirm preflight uses dedicated role config, not orchestrator defaults | e5fb45a |
| 260519-lf1-bedrock-audit | Bedrock audit script — verify all model calls route through model-adapter guard layer | a459815 |
| 260520-bgd-close-out-v1-3-deferred-items | Close out v1.3 deferred items: commit untracked archive files, backfill audit-open status for k9t+lf1, resolve stale open_questions in Phase 18 + 20 CONTEXT | (this commit) |

---

## Deferred Items

Items acknowledged at v1.2 close that are NOT in v1.3 scope:

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/5 v1.1 + 0/6 v1.2 + 0/5 v1.3 phases compliant | deferred past v1.3 (decision: retro-validate vs. disable toggle) |
| uat_gap | Phase 14 SC#4 plugin smoke transcript | deferred past v1.3 (capture as regression artifact later) |
| thread | next-milestone-planning | deferred (carry-forward; close at v1.3 close or convert at v1.4 scoping) |

Items acknowledged at v1.3 close (2026-05-20):

| Category | Item | Status |
|----------|------|--------|
| verification | Phase 18 — `18-VERIFICATION.md` `human_needed` | ✅ closed 2026-05-20 — user typed `/init` in active session; native Claude Code CLAUDE.md init workflow fired (canonical prompt text confirmed). Plugin's `/graph-wiki:bootstrap` is the only graph-wiki bootstrap path. See `18-VERIFICATION.md` §Human Verification Required #1 for full UAT capture. |
| quick_task | 260519-k9t-preflight-role | closed (260520-bgd Task 2): SUMMARY.md stub added + Quick Tasks Completed index backfilled |
| quick_task | 260519-lf1-bedrock-audit | closed (260520-bgd Task 2): SUMMARY.md stub added + Quick Tasks Completed index backfilled |
| context_questions | Phase 18 `18-CONTEXT.md` — 3 open question lines | answered during execution (rename approach + reinstall instructions + historical sweep granularity), question markers not cleared from CONTEXT.md text |
| context_questions | Phase 20 `20-CONTEXT.md` — 3 open question lines | answered during execution (RoleConfig field set + `--config` drop + `models.toml` lifecycle), question markers not cleared from CONTEXT.md text |

---

## Session Continuity

**Last session:** 2026-05-20T04:04:01.349Z
**Stopped at:** Phase 19 context gathered
**Resume file:** .planning/phases/19-phase-16-code-review-burndown/19-CONTEXT.md

**Critical context for next session:**

- v1.3 phases: 17 (vault-io bugs: scan companion-page diff + CountTokens API shape + repo resolution), 18 (plugin /init → /init-wiki rename), 19 (Phase 16 review burndown)
- Phase 17 touches packages/vault-io/ only; Phase 18 touches plugins/graph-wiki/ only (no Python changes); Phase 19 touches packages/eval-harness/ + trace pipeline
- vault-io write path: always goes through packages/vault-io/layout_io.py — do not introduce yaml.dump
- MCP stdout discipline (_StdoutGuard) is non-negotiable for any new MCP tools
- models.toml defaults: Qwen3-32B fan-out + Qwen3-80B synthesis (v1.1 Phase 7)

---

*State initialized: 2026-05-13*
*v1.1 roadmap: 2026-05-15 — shipped 2026-05-17*
*v1.2 roadmap: 2026-05-17 — shipped 2026-05-19*
*v1.3 roadmap: 2026-05-19*
