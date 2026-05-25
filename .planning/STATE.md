---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Code Graph Ontology Expansion
status: roadmap_created
last_updated: "2026-05-25"
last_activity: 2026-05-25
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: agent-research

**Last updated:** 2026-05-25 — v1.6 roadmap created (Phases 28-34)
**Updated by:** gsd-roadmapper

---

## Project Reference

See: `.planning/PROJECT.md`

**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** v1.6 Phase 28 — Schema v2 + URI Foundation (ready to plan)

---

## Current Position

Phase: 28 of 34 (Schema v2 + URI Foundation)
Plan: — (not yet planned)
Status: Ready to plan
Last activity: 2026-05-25 — v1.6 roadmap created; 7 phases, 56 requirements mapped

Progress: [░░░░░░░░░░] 0%

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.0–v1.5) | 27 |
| Phases complete (v1.0–v1.5) | 27 |
| Requirements total (v1.0–v1.5) | 118+ |
| Plans written (v1.0–v1.5) | 118 |
| v1.6 phases planned | 7 |
| v1.6 requirements | 56 |

---

## Accumulated Context

### Key Decisions (v1.6)

- **Domain assignment is explicit-config-only in v1.6** — convention inference deferred to v1.7 (decision 2026-05-25). `domains.yaml` at repo root is the sole source. Missing file = zero-domain (not an error).
- **URI column is `TEXT` nullable in v1.6** — `UNIQUE NOT NULL` deferred to v1.7 after coverage validated. AST nodes (functions, classes) have NULL URI.
- **No 9-stage pipeline restructure in v1.6** — additive flat calls in `update.py`; restructure is v1.7 when `--domains-only` re-run becomes load-bearing.
- **SPARSER-01/02 in Phase 29** — source-parser AST attrs (`has_main`, `is_importable`) tightly coupled to structural node emission; grouped together.
- **`packages.refresh` returns manifest data** — `entry_points.emit` consumes it; avoids double I/O (anti-pattern 5 in ARCHITECTURE.md).
- **Brand sweep (Phase 34) runs last** — zero code dependencies; last to avoid merge conflicts with substantive changes.

### Active Pitfall Guards (encode in plans)

- Pitfall 1: `test_nodes_table_has_uri_column` must exist before Phase 29 begins
- Pitfall 4: `_upsert_node` must pop `uri` from `node.attrs` before serializing `attrs_json`
- Pitfall 2: `SCHEMA_MISMATCH` exit code 4 wired in `cli/main.py` — test with seeded v999 DB
- Pitfall 5: `resolve.sweep` guard extended to exclude `repository`, `domain`, `test_suite`, `entry_point` from path=NULL deletion
- Pitfall 6: `test_suites.emit` must run after `packages.refresh`; add ordering test

### Pending Todos

None — fresh milestone start.

### Blockers

None.

---

## Deferred Items

Carried forward from v1.5 close (still pending):

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/21+ v1.1-v1.5 phases produced VALIDATION.md | decision pending (retro-validate vs. disable toggle) |
| uat_gap | Phase 14 SC#4 plugin smoke transcript | deferred from v1.2 |
| slug_fix | `librarian.py:21` `_SLUG_ONLY_RE` parity fix | deferred, not load-bearing |
| quick_tasks | 9 untracked quick tasks + 2 bootstrap todos | acknowledged-deferred |

---

## Session Continuity

Last session: 2026-05-25
Stopped at: v1.6 roadmap created — ROADMAP.md + STATE.md + REQUIREMENTS.md traceability written
Resume file: None

**Next action:** `/gsd:plan-phase 28`

---

*State initialized: 2026-05-13*
*v1.6 roadmap created: 2026-05-25 — 7 phases (28-34), 56 requirements*
