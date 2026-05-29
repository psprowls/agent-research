---
phase: 58-entity-page-index-uat-follow-ups
plan: "03"
subsystem: wiki-io
tags: [index-generator, test-suite, uri-keyed, fan-out-fix, sc3]
one_liner: "Switch three consumer-resolution SQL queries from ts.name to ts.uri in index_generator.py, with a fan-out regression guard proving distinct per-suite results"
depends_on: ["58-02"]
provides: [sc3-renderer-fix, uri-keyed-consumer-resolution, fan-out-regression-guard]
affects: []
tech_stack:
  added: []
  patterns: [uri-keyed-sql-parameterization, direct-sqlite-insertion-for-same-name-fixtures]
key_files:
  modified:
    - packages/wiki-io/src/wiki_io/index_generator.py
    - packages/wiki-io/tests/test_index_generator.py
decisions:
  - "Add uri= parameter to _compute_qualifying_domains with default empty string — backward compatible; non-test_suite branches ignore it"
  - "Keep entity_name= on _consumer_pkgs/_consumer_pkgs_in_domain as a default-empty fallback so dependency callers are unchanged"
  - "Fan-out fixture uses direct SQLite INSERT (bypassing upsert_records) to create same-name/distinct-path/distinct-URI suite nodes"
  - "Snapshot rebaseline deferred — no live graph in execution environment; hand-built fan-out guard stands as automated proof (D-10 partial)"
metrics:
  duration_minutes: 30
  completed_date: "2026-05-29"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  tests_added: 1
---

# Phase 58 Plan 03: URI-Keyed Consumer Resolution Summary

**One-liner:** Switch three consumer-resolution SQL queries from `ts.name = ?` to `ts.uri = ?` in `index_generator.py`, with a fan-out regression guard proving distinct per-suite results.

## What Was Built

Fixed the renderer-side half of SC#3 (Item #3: Test-Suite Fan-Out). Three SQL queries in `index_generator.py` previously resolved consumer packages by `ts.name = ?`. Because all 9 package-owned suites in the live graph shared `name='tests'` before Plan 02's rename, every query with `name='tests'` matched all 9 suites — each suite appeared as "tested by" all 23 `tests`-edge targets.

The fix switches all three queries to join on `ts.uri = ?` (URIs are first-class DB columns, unique and stable — see RESEARCH §"URI impact"). The `uri` variable was already extracted at `_place_entities:369` (`uri = node.attrs.get("uri") or ""`), so threading it through is a callsite-only change.

### Changes

**`_compute_qualifying_domains` (line 163):**
- Added `uri: str = ""` parameter (default keeps all non-test_suite callers unchanged)
- `test_suite` branch: `ts.name = ?` → `ts.uri = ?`; binds `(uri,)` instead of `(name,)`
- Caller at `_place_entities:371` now passes `uri=uri`

**`_consumer_pkgs_in_domain` (line 225):**
- Renamed `entity_name: str` → `entity_uri: str = ""`; kept `entity_name: str = ""` for dependency arm
- `test_suite` branch: `ts.name = ?` → `ts.uri = ?`; binds `(entity_uri, domain_name)`

**`_consumer_pkgs` (line 269):**
- Same signature change as `_consumer_pkgs_in_domain`
- `test_suite` branch: `ts.name = ?` → `ts.uri = ?`; binds `(entity_uri,)`

**`_place_entities` (line 366):**
- Updated `_compute_qualifying_domains` call to pass `uri=uri`
- Split the `if kind in ("dependency", "test_suite")` block: `test_suite` calls with `entity_uri=uri`; `dependency` calls with `entity_name=node.name`

**Two existing qualifying-domain tests** for `test_suite` kind updated to pass `uri=` alongside `name=` (the function now uses `uri` for the test_suite branch).

## Tasks Completed

### Task 1: Switch three consumer-resolution queries from ts.name to ts.uri (TDD)

**RED commit:** `e38295a` — Added `_make_fanout_fixture` helper and `test_consumer_pkgs_fanout_regression_guard` calling `_consumer_pkgs(entity_uri=...)`. Confirmed failing with `TypeError: _consumer_pkgs() got an unexpected keyword argument 'entity_uri'`.

**GREEN commit:** `d0bf33d` — Implemented all three query changes plus callsite updates. Updated two existing qualifying-domain tests. All 54 tests pass, 1 skipped (snapshot, no live graph).

