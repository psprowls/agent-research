---
phase: 31-domain-layer-derived-edges
plan: 03
subsystem: graph-io
tags: [graph-io, domains, emitter, yaml-parsing, cycle-detection]
requires:
  - 31-01
provides:
  - graph_io.domains module (emit, DomainYamlError, _detect_cycles)
  - Domain nodes from domains.yaml (DOMAIN-01)
  - belongs_to_domain edges Package -> Domain (DOMAIN-02)
  - domain_contains_domain edges with D-15 surgical cycle recovery (DOMAIN-03)
  - sample_monorepo/domains.yaml fixture for Plan 31-04
affects:
  - Plan 31-04 update.run wiring (domains.emit will be called between test_suites.emit and resolve.sweep)
tech-stack:
  added:
    - "packages/graph-io/src/graph_io/domains.py (new module)"
  patterns:
    - "Tarjan SCC for surgical cycle recovery — skip only intra-SCC containment edges, preserve acyclic remainder (D-15)"
    - "DomainYamlError(Exception, exit_code=4) — reuses Phase 28's exit code 4 (D-06)"
key-files:
  created:
    - packages/graph-io/src/graph_io/domains.py
    - packages/graph-io/tests/test_domains.py
    - packages/graph-io/tests/fixtures/sample_monorepo/domains.yaml
key-decisions:
  - "Self-loops are detected separately from multi-node SCCs — Tarjan operates only on the non-self-loop edges. Avoids polluting SCC analysis with degenerate 1-node 'cycles' that need a different warning message."
  - "Cycle detection warning includes intra-SCC edge count: 'Skipping <N> domain_contains_domain edge(s)' — gives users actionable signal about graph impact."
  - "Single transaction via 'with conn:' — partial failures roll back. Compatible with nested transactions because sqlite3 silently no-ops nested with blocks."
  - "No raw INSERTs — all writes go through upsert.upsert_records, preserving the (src, dst, kind) dedupe semantics and idempotency."
requirements-completed:
  - DOMAIN-02
  - DOMAIN-04
  - DOMAIN-05
duration: "25 min"
completed: 2026-05-26
---

# Phase 31 Plan 03: domains.py Loader + Cycle Detection Summary

New module `graph_io.domains` implements the Domain emitter per
CONTEXT.md D-01..D-06 and the D-15 surgical cycle-recovery contract.
The emitter reads `<repo_root>/domains.yaml`, produces `Domain` nodes,
`belongs_to_domain` edges (Package → Domain), and `domain_contains_domain`
edges (Domain → Domain) — applying Tarjan-based cycle detection that
skips ONLY cycle-participating containment edges and preserves the
acyclic remainder (matching ROADMAP SC#2 wording locked in Plan 31-01).

**Tasks:** 4
**Files created:** 3 (domains.py, test_domains.py, domains.yaml fixture)
**Files modified:** 0
**Duration:** ~25 min
**Test result:** 237 passed, 1 skipped (up from 223 — net +14 new test_domains tests, no Phase 30 regressions)

## Task Outcomes

| # | Task | Commit | Result |
|---|------|--------|--------|
| 1+2 | domains.py module + Tarjan _detect_cycles | 8c1b3a1 | Module imports; AC pass for both tasks |
| 3 | sample_monorepo/domains.yaml fixture | 1f1a3fb | 9 lines, parses correctly |
| 4 | 14 unit tests in test_domains.py | 805a6b9 | 14/14 pass first run |

Tasks 1 and 2 were tightly coupled — `_emit_containment_edges` calls `_detect_cycles`, so I committed them together rather than landing a working-stub-then-Tarjan-replacement sequence that would have left an intermediate stub in history. The combined commit fully satisfies both Task 1 and Task 2 acceptance criteria.

## Cycle Recovery Behaviour (D-15)

For a `domains.yaml` declaring:

```yaml
payments: { packages: [], parent: billing }
billing:  { packages: [mypkg], parent: payments }
outside:  { packages: [], parent: payments }
```

`domains.emit` produces:

- Domain nodes: `payments`, `billing`, `outside`
- One WARNING: `cycle detected involving domains: billing, payments. Skipping 2 domain_contains_domain edge(s); the acyclic remainder is preserved.`
- `domain_contains_domain` edges emitted: ONLY `(payments, outside)`
- `belongs_to_domain` edges: `(mypkg, billing)`

The intra-SCC edges `(payments → billing)` and `(billing → payments)` are skipped; the `(payments → outside)` edge is preserved because `outside` is not in the SCC.

## Test Coverage (14 tests)

All DOMAIN-01..05 paths, every validation warning shape, and SC#5 covered. See PLAN.md must_haves truth (m) for the full matrix.

## Deviations from Plan

**[Rule 3 - Sequencing simplification]** Tasks 1 and 2 committed together — the `_emit_containment_edges` function in domains.py is called from `emit`, so landing Task 1 with a stub body would have created a transient broken state where `emit` would have produced edges that don't respect cycle detection. Combining them into one commit (`8c1b3a1`) is more honest and avoids the stub-replacement noise in git history.

**Total deviations:** 1 (sequencing only — no behavioural deviation)
**Impact:** None — both tasks' acceptance criteria pass; the combined commit cleanly references both tasks via the commit message and code structure.

## Self-Check: PASSED

- Key files exist on disk: `domains.py`, `test_domains.py`, `domains.yaml` fixture
- `git log --oneline --grep="31-03"` returns 4 commits (1 module + 1 fixture + 1 test + 1 summary-pending)
- All `<acceptance_criteria>` re-run: PASS (33 individual assertions across 4 tasks)
- Plan-level `<verification>` (full graph-io suite): PASS — 237 passed, 1 skipped

## Next Steps

Ready for Wave 2: Plan 31-04 (`derived_edges.py` + `update.run` wiring).
Plan 31-04 will:
1. Call `domains.emit` from `update.run` in the correct order (per D-16)
2. Add `derived_edges.compute` consuming `scan_package_imports` from Plan 31-02
3. End-to-end test using the `sample_monorepo/domains.yaml` fixture
