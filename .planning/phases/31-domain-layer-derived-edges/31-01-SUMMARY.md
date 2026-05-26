---
phase: 31-domain-layer-derived-edges
plan: 01
subsystem: graph-io
tags: [graph-io, wave-0, roadmap-amendment, pyyaml-dep, uri-shape]
requires: []
provides:
  - amended ROADMAP SC#2 wording (surgical cycle recovery, D-15)
  - pyyaml>=6.0 as a declared graph-io dependency (D-06)
  - domain_uri(ctx, name) → "domain:<org>/<repo>/<name>" (D-05)
affects:
  - downstream Wave 1 plans 31-02 and 31-03
tech-stack:
  added:
    - "pyyaml>=6.0 (resolved: 6.0.3)"
  patterns:
    - "ctx-aware URI helpers: every helper in uri.py now takes RepoContext as the first positional arg (no exceptions)"
key-files:
  modified:
    - .planning/ROADMAP.md
    - packages/graph-io/pyproject.toml
    - packages/graph-io/src/graph_io/uri.py
    - packages/graph-io/tests/test_uri.py
    - uv.lock
key-decisions:
  - "D-15 surgical cycle recovery wording is now locked in ROADMAP SC#2 — downstream verifier reads the corrected text"
  - "domain_uri signature break is safe — zero callers outside uri.py before the change (grep-verified)"
requirements-completed:
  - DOMAIN-01
  - DOMAIN-03
duration: "10 min"
completed: 2026-05-26
---

# Phase 31 Plan 01: Wave 0 — Three Pre-Req Patches Summary

Three independent single-file edits that Wave 1 plans depend on:
(1) ROADMAP SC#2 wording amendment for surgical cycle recovery (D-15),
(2) pyyaml>=6.0 added to graph-io dependencies so `domains.emit` can use
`yaml.safe_load` (D-06), and (3) `domain_uri` amended from `(name)` to
`(ctx, name)` returning `domain:<org>/<repo>/<name>` (D-05).

**Tasks:** 3
**Files modified:** 5 (4 source + uv.lock)
**Duration:** ~10 min
**Test result:** 215 passed, 1 skipped (no regressions vs Phase 30 baseline)

## Task Outcomes

| # | Task | Commit | Result |
|---|------|--------|--------|
| 1 | Amend ROADMAP.md SC#2 wording (D-15) | f4ea03b | All 4 AC pass |
| 2 | Add pyyaml>=6.0 dep (D-06) | 52aaa91 | yaml 6.0.3 resolved; `import yaml` works |
| 3 | Amend domain_uri signature (D-05) — RED/GREEN | 34dc643, ba28f70 | 19/19 test_uri.py pass |

## Acceptance Criteria

All 16 acceptance criteria across the 3 tasks verified individually
(grep assertions for source shape, pytest run for behavior). Plan-level
`<verification>` (full graph-io suite): **215 passed, 1 skipped, 0 failed**
— matches Phase 30 baseline exactly.

## Key Decisions

- **D-15 locked in ROADMAP**: Downstream Phase 31 verification will read
  "skip ONLY the cycle-participating containment edges (keeping the acyclic
  remainder)" — the cycle handler in Wave 2's 31-03 must implement surgical
  removal, not blanket suppression.
- **domain_uri signature break is safe**: `grep -rn 'domain_uri(' packages/graph-io/src/ | grep -v uri.py` returns no matches, confirmed before the edit. The Wave 1 31-03 plan (domains.emit) will be the first real caller.
- **pyyaml is a published dep, not a workspace member**: No `[tool.uv.sources]`
  entry needed. Reuses the same `>=6.0` floor that `workspace-io` already
  declares.

## Deviations from Plan

None — plan executed exactly as written.

**Total deviations:** 0
**Impact:** None.

## Self-Check: PASSED

- Key files modified exist on disk: confirmed (ROADMAP.md, pyproject.toml,
  uri.py, test_uri.py, uv.lock)
- `git log --oneline --grep="31-01"` returns 4 commits (Task 1 + Task 2 +
  RED + GREEN)
- All `<acceptance_criteria>` re-run: PASS
- Plan-level `<verification>` (full graph-io suite): PASS — 215 passed, 1 skipped

## Next Steps

Ready for Wave 1: plans 31-02 (extract `import_scan.py`) and 31-03
(`domains.py` loader + cycle detection) can run in parallel — they touch
disjoint files and both depend only on 31-01.
