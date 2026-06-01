# Quick Task: Please reclassify these nodes with a kind of  `unresolved_symbol` so that when looking at the DB I am able to identify the reason they lack the full data.  I may in the future decide to drop them entirely, but for now I think this is a good choice

**Date:** 2026-06-01
**Branch:** fix/drop-external-import-stubs

## What Changed
- Store unresolved call/export destination placeholders as `kind='unresolved_symbol'` instead of leaving them indistinguishable from real `function` nodes with `NULL` paths.
- Preserve the intended target kind on edge metadata as `symbol_kind` so `resolve.sweep()` can still resolve exact, ambiguous, and cross-kind matches to concrete code nodes.
- Allow `unresolved_symbol` in graph query kind filters and update health-check reporting for the new placeholder kind.
- Updated tests to assert the new placeholder kind and metadata shape.

## Files Modified
- `packages/graph-io/src/graph_io/upsert.py`
- `packages/graph-io/src/graph_io/queries.py`
- `packages/source-parser/src/source_parser/projections/graph.py`
- `packages/graph-io/tests/test_upsert.py`
- `packages/graph-io/tests/test_resolve.py`
- `packages/graph-io/tests/test_queries.py`
- `scripts/graph_health.py`
- `.gsd/quick/3-please-reclassify-these-nodes-with-a-kin/3-SUMMARY.md`

## Verification
- `uv run --package graph-io pytest packages/graph-io/tests/test_upsert.py packages/graph-io/tests/test_resolve.py packages/graph-io/tests/test_queries.py -q` — 120 passed, 1 skipped.
- `uv run --package graph-io pytest packages/graph-io/tests -q` — 399 passed, 1 skipped.
- Temporary SQLite smoke check confirmed an unresolved `hexdigest` call is stored as `('unresolved_symbol', 'hexdigest', NULL)` with `resolution='unresolved'` and `symbol_kind='function'` edge metadata.
