---
phase: 28-schema-v2-uri-foundation
plan: 03
subsystem: graph-io
tags: [schema-v2, uri, upsert, pitfall-4, sentinel-test]
requires: [28-01]
provides:
  - upsert._upsert_node writes uri to dedicated column (not attrs_json)
  - D-12 sentinel test_upsert_uri_lands_in_column locks PITFALL 4
affects:
  - packages/graph-io/src/graph_io/upsert.py
  - packages/graph-io/tests/test_upsert.py
tech-stack:
  added: []
  patterns:
    - "dict-copy-before-pop to avoid mutating caller's attrs"
    - "column write on both INSERT and UPDATE paths for idempotent re-upsert"
key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/upsert.py
    - packages/graph-io/tests/test_upsert.py
decisions:
  - "Pop uri from a COPY of node.attrs (dict(node.attrs)) — never mutate the caller's dict (T-28-03-01 mitigation)"
  - "_ensure_node passes None for uri so placeholder rows (created for unresolved edge endpoints) keep NULL uri (no behavior change)"
metrics:
  duration_minutes: 5
  completed: 2026-05-25
---

# Phase 28 Plan 03: Upsert URI Column Write Path Summary

Lock PITFALL 4: `_upsert_node` now pops `uri` from a copy of `node.attrs` before serializing, writes it to the dedicated `uri` column on both INSERT and UPDATE paths, and the D-12 sentinel test (`test_upsert_uri_lands_in_column`) proves URIs never contaminate `attrs_json`.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | Pop uri from attrs and write to uri column in _upsert_node + _insert_node | 1bd48bd |
| 2 | Add test_upsert_uri_lands_in_column sentinel + regression guards | 2e78be4 |

## Implementation Detail

### `_upsert_node` (upsert.py)

Before this plan, `_upsert_node` serialized `node.attrs` wholesale into `attrs_json`. Now:

```python
attrs_for_json = dict(node.attrs)          # COPY — do not mutate caller's dict
uri_value = attrs_for_json.pop("uri", None)
```

The remaining attrs are serialized into `attrs_json`; `uri_value` is bound to the new `uri` column on both the UPDATE SQL (`UPDATE nodes SET line=?, attrs_json=?, uri=? WHERE id=?`) and the INSERT SQL (via `_insert_node`).

### `_insert_node`

Gained a 5th positional parameter `uri: str | None`. SQL is now `INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?, ?, ?, ?, ?, ?)`.

### `_ensure_node`

Updated to honor the new `_insert_node` signature: `_insert_node(conn, key, None, None, None)`. Placeholder rows created for unresolved edge endpoints keep `uri` NULL — no behavior change for non-URI nodes.

## Tests Added

1. **`test_upsert_uri_lands_in_column`** (D-12 sentinel) — asserts a node upserted with `attrs={'uri': 'pkg:org/repo/auth', ...}` has the uri in the column and ABSENT from `attrs_json`; other attrs round-trip unchanged.
2. **`test_upsert_node_without_uri_has_null_uri_column`** — regression guard for the NULL path: nodes without a `uri` attr have `uri IS NULL`.
3. **`test_upsert_uri_idempotent`** — re-upserting the same uri-bearing node preserves uri without duplicating the row.

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/test_upsert.py -x` → 8 passed (5 existing + 3 new)
- `uv run --package graph-io pytest packages/graph-io/tests/test_schema.py -x` → 6 passed
- Acceptance greps all return matches:
  - `attrs.*\.pop\(.uri.` → 1 match in upsert.py
  - `INSERT INTO nodes\(kind, name, path, line, attrs_json, uri\)` → 1 match
  - `UPDATE nodes SET line=\?, attrs_json=\?, uri=\?` → 1 match
  - `node\.attrs\.pop` outside comments/strings → 0 matches (mitigates T-28-03-01)

## Threat Mitigations

| Threat ID | Status | Evidence |
|-----------|--------|----------|
| T-28-03-01 (caller's dict mutation) | Mitigated | `attrs_for_json = dict(node.attrs)` is the only pop target; grep confirms no `node.attrs.pop` |
| T-28-03-02 (PITFALL 4 recurrence) | Mitigated | `test_upsert_uri_lands_in_column` asserts `'uri' not in json.loads(attrs_json)` |
| T-28-03-03 (empty-string uri overwrites) | Accepted | Out of scope for v1.6; no emitter produces empty-string uri |
| T-28-03-04 (v1 attrs_json carryover) | Mitigated by Plan 05 | This plan does not touch the migration path |
| T-28-03-SC (supply chain) | N/A | Zero package installs |

## Deviations from Plan

None — plan executed exactly as written.

## Requirements Closed

- SCHEMA-04 (uri column write path in upsert)

## Self-Check: PASSED

- FOUND: packages/graph-io/src/graph_io/upsert.py (modified)
- FOUND: packages/graph-io/tests/test_upsert.py (modified)
- FOUND commit: 1bd48bd (Task 1)
- FOUND commit: 2e78be4 (Task 2)
