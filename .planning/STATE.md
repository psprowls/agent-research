---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Tooling Cleanup
status: executing
stopped_at: Phase 17 context gathered
last_updated: "2026-05-20T00:02:07.174Z"
last_activity: 2026-05-20
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 9
  completed_plans: 5
  percent: 56
---

# Project State: deep-agents

**Last updated:** 2026-05-19
**Updated by:** gsd-roadmapper (v1.3 roadmap created)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-19 after milestone v1.2 SHIPPED)

**Core Value:** Faithfully reproduce the upstream graph-wiki wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 17 — vault-io-bug-fixes

**North Star:** `code-wiki-agent query "..."` returns answers as good as today's graph-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: 17 (vault-io-bug-fixes) — EXECUTED, awaiting re-verification on SC#4
Plan: 5 of 5 (all plans shipped including 17-05 gap closure)
Status: 17-05 (WSRES-02 gap closure) committed; ready for verifier re-run on SC#4
Last activity: 2026-05-19 -- Phase 17 plan 17-05 complete (93 vault-io tests pass)

Progress: [██████████] 100% (5/5 plans complete; awaiting verification)

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
| Phases total (v1.3) | 3 |
| Phases complete (v1.3) | 0 |
| Requirements total (v1.3) | 13 |

---

## Accumulated Context

### Key Decisions

(Full log lives in `PROJECT.md → Key Decisions`. Recent decisions affecting v1.3:)

- v1.2 Phase 16: MCP cancel deferral re-anchored to event trigger (langchain-aws#663 OR aioboto3 GA/1.0)
- v1.3 scope: SCAN + TOK + WSRES grouped into Phase 17 (all in packages/vault-io/, shared fixture territory); CMD isolated in Phase 18 (plugins/graph-wiki/ only, no Python); REVIEW in Phase 19

### Roadmap Evolution

- Phase 20 added (2026-05-19): Workspace Manifest Model Config — move wiki model overrides into `<workspace>/.graph-wiki.yaml` `plugins[].roles[]`; delete the orphan `wiki-config.toml` pathway (`WikiConfig.models_path`, `set_models_path()`, `--config`, `CODE_WIKI_CONFIG`); packaged `model-adapter/models.toml` becomes per-role fallback. Triggered by discovering `wiki-config.toml` had no source-code references and the user's direction that all config should live in the `.graph-wiki.yaml` family.

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

**Last session:** 2026-05-19T22:36:35.168Z
**Stopped at:** Phase 17 context gathered
**Resume file:** None

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
