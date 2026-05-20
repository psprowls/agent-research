---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Tooling Cleanup
status: completed
stopped_at: Phase 21 context gathered
last_updated: "2026-05-20T03:42:16.469Z"
last_activity: 2026-05-20 -- Phase 21 marked complete
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 20
  completed_plans: 20
  percent: 80
---

# Project State: deep-agents

**Last updated:** 2026-05-19
**Updated by:** gsd-roadmapper (v1.3 roadmap created)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-19 after milestone v1.2 SHIPPED)

**Core Value:** Faithfully reproduce the upstream graph-wiki wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 21 — rename-graph-wiki-agent-to-graph-wiki-agent-update-all-code-r

**North Star:** `graph-wiki-agent query "..."` returns answers as good as today's graph-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: 21 — COMPLETE
Plan: 1 of 5
Status: Phase 21 complete
Last activity: 2026-05-20 -- Phase 21 marked complete

v1.3 Progress: [████░░░░░░] 40% (2/5 phases complete; 9 plans shipped this milestone)

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

### Blockers

(None.)

---

## Deferred Items

Items acknowledged at v1.2 close that are NOT in v1.3 scope:

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/5 v1.1 + 0/6 v1.2 phases compliant | deferred past v1.3 (decision: retro-validate vs. disable toggle) |
| uat_gap | Phase 14 SC#4 plugin smoke transcript | deferred past v1.3 (capture as regression artifact later) |
| thread | next-milestone-planning | deferred (carry-forward; close at v1.3 close or convert at v1.4 scoping) |

---

## Session Continuity

**Last session:** 2026-05-20T00:52:39.540Z
**Stopped at:** Phase 21 context gathered
**Resume file:** .planning/phases/21-rename-graph-wiki-agent-to-graph-wiki-agent-update-all-code-r/21-CONTEXT.md

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
