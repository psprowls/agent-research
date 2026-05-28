---
status: passed
phase: 55-dependency-classification-fix
verified: 2026-05-28
requirements: [CLASS-01, CLASS-02]
must_haves_verified: 3
must_haves_total: 3
human_verification: []
---

# Phase 55 Verification

**Status: PASSED** — all three success criteria verified end-to-end against a real
`cg update --full`; both requirements (CLASS-01, CLASS-02) satisfied; full graph-io
test suite green.

## Goal

> Workspace packages are never double-classified as both a `package`/`app` node and a
> `dependency` node in the same repo.

Achieved: a dependency declaration naming a workspace package is no longer emitted as a
`dependency` node; the relationship is carried by a `depends_on_package` edge and a
retargeted `used_by` edge, and surfaces in `cg describe-package`.

## Success Criteria

### SC#1 — No `dependency` node (no `dep_<name>.md`) for any workspace-package name
**VERIFIED.** End-to-end: a throwaway workspace where `beta` declares `graph-io` (whose
own manifest name is `graph_io`) plus external `boto3`, run through `cg update --full`:
- `SELECT COUNT(*) FROM nodes WHERE kind='dependency' AND name IN ('graph_io','graph-io')` → **0**
- External `boto3` `dependency` node still present → **1** (suppression is name-scoped, not blanket)

Unit coverage: `test_workspace_dep_suppressed_and_depends_on_package_emitted` (CLASS-01 +
external regression).

### SC#2 — Internal package→package relationship is a `depends_on` edge between the two nodes
**VERIFIED** (per the D-04/D-05 amendment: the edge kind is `depends_on_package`, a
distinct kind chosen for query ergonomics — REQUIREMENTS.md CLASS-02 and the line-54 scope
note both name it). End-to-end: exactly one `depends_on_package` edge
`(package, beta) → (package, graph_io)`. The retargeted `used_by` edge also points at the
real package node (D-07), verified for both package and app targets.

Unit coverage: `test_workspace_dep_suppressed_and_depends_on_package_emitted`,
`test_internal_dep_on_app_target_resolves_app_kind`, `test_internal_dep_edges_dedupe_per_consumer`.

### SC#3 — Edge surfaces in `cg describe-package`
**VERIFIED.** End-to-end JSON output:
- `describe-package graph_io` → `internal_dependents == ['beta']` (incoming, SC#3-mandatory)
- `describe-package beta` → `internal_dependencies == ['graph_io']` (outgoing, D-08)

Unit coverage: `test_describe_package_internal_deps_and_dependents` (query) +
`test_cg_describe_package_internal_deps_json` / `_dependents_json` / `_deps_human` (CLI).

## Requirements Traceability

| Requirement | Plan(s) | Status |
|-------------|---------|--------|
| CLASS-01 | 55-01 | Satisfied — suppression in `refresh()`, name-scoped, normalized, cross-ecosystem |
| CLASS-02 | 55-01 (edge emission) + 55-02 (describe-package surfacing) | Satisfied — `depends_on_package` edge (D-04/D-05 amendment, reflected in REQUIREMENTS.md) emitted and surfaced both directions |

Both PLAN frontmatter `requirements` arrays (`[CLASS-01, CLASS-02]` and `[CLASS-02]`) are
accounted for; REQUIREMENTS.md marks both complete under Phase 55.

## Locked-Decision Compliance (55-CONTEXT.md D-01..D-08)

- D-01/D-02/D-03 suppression (normalized, once, cross-ecosystem) — implemented + tested.
- D-04 new `depends_on_package` edge kind — implemented; D-05 amendment already reflected
  in REQUIREMENTS.md (CLASS-02 + line ~54), so no verifier mismatch.
- D-06 manifest-declaration-driven emission — implemented (same parse as suppression).
- D-07 two-edge redundancy + stored-kind dst resolution — implemented (inline comment present)
  + tested (app-target case).
- D-08 both-direction surfacing — implemented + tested.

## Test Posture

Full graph-io suite: **462 passed, 1 skipped** (pre-existing
`test_domain_depends_on_no_self_loop`), **1 xfailed**. No cross-phase regressions in the
touched package. The 4 known pre-existing `wiki-io/test_overview_template_wikilinks.py`
failures (tracked in STATE.md, slated for Phase 56) are unrelated — Phase 55 touched only
`graph-io`.

## Code Review

`55-REVIEW.md`: status clean (0 Critical, 0 Warning, 1 Info — no action required).

## Human Verification

None required — all criteria verified by automated end-to-end checks.
