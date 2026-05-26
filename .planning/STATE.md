---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: — Code Graph Ontology Expansion (SHIPPED 2026-05-26)
status: shipped
stopped_at: v1.6 milestone archived; awaiting /gsd-new-milestone for v1.7
last_updated: "2026-05-26T05:35:00.000Z"
last_activity: 2026-05-26 -- v1.6 milestone archived
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 30
  completed_plans: 30
  percent: 100
---

# Project State: agent-research

**Last updated:** 2026-05-25 — v1.6 roadmap created (Phases 28-34)
**Updated by:** gsd-roadmapper

---

## Project Reference

See: `.planning/PROJECT.md`

**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** Phase 33 — CLI Surface

---

## Current Position

Phase: 33 — COMPLETE
Plan: 5 of 5
Status: Phase 33 complete
Last activity: 2026-05-26 -- Phase 33 marked complete

Progress: [███████░░░] 67%

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

Carried forward from prior milestone closes (still pending after v1.6 ship 2026-05-26):

| Category | Item | Status |
|----------|------|--------|
| nyquist | 0/21+ v1.1-v1.5 phases produced VALIDATION.md | decision pending (retro-validate vs. disable toggle) |
| uat_gap | Phase 14 SC#4 plugin smoke transcript | deferred from v1.2 |
| slug_fix | `librarian.py:21` `_SLUG_ONLY_RE` parity fix | deferred, not load-bearing |
| quick_task | 260521-ans-typer-help-ansi-strip | acknowledged-deferred (v1.6 close) |
| quick_task | 260521-gc0-tackle-four-lint-driven-fixes-w1-repo-di | acknowledged-deferred (v1.6 close) |
| quick_task | 260521-hfr-patch-graph-wiki-scanner-wikilink-emissi | acknowledged-deferred (v1.6 close) |
| quick_task | 260521-i26-add-container-dir-template-variable-for- | acknowledged-deferred (v1.6 close) |
| quick_task | 260521-kxi-fix-graph-wiki-plugin-docs-use-uv-run-py | acknowledged-deferred (v1.6 close) |
| quick_task | 260521-lj3-workspace-io-tolerate-missing-plugins | acknowledged-deferred (v1.6 close) |
| quick_task | 260521-mfm-add-self-healing-uv-re-exec-to-graph-wik | acknowledged-deferred (v1.6 close) |
| quick_task | 260523-he3-revise-file-map-format-on-package-app-ov | acknowledged-deferred (v1.6 close) |
| quick_task | 260523-i35-add-testing-md-subpage-to-app-package-an | acknowledged-deferred (v1.6 close) |
| quick_task | 260523-iws-rename-overview-pages | acknowledged-deferred (v1.6 close) |
| todo | 2026-05-21-bootstrap-interactive-flag.md | acknowledged-deferred (v1.6 close) |
| todo | 2026-05-21-bootstrap-should-stub-empty-category-index-files.md | acknowledged-deferred (v1.6 close) |
| audit | v1.6-MILESTONE-AUDIT.md not produced | acknowledged at v1.6 close — phase-level SC checks passed for all 7 phases |

---

## Session Continuity

Last session: 2026-05-26 — v1.6 milestone closed and archived.
Stopped at: awaiting v1.7 scoping.

**Next action:** `/gsd-new-milestone` to scope v1.7. Primary candidate: wire `graph-io` into `graph-wiki-agent` (the integration v1.6 was explicitly built to enable).

---

*State initialized: 2026-05-13*
*v1.6 archived: 2026-05-26 — 7 phases (28-34), 30 plans, 56 requirements, all SC checks pass; no audit produced (acknowledged at close)*
