---
phase: 28-schema-v2-uri-foundation
plan: 01
subsystem: graph-io
tags: [schema, ddl, sqlite, sentinels]
requires: []
provides:
  - "graph_io.schema.SCHEMA_VERSION == 2"
  - "nodes.uri (nullable TEXT) column"
  - "idx_nodes_uri index on nodes(uri)"
  - "Sentinel tests: test_schema_version_is_two, test_nodes_table_has_uri_column"
affects:
  - "downstream plans 28-03 (upsert) and 28-05 (full-rebuild path) depend on the column existing"
  - "every Phase 29-31 emitter that writes uri reads through this column"
tech-stack:
  added: []
  patterns:
    - "PRAGMA table_info introspection for column-presence sentinel"
key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/schema.py
    - packages/graph-io/tests/test_schema.py
decisions:
  - "Column appended after attrs_json — preserves existing column order so positional index references in downstream code remain stable until they explicitly opt into uri."
  - "idx_nodes_uri name follows the existing idx_nodes_<column> convention (D-locks left this as Claude's Discretion)."
  - "No UNIQUE constraint on uri (D-09 / D-10 lock; v1.7 explicitly defers UNIQUE)."
metrics:
  duration_minutes: 4
  completed_date: 2026-05-25
  tasks_completed: 2
  files_touched: 2
---

# Phase 28 Plan 01: Schema v2 + URI Column Foundation Summary

Bumped `graph-io` to schema v2 by adding a nullable `uri TEXT` column to the `nodes` CREATE TABLE plus a new `idx_nodes_uri` index, and updated the sentinel test set to D-12 names — the wedge that downstream Phase 28 plans (03, 05) and every Phase 29-31 emitter drive into.

## What Was Built

### Task 1 — Schema constant + DDL bump (`a0f5905`)
- `packages/graph-io/src/graph_io/schema.py`
  - `SCHEMA_VERSION`: `1` → `2`
  - `_DDL_STATEMENTS`: nodes CREATE TABLE gains a trailing `uri TEXT` column (nullable, no DEFAULT, no UNIQUE per D-09/D-10 lock and v1.7 deferral)
  - `_DDL_STATEMENTS`: new statement `CREATE INDEX IF NOT EXISTS idx_nodes_uri ON nodes(uri)`
  - `apply_schema` signature unchanged; idempotency preserved (verified by existing `test_apply_schema_is_idempotent`)

### Task 2 — Sentinel tests (`03e1b0c`)
- `packages/graph-io/tests/test_schema.py`
  - Renamed `test_schema_version_is_one` → `test_schema_version_is_two`, assertion bumped to `== 2` (D-12 sentinel #1)
  - Added `test_nodes_table_has_uri_column` which calls `apply_schema(conn)`, runs `PRAGMA table_info('nodes')`, and asserts exactly one `uri` row of type `TEXT` (case-insensitive) (D-12 sentinel #2)
  - Updated `test_apply_schema_creates_indexes` expected set to include `"idx_nodes_uri"`

## Verification Results

| Check | Result |
|-------|--------|
| `uv run --package graph-io pytest packages/graph-io/tests/test_schema.py -x` | 6 passed |
| `uv run --package graph-io pytest packages/graph-io/tests/ -x` (regression) | 114 passed |
| `uv run --package graph-io python -c "from graph_io import schema; assert schema.SCHEMA_VERSION == 2"` | exit 0 |
| `grep -c "UNIQUE"` in schema.py (non-comment) | 0 (no UNIQUE on uri) |
| `grep "SCHEMA_VERSION = 2"` | match at line 12 |
| `grep -E "uri\s+TEXT"` | match inside nodes CREATE TABLE |
| `grep "idx_nodes_uri"` (schema.py) | match in CREATE INDEX statement |
| `grep "def test_schema_version_is_one"` | no match (renamed cleanly) |
| `grep "def test_schema_version_is_two"` | match |
| `grep "def test_nodes_table_has_uri_column"` | match |

All acceptance criteria in both task `<acceptance_criteria>` blocks pass.

## Decisions Made

1. **Column placement: appended after `attrs_json`.** Preserves existing column ordinals so any positional access in downstream code (none currently, but harmless caution) does not shift.
2. **Index name: `idx_nodes_uri`.** Matches the existing `idx_nodes_kind_name` / `idx_nodes_path` convention. CONTEXT.md left this as Claude's Discretion.
3. **`PRAGMA table_info` is the introspection vector for the column sentinel.** It returns `(cid, name, type, notnull, dflt_value, pk)`; the sentinel asserts on `name` and `type` only — `notnull == 0` (nullable) is implied by the absence of `NOT NULL` in the DDL and is already locked by D-09 at plan level, so the sentinel does not re-assert it to avoid coupling to PRAGMA row layout beyond what is necessary.

## Deviations from Plan

None — plan executed exactly as written. TDD-ordered execution noted: Task 1 modifies schema first (making `test_schema_version_is_one` red), Task 2 then renames the sentinel and adds the column-presence test. This matches the plan's explicit task ordering and verify commands; no out-of-order or scope-creep modifications were made.

## Files Modified

- `packages/graph-io/src/graph_io/schema.py` — `+4 / -2` (constant bump + uri column + idx_nodes_uri statement)
- `packages/graph-io/tests/test_schema.py` — `+12 / -2` (rename sentinel, add uri-column sentinel, expand expected-index set)

## Commits

| Hash | Message |
|------|---------|
| `a0f5905` | feat(28-01): bump schema to v2 with uri column and idx_nodes_uri index |
| `03e1b0c` | test(28-01): add v2 schema sentinels and update index expectations |

## Threat Flags

None — no new trust boundaries or external surface introduced; T-28-01-01 and T-28-01-02 are both mitigated by the sentinel suite and the `UNIQUE`-count grep gate.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: packages/graph-io/src/graph_io/schema.py (modified)
- FOUND: packages/graph-io/tests/test_schema.py (modified)
- FOUND commit a0f5905 in git log
- FOUND commit 03e1b0c in git log
- All sentinel tests green; full graph-io suite (114 tests) green
