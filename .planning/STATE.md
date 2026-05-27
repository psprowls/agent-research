---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: Wiki Entity Restructure
status: executing
stopped_at: Phase 43 context gathered
last_updated: "2026-05-27T03:56:05.630Z"
last_activity: 2026-05-27 -- Phase 43 planning complete
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 6
  completed_plans: 0
  percent: 0
---

# Project State: agent-research

**Last updated:** 2026-05-26 — v1.8 roadmap created (Phases 42-48)
**Updated by:** gsd-roadmapper

---

## Project Reference

See: `.planning/PROJECT.md`

**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 42 — URI Slug Scheme + Per-Kind Templates (design lock)

---

## Current Position

Phase: 42 of 48 (URI Slug Scheme + Per-Kind Templates)
Plan: — (not yet planned)
Status: Ready to execute
Last activity: 2026-05-27 -- Phase 43 planning complete

Progress: [░░░░░░░░░░] 0% (0/7 phases complete)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.0–v1.7) | 41 |
| Phases complete (v1.0–v1.7) | 41 |
| Plans written (v1.0–v1.7) | 150 |
| v1.8 phases planned | 7 |
| v1.8 requirements | 32 |

---

## Accumulated Context

### Key Decisions (v1.8 scoping)

- **D1 lock: URI slug encoding uses `__` as separator** — `pkg:agent-research/graph-io` → `pkg__agent-research__graph-io.md`; `:` and `/` both encode as `__`; encoding is injective and must be property-tested before any entity page is written
- **D2 lock: scanner-owned whitelist is a `frozenset` constant in `entity_writer.py`** — reconcile ARCHITECTURE.md per-kind breakdown + FEATURES.md flat list at Phase 42; human-authored keys (`status`, `last_reviewed`, `owner`, `notes`) explicitly excluded
- **Hard-delete with append-log** — entity pages for disappeared graph nodes are deleted on next scan; every deletion logged to `.graph-wiki/deletions.log`; vault is disposable per PROJECT.md
- **Phases 47-48 are independent** — `cg domain-clusters` (Phase 47) and `graph propose-domains` (Phase 48) touch only `graph-io/` and `commands/graph.py`; can proceed in parallel with Phases 42-46 or slip to v1.9 with zero rework cost
- **Phase 42 must complete before any entity-writing code runs** — the slug scheme and whitelist are the load-bearing contracts that cascade across all downstream phases

### Active Pitfall Guards (encode in plans)

- Pitfall 1 (slug collision): property test over 1,000 URIs from all 7 admitted kinds must pass before entity writer is wired into any scan path
- Pitfall 2 (frontmatter key collision): whitelist merge enforced at write time; merge test (human `status: deprecated` survives entity update) required in Phase 43 acceptance criteria
- Pitfall 3 (hard-delete losing human edits): deletion policy is hard-delete-with-log; policy must be stated explicitly in Phase 43 plan
- Pitfall 4 (migration regex over-matching): Markdown-aware tokenizer required; code-block exclusion test in Phase 46 acceptance criteria
- Pitfall 5 (index churn): determinism test + write-if-changed guard required in Phase 44
- Pitfall 6 (degenerate clusters): hub-exclusion preprocessing + degenerate-cluster warning in Phase 47 initial implementation, not v1.9
- Pitfalls 7-8 (LLM hallucination + auto-apply): grounding check + isolation test required in Phase 48 same commit
- Pitfall 9 (concurrent scan race): scan.lock in Phase 43
- Pitfall 10 (migration re-run artifacts): idempotency guard in Phase 46

### Pending Todos

None — fresh milestone start.

### Blockers

None.

---

## Deferred Items

Carried forward from prior milestone closes:

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/28+ v1.1-v1.6 phases produced VALIDATION.md | decision pending (retro-validate vs. disable toggle) |
| slug_fix | `librarian.py:21` `_SLUG_ONLY_RE` parity fix | not load-bearing; deferred past v1.8 |
| audit | v1.6-MILESTONE-AUDIT.md not produced | acknowledged at v1.6 close |

---

## Session Continuity

Last session: 2026-05-27T03:31:43.321Z
Stopped at: Phase 43 context gathered

**Next action:** `/gsd:plan-phase 42` to plan the URI Slug Scheme + Per-Kind Templates phase.

---

*State initialized: 2026-05-13*
*v1.7 archived: 2026-05-26 — 7 phases (35-41), 10 plans, 27 requirements*
*v1.8 roadmap created: 2026-05-26 — 7 phases (42-48), 32 requirements*
