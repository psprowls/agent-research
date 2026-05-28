---
phase: 49-builtin-kind-graph-io
plan: "02"
subsystem: graph-io
tags: [builtin-kind, graph-io, stdlib-classification, node-cache, import-scan]
dependency_graph:
  requires:
    - 49-01  # _VALID_KINDS "builtin" + builtin_uri already in place
  provides:
    - graph_io.builtins.refresh (stdlib scan + Builtin node + used_by edge emission)
    - graph_io.update.run calls builtins.refresh inside existing transaction
    - tests/test_builtins.py: 11 tests covering D-01..D-09 + cache + idempotency
  affects:
    - packages/graph-io
tech_stack:
  added: []
  patterns:
    - Dedup-and-emit accumulator (mirrors packages.py:203-220)
    - Per-major disk cache for Node builtins (D-02: .graph/cache/node-builtins-<major>.json)
    - Silent-skip on missing subprocess (D-03: frozenset() + zero stderr)
    - Top-level module normalization (D-05: os.path → os; D-06: node:fs/promises → fs)
    - Symbol union across files per (package, builtin) (D-08/D-09)
key_files:
  created:
    - packages/graph-io/src/graph_io/builtins.py
    - packages/graph-io/tests/test_builtins.py
  modified:
    - packages/graph-io/src/graph_io/update.py
decisions:
  - "Defined _SCAN_EXTENSIONS_JS inline in builtins.py to break circular import chain (update → builtins → import_scan → structural_nodes → update)"
  - "Used frozenset membership check with both normalized form and raw spec for Node builtin matching (handles both node:fs and fs forms in the builtin list)"
  - "_extract_python_symbols uses the matched line context (start/end offsets) to extract from-import symbols without a second finditer pass"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-27"
  tasks_completed: 3
  tasks_total: 3
---

# Phase 49 Plan 02: Builtin Emission Module Summary

## One-liner

Implemented `graph_io/builtins.py` with Python stdlib + Node.js builtin detection, per-major cache, dedup-and-emit for Builtin nodes + `used_by` edges, wired into `update.run()`, covered by 11 unit/integration tests.

## What Was Built

### Task 1: `packages/graph-io/src/graph_io/builtins.py` (new module)

The Builtin classification + emission module, a sibling of `packages.py`. Exports one public function: `refresh(conn, *, repo_root, workspace, ctx)`.

Module structure:
- `_PYTHON_STDLIB` — `sys.stdlib_module_names` frozenset (D-01/D-04)
- `_is_python_stdlib(module_str)` — top-level segment membership check (D-05)
- `_normalize_node_spec(spec)` — strips `node:` prefix + subpath (D-06)
- `_node_major()` — subprocess `node --version` with timeout + silent-skip (D-03)
- `_harvest_node_builtins()` — subprocess `node -e` JSON harvest with silent-skip
- `_load_node_builtins(cache_dir)` — per-major cache: read on hit, write on miss, empty frozenset on failure (D-02/D-03)
- `_scan_package(repo_root, pkg_name, file_rels, node_builtins)` — per-package file scan; Python + JS; symbol capture via line-context regex
- `refresh(conn, ...)` — outer loop: loads packages from DB, loads Node builtins once, scans each package, emits one `GraphNode` per `(lang, module_name)` + one `GraphEdge` per `(pkg, lang, module_name)` with `imported_symbols`

