---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-05-14T17:42:57.145Z"
last_activity: 2026-05-14
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 23
  completed_plans: 17
  percent: 74
---

# Project State: deep-agents

**Last updated:** 2026-05-13
**Updated by:** roadmapper (gsd-new-project)

---

## Project Reference

**Core Value:** Faithfully reproduce lattice-wiki's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 04 — eval-harness

**North Star:** `code-wiki-agent query "..."` returns answers as good as today's lattice-wiki librarian, on cheaper Bedrock models, faster.

---

## Current Position

Phase: 04 (eval-harness) — EXECUTING
Plan: 1 of 4
**Phase:** 4
**Plan:** Not started
**Status:** Ready to execute
**Plans written:** 4 (04-01 through 04-04)
**Last activity:** 2026-05-14

**Progress:**

```
[Phase 1] [ ] Infrastructure, Vault IO, and MCP Skeleton
[Phase 2] [ ] Subagent Fan-Out Runtime
[Phase 3] [ ] Query Vertical Slice + Hybrid Search
[Phase 4] [ ] Eval Harness
[Phase 5] [ ] Remaining Commands
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 5 |
| Phases complete | 0 |
| Requirements total | 67 |
| Requirements mapped | 67 |
| Requirements complete | 0 |
| Plans written | 0 |
| Plans complete | 0 |

---

## Accumulated Context

### Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| SubagentPool over deepagents SubAgentMiddleware | Bugs #694 (cancellation cascade) and #1698 (recursion limit) confirmed on primary fan-out path; raw asyncio is safer | Pending validation in Phase 2 |
| Try SubAgentMiddleware first (SUB-02), fall back to raw asyncio (SUB-03) | Per requirements: record which path was taken as a Key Decision in PROJECT.md | Pending Phase 2 |
| Vault round-trip golden test gates all write-path code | PyYAML round-trip silently corrupts existing vault pages; test must pass before any command touches vault writes | Phase 1 gate |
| Structured trace in Phase 2, not later | Retrofitting cross-cutting trace output after multiple commands exist is expensive; design at SubagentPool layer | Phase 2 deliverable |
| Hybrid search in v1 (SEARCH-01..06) | In Phase 3 with query command; BM25 + Bedrock embeddings | Phase 3 deliverable |
| Eval harness after query, before remaining commands | Need a working command to record baselines against; harness architecture must be correct before all baselines committed | Phase 4 |
| Wikilink placeholder filter (VAULT-06) in Phase 1 | Ported from lattice-wiki-core commits 9502c45+9388cdd; needed before lint in Phase 5, safest to establish in vault IO layer early | Phase 1 deliverable |
| Bedrock IAM cross-region inference profile verified in Phase 1 | BED-01 is an explicit gate; don't write application code before IAM is confirmed | Phase 1 gate |
| python-frontmatter read-only; all writes via ported layout_io.py emitter | Prevents YAML round-trip format drift; vault/ internal convention | Phase 1 deliverable |

### Active TODOs

- [ ] Verify Bedrock IAM: run `aws bedrock invoke-model` with cross-region inference profile ARN before writing any application code (BED-01 gate)
- [ ] Decide: use deepagents SubAgentMiddleware or skip directly to raw asyncio SubagentPool? (SUB-02/SUB-03 — answer in Phase 2 integration test)
- [ ] Confirm: which Bedrock embedding model for SEARCH-02? (Titan Embeddings v2 or Cohere Embed — pick during Phase 3 research)
- [ ] Confirm: real on-demand max_tokens ceilings for Haiku and Nova Micro on Pat's account (affects BED-03 / SUB-05 values)

### Blockers

(None — project not yet started)

### Research Flags

| Phase | Risk | Note |
|-------|------|------|
| Phase 2 | MEDIUM | deepagents SubAgentMiddleware internal API is medium-confidence; read 0.6.1 source before implementing |
| Phase 4 | MEDIUM | deepeval 4.0 AmazonBedrockModel cost tracking fields need verification against actual release; heterogeneous judge panel with two GEval instances has no prior art in deepeval docs — plan a spike |

---

## Session Continuity

**To resume:** Start with Phase 1 plan (`/gsd-plan-phase 1`).

**Critical context for next session:**

- 67 v1 requirements across 10 categories; all mapped; see ROADMAP.md for phase assignments
- Phase 1 has two hard gates before any agent code: (1) Bedrock IAM cross-region inference verified, (2) vault round-trip golden test passing on real vault
- MCP server must enforce stderr-only logging from the first commit — any stdout write corrupts JSON-RPC framing
- lattice-wiki-core source is at `/Users/pat/Personal/lattice/packages/lattice-wiki-core` — the vault IO port pulls from there
- deepagents bugs #694 and #1698 affect SubAgentMiddleware; SubagentPool in cores/subagent-runtime patches both

---

*State initialized: 2026-05-13*
