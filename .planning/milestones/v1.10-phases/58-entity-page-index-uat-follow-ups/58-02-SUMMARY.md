---
phase: 58-entity-page-index-uat-follow-ups
plan: "02"
subsystem: graph-io
tags: [test-suite, scan, naming, uniqueness, graph-io]
one_liner: "Rename package-owned test_suite nodes from basename 'tests' to unique '<owner>-<kind>-tests' at all four scan-side mutation points"
depends_on: []
provides: [unique-suite-names, sc3b-uniqueness-guard, oq3-resolution]
affects: [wiki-io-plan-03]
tech_stack:
  added: []
  patterns: [f-string-qualified-naming, kind-before-name-ordering]
key_files:
  modified:
    - packages/graph-io/src/graph_io/test_suites.py
    - packages/graph-io/tests/test_test_suites.py
decisions:
  - "Use literal kind_attr value in qualified name (e.g. 'integration', not 'int') — mechanical, no abbreviation map needed (OQ#1)"
  - "OQ#3 resolved: cg update --full is the correct stale-node remediation — no bespoke DELETE added to test_suites.py"
  - "kind_attr computed before suite_name assignment to avoid NameError (Pitfall 2 from RESEARCH)"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-29"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  tests_added: 3
---

# Phase 58 Plan 02: Rename Package-Owned Test Suite Nodes Summary

**One-liner:** Rename package-owned test_suite nodes from basename 'tests' to unique `<owner>-<kind>-tests` at all four scan-side mutation points in test_suites.py.

## What Was Built

Fixed the scan-side half of SC#3b (Item #3: Test-Suite Fan-Out): package-owned `test_suite` nodes previously always received the name `Path(rel_path).name` (= `'tests'` for every Python package, `'__tests__'` for every JS package). This caused all 9 suites in the live graph to share the name `'tests'`, making any name-keyed SQL query (`ts.name = ?`) return all 23 `tests`-edge targets as consumers of every single suite.

The fix renames package-owned suites to `<owner_name>-<suite_kind>-tests` (e.g., `wiki-io-unit-tests`, `graph-io-integration-tests`). Repository-owned suites keep their full `rel_path` name (already unique, unchanged per D-09). URIs are unchanged — `test_suite_uri` keys on `rel_path`, not `suite_name`.

## Tasks Completed

### Task 1: Rename package-owned suite nodes at all four scan-side mutation points (TDD)

**Files:** `packages/graph-io/src/graph_io/test_suites.py`, `packages/graph-io/tests/test_test_suites.py`

**RED commit:** `50989ad` — Updated test assertions to expect new qualified names (`foo-unit-tests`, `jspkg-unit-tests`), added negative assertions that old basenames are absent. Tests confirmed failing.

**GREEN commit:** `5c9cfe7` — Implemented all four changes:

| Location | Change |
|----------|--------|
| Main emit loop — node creation (~line 335-340) | Reordered: compute `kind_attr` BEFORE `suite_name`; replaced `Path(r.rel_path).name` with `f"{r.owner_name}-{kind_attr}-tests"` |
| Main emit loop — `physically_contains` dst (~line 371) | Uses `suite_name` which is now the qualified form — no separate change needed |
| Re-parenting loop — DB lookup (~line 383-390) | Added `_rp_kind_attr` computation; replaced `Path(r.rel_path).name` with `f"{r.owner_name}-{_rp_kind_attr}-tests"` |
| `_emit_tests_edges` — tests edge src (~line 443-447) | Added `_te_kind_attr` computation; replaced `Path(r.rel_path).name` with `f"{r.owner_name}-{_te_kind_attr}-tests"` |

All four `Path(r.rel_path).name` occurrences for package-owned suites removed (`grep -c` returns 0).

### Task 2: SC#3b uniqueness guard and OQ#3 stale-node documentation

**Commit:** `119695b`

Added `test_suite_names_unique_after_multi_package_emit` to `test_test_suites.py`:
- Multi-package fixture: `packages/foo/tests` + `packages/bar/tests`
- Asserts `SELECT name, COUNT(*) FROM nodes WHERE kind='test_suite' GROUP BY name HAVING COUNT(*) > 1` returns 0 rows
- Asserts qualified names `foo-unit-tests` and `bar-unit-tests` exist
- Documents OQ#3 resolution in docstring

## OQ#3 Resolution (for Plan 03 and verification to consume)

**Stale-node handling:** `cg update --full` is the correct and sufficient remediation for sweeping stale `tests`-named suite nodes from a live graph after upgrading to this rename.

`update.py:285` runs `DELETE FROM nodes WHERE kind NOT IN ('package','app','builtin') AND path IS NOT NULL AND path NOT IN (...tracked...)` before re-emitting during a full scan. This sweeps stale `('test_suite','tests',<path>)` nodes before the new `('test_suite','<pkg>-<kind>-tests',<path>)` nodes are emitted.

**Incremental `cg update` does NOT sweep stale nodes** — it upserts by `(kind, name, path)` key, so old `tests`-named nodes linger alongside the new qualified ones. Any workspace upgraded from pre-Phase-58-02 code must run `cg update --full` once to clear stale suite nodes.

**No bespoke DELETE was added to `test_suites.py`** — the `--full` path is the chosen resolution (RESEARCH OQ#3 option b).

## Verification Results

```
uv run --package graph-io pytest packages/graph-io/tests/ -x -q
464 passed, 3 skipped, 1 xfailed
```

Acceptance criteria met:
- `grep -c 'Path(r.rel_path).name' test_suites.py` → 0
- `grep -c 'f"{r.owner_name}-{' test_suites.py` → 3 (all four mutation points use the pattern; two share a single computation)
- `test_test_suites.py:111` repository-owned assertion `[("tests","tests")]` unchanged
- Old package-owned assertion `("tests","packages/foo/tests")` appears only as a negative assertion (`not in rows`)
- SC#3b uniqueness query returns 0 rows in the new test

## Deviations from Plan

None — plan executed exactly as written.

## Key Decisions

1. **Literal kind_attr, no abbreviation (OQ#1):** Used `kind_attr` value directly (`"integration"`, `"unit"`, etc.) rather than an abbreviation dict. Result is `foo-integration-tests` not `foo-int-tests`. Mechanical and unambiguous.

2. **OQ#3: cg update --full, no bespoke DELETE:** The existing full-scan DELETE in `update.py:285` is the right place for stale-node cleanup. Adding a bespoke DELETE in `test_suites.py` would duplicate logic and create a maintenance burden. Documented as a deployment note.

3. **TDD gate compliance:** RED commit (`50989ad`) → GREEN commit (`5c9cfe7`) — both exist in git log. REFACTOR not needed; code is clean.

## Threat Surface Scan

No new threat surface. Suite names are derived from local filesystem paths via f-string and stored as a SQLite column value. No query interpolation; all lookups remain parameterized. Consistent with T-58-02 threat register disposition (accept).

## Self-Check

Files exist:
- [x] `packages/graph-io/src/graph_io/test_suites.py` — modified
- [x] `packages/graph-io/tests/test_test_suites.py` — modified

Commits exist:
- [x] `50989ad` — RED phase (failing tests)
- [x] `5c9cfe7` — GREEN phase (implementation)
- [x] `119695b` — Task 2 (uniqueness guard)

## Self-Check: PASSED