**Hard constraints obeyed:**
- Does NOT open a SQLite transaction (reuses caller's via `store.transaction`)
- Does NOT write to stderr on any failure
- Does NOT emit Function/Symbol nodes (D-07)
- Does NOT preserve file-level edge granularity (D-09)
- Does NOT bump `SCHEMA_VERSION` (D-10)

**Deviation [Rule 3 - Circular Import Fix]:** `import_scan._SCAN_EXTENSIONS_JS` could not be imported at module level because `import_scan` → `structural_nodes` → `update` creates a cycle. Fixed by defining `_SCAN_EXTENSIONS_JS` inline in `builtins.py` (same value: `frozenset((".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs"))`). This is the correct resolution per the plan's "Hard constraints" which prohibit circular imports.

### Task 2: `packages/graph-io/src/graph_io/update.py` (modified)

Two surgical changes:
1. `from graph_io import _ignore, builtins, packages, resolve, schema, store, upsert` (alphabetical insertion of `builtins`)
2. `builtins.refresh(conn, repo_root=repo_root, workspace=workspace, ctx=ctx)` inserted after `packages.refresh(...)` at line 276, before `resolve.sweep(conn)` at line 309 — inside the existing `store.transaction(conn)` block.

### Task 3: `packages/graph-io/tests/test_builtins.py` (new, 11 tests)

| Test function | Coverage |
|---------------|----------|
| `test_python_stdlib_emits_builtin_nodes` | BUILTIN-01 / D-01 / D-04 / D-05 |
| `test_python_stdlib_top_level_only` | D-05 (os.path → os) |
| `test_node_spec_normalization` | D-06 (pure unit, three cases) |
| `test_node_stdlib_emits_builtin_nodes` | BUILTIN-02 / D-06 (skips if no node binary) |
| `test_node_dependency_vs_builtin_classification` | BUILTIN-03 (express stays dependency) |
| `test_builtin_node_attrs_and_uri` | BUILTIN-04 / D-15 (language, module_name, uri) |
| `test_used_by_edge_dedup_and_symbol_union` | BUILTIN-05 / D-08 / D-09 (sorted union) |
| `test_emit_is_idempotent` | idempotency invariant |
| `test_node_builtins_cache_lifecycle` | D-02 (created / reused / re-harvested) |
| `test_silent_skip_when_node_missing` | D-03 (no exception, no stderr, no cache file) |
| `test_update_run_invokes_builtins_refresh` | Task 2 wiring integration |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `ff97eb4` | feat(49-02): add builtins.py — stdlib classification + Node cache + emit |
| 2 | `6651bef` | feat(49-02): wire builtins.refresh() into update.run() transaction |
| 3 | `1fc7663` | test(49-02): add test_builtins.py — D-01..D-09 + cache + silent-skip + idempotency |

## Verification

- `uv run --package graph-io pytest packages/graph-io/tests/test_builtins.py -x -q` → 11 passed
- `uv run --package graph-io pytest packages/graph-io/tests/test_e2e.py -x -q` → 1 passed
- `uv run --package graph-io pytest packages/graph-io/tests/ -q` → 391 passed, 3 skipped, 1 xfailed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Circular Import] Broke import_scan dependency to avoid circular import**
- **Found during:** Task 1 verification (circular import error at `update` → `builtins` → `import_scan` → `structural_nodes` → `update`)
- **Issue:** The plan specified importing `_SCAN_EXTENSIONS_JS` from `import_scan`, which triggers the circular chain
- **Fix:** Defined `_SCAN_EXTENSIONS_JS` inline in `builtins.py` with the same frozenset value
- **Files modified:** `packages/graph-io/src/graph_io/builtins.py`
- **Commit:** `6651bef` (included in Task 2 commit)

## Known Stubs

None — all functionality is implemented and exercised by tests.

## Threat Flags

None — all threat-model mitigations from the plan's STRIDE register are implemented:
- T-49-02-T1: `subprocess.run` argv is a hardcoded literal string list (verified)
- T-49-02-T2: Cache path composed from `graph_dir(workspace)` only; write is `try/except OSError`
- T-49-02-T3: `json.loads()` only; `JSONDecodeError` → D-03 silent skip
- T-49-02-D: `timeout=_NODE_SUBPROCESS_TIMEOUT_S` (5s) on all subprocess calls

## Self-Check: PASSED

- `packages/graph-io/src/graph_io/builtins.py` — FOUND (419 lines, `def refresh` count = 1)
- `packages/graph-io/tests/test_builtins.py` — FOUND (519 lines, 11 test functions)
- `packages/graph-io/src/graph_io/update.py` — FOUND (contains `builtins.refresh(`)
- Commit `ff97eb4` — verified in git log
- Commit `6651bef` — verified in git log
- Commit `1fc7663` — verified in git log
- Full test suite: 391 passed, 3 skipped, 1 xfailed