**Acceptance criteria verified:**
- `grep -c 'ts.name = ?' index_generator.py` → 0
- `grep -c 'ts.uri = ?' index_generator.py` → 3
- No callsite passes `entity_name=node.name` or `name=node.name` for suite resolution
- Fan-out regression guard passes

### Task 2: Rebaseline live-graph snapshot and run full cross-package suite

No live graph available in the execution environment — the snapshot test `test_snapshot_against_agent_research` is skip-guarded and was skipped (not failed), as expected per the plan's acceptance criteria.

**Full cross-package suite result:**
```
1556 passed, 41 skipped, 2 xfailed in 173.90s
```

All tests pass. Item #3 is confirmed end-to-end across graph-io (Plan 02 rename) + wiki-io (this plan's renderer fix).

## Snapshot Rebaseline Deferral (D-10)

The live-graph syrupy snapshot (`test_snapshot_against_agent_research`) was not regenerated in this execution — no `graph.db` is present at any parent directory of the worktree. The snapshot test is skip-guarded (`@pytest.mark.skipif(_WS_ROOT is None, reason="no live agent-research graph")`).

**Deferral standing proof:** The hand-built `_make_fanout_fixture` + fan-out regression guard proves the URI-keyed behavior is correct for the exact pre-Plan-02 collision scenario (two `'tests'`-named suites with distinct paths and URIs, each testing a different package).

**To rebaseline the snapshot:** After running `cg update --full` on a live workspace (per 58-02's OQ#3 resolution), run:
```bash
uv run --package wiki-io pytest packages/wiki-io/tests/test_index_generator.py::test_snapshot_against_agent_research --snapshot-update
```

## Deviations from Plan

### Auto-adjusted: Fixture helper uses direct SQLite INSERT

**Found during:** Task 1 fan-out test development
**Issue:** `_make_index_fixture_graph` calls `upsert_records` which collapses same-`(kind, name, path)` tuples. Two suites named `'tests'` with empty paths would upsert as a single row — only the second URI would survive. The test would silently test a single suite rather than a fan-out scenario.
**Fix:** Added `_make_fanout_fixture()` helper that inserts nodes directly via `conn.execute(INSERT INTO nodes...)`, setting distinct paths (`packages/alpha/tests`, `packages/beta/tests`) so both rows coexist. This mirrors the actual production data shape (suites always have real paths).
**Files modified:** `packages/wiki-io/tests/test_index_generator.py`
**Commit:** `d0bf33d`

### Auto-adjusted: Keep backward-compatible default parameters

**Found during:** Task 1 implementation
**Issue:** Removing `entity_name` entirely from `_consumer_pkgs` and `_consumer_pkgs_in_domain` would break the dependency callers that still use `entity_name=node.name`.
**Fix:** Added `entity_uri: str = ""` and kept `entity_name: str = ""` as a default. Dependency callers pass `entity_name=`; test_suite callers pass `entity_uri=`. Both are keyword-only (after `*`).
**Files modified:** `packages/wiki-io/src/wiki_io/index_generator.py`
**Commit:** `d0bf33d`

## TDD Gate Compliance

- RED commit: `e38295a` — failing test (TypeError: entity_uri not valid kwarg)
- GREEN commit: `d0bf33d` — passing implementation
- REFACTOR: not needed; code is clean

## Verification Results

```
uv run pytest packages/wiki-io/tests/test_index_generator.py -x -q
54 passed, 1 skipped in 0.24s

uv run pytest -x -q
1556 passed, 41 skipped, 2 xfailed in 173.90s
```

## Known Stubs

None — all query changes are production-ready. Snapshot rebaseline is documented as a deferred action requiring a live graph, not a stub.

## Threat Surface Scan

No new threat surface. The `ts.name = ?` → `ts.uri = ?` change is a column swap within already-parameterized SQL. No string interpolation added. Consistent with T-58-03 threat register disposition (accept).

## Self-Check

Files exist:
- [x] `packages/wiki-io/src/wiki_io/index_generator.py` — modified
- [x] `packages/wiki-io/tests/test_index_generator.py` — modified

Commits exist:
- [x] `e38295a` — RED phase
- [x] `d0bf33d` — GREEN phase

## Self-Check: PASSED
