---
phase: 49-builtin-kind-graph-io
plan: "01"
subsystem: graph-io
tags: [builtin-kind, graph-io, wiki-io, uri, schema]
dependency_graph:
  requires: []
  provides:
    - graph_io.queries._VALID_KINDS admits "builtin"
    - graph_io.uri.builtin_uri(language, module_name)
  affects:
    - packages/graph-io
    - packages/wiki-io
tech_stack:
  added: []
  patterns:
    - URI builder pattern (one-line pure function mirroring dependency_uri)
    - _VALID_KINDS frozenset admission for new node kind
key_files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/src/graph_io/uri.py
    - packages/wiki-io/src/wiki_io/entity_writer.py
    - packages/graph-io/tests/test_queries.py
decisions:
  - "builtin_uri follows dependency_uri one-liner pattern: return f\"builtin:{language}/{module_name}\""
  - "Phase 49 D-16 exclusion documented as comment above ADMITTED_KINDS, not via code change"
  - "Tests placed adjacent to test_valid_kinds_includes_dependency_plugin for logical grouping"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-27"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 49 Plan 01: Builtin Kind Foundation Summary

## One-liner

Added `"builtin"` to `_VALID_KINDS`, added `builtin_uri(language, module_name)` URI builder using the `builtin:<language>/<module_name>` scheme, and documented the Phase 49 D-16 exclusion of `builtin` from `wiki_io.entity_writer.ADMITTED_KINDS`.

## What Was Built

Three minimal changes establish the schema-level foundation for the `builtin` node kind:

1. **`_VALID_KINDS` admission** (`queries.py`): `"builtin"` added to the frozenset with an inline comment referencing Phase 49 D-14. `SCHEMA_VERSION` stays at 2 (D-10 — SQL layer is text-flexible; admission is Python-side only).

2. **`builtin_uri` URI builder** (`uri.py`): One-line pure function `return f"builtin:{language}/{module_name}"` placed immediately after `dependency_uri`, grouped with all other `*_uri` builders. Returns `builtin:python/pathlib`, `builtin:javascript/fs`, etc.

3. **ADMITTED_KINDS D-16 annotation** (`entity_writer.py`): Extended the comment block above the `ADMITTED_KINDS` frozenset to explicitly document that `builtin` is intentionally excluded per Phase 49 D-16 (stdlib modules inspectable via `cg list-builtins` / `cg describe-builtin` but do not warrant standalone wiki pages). The frozenset content is unchanged — still 7 elements; bijection invariant tests continue passing.

4. **Unit tests** (`test_queries.py`): Added `test_valid_kinds_includes_builtin()` and `test_builtin_uri_shape()` adjacent to the existing `test_valid_kinds_includes_dependency_plugin` test. Cover all three URI examples from the BUILTIN-04 spec including dotted submodule (`os.path`).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `564185e` | feat(49-01): admit builtin to _VALID_KINDS and add builtin_uri builder |
| 2 | `bd06366` | docs(49-01): annotate ADMITTED_KINDS with Phase 49 D-16 builtin exclusion |
| 3 | `6e7f14d` | test(49-01): lock _VALID_KINDS builtin admission and builtin_uri shape |

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -x -q` → 76 passed, 1 skipped
- `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_templates.py -x -q` → 16 passed
- Manual assertions: `builtin_uri('python', 'pathlib') == 'builtin:python/pathlib'`, `builtin_uri('javascript', 'fs') == 'builtin:javascript/fs'`, `schema.SCHEMA_VERSION == 2`

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — changes are internal Python constants and comments with no external input surface.

## Self-Check: PASSED

- `packages/graph-io/src/graph_io/queries.py` — FOUND (contains `"builtin"`)
- `packages/graph-io/src/graph_io/uri.py` — FOUND (contains `def builtin_uri`)
- `packages/wiki-io/src/wiki_io/entity_writer.py` — FOUND (contains Phase 49 D-16 annotation)
- `packages/graph-io/tests/test_queries.py` — FOUND (contains both new test functions)
- Commits `564185e`, `bd06366`, `6e7f14d` — all present in git log
