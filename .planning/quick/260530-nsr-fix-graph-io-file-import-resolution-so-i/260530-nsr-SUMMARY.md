---
phase: quick-260530-nsr
plan: 01
subsystem: graph-io
tags: [graph-io, import-resolution, resolve, deriver-version, idempotency]
requires:
  - graph-io update pipeline (update.run)
  - import_scan JS/python specifier matching
provides:
  - resolve.resolve_file_imports (specifier-stub → real-file-node repointing)
  - import_scan.resolve_js_import_file / resolve_python_import_file (repo-relative FILE resolution)
  - conservative single-candidate cross-kind sweep fallback
  - DERIVER_VERSION = 4 (auto full-rebuild for existing graphs)
affects:
  - graph-io imports/imported-by query results (now point at real file nodes)
tech-stack:
  added: []
  patterns:
    - "name != path discriminator to distinguish specifier stubs from transiently-uri-less real file nodes"
    - "lazy import to break resolve → import_scan → structural_nodes → update cycle"
key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/resolve.py
    - packages/graph-io/src/graph_io/import_scan.py
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/src/graph_io/schema.py
    - packages/graph-io/tests/test_resolve.py
    - packages/graph-io/tests/test_import_scan.py
    - packages/graph-io/tests/test_cli_smoke.py
    - .planning/STATE.md
decisions:
  - "Stub vs real-file discriminator is dst.name != dst.path (not uri IS NULL alone) — _process_files transiently nulls uri on re-upsert, so uri alone caused an idempotency regression"
  - "queries.py left untouched; imported symbol preserved in edge attrs.symbol instead of mutating query layer"
metrics:
  duration: ~45m
  completed: 2026-05-30
---

# Phase quick-260530-nsr: graph-io File-Import Resolution Summary

A new `resolve.resolve_file_imports` pass repoints `imports` edges from raw-specifier
stub nodes onto real repo-relative file nodes (in-repo specifiers → exact/ambiguous,
external → unresolved, never fabricated), wired BEFORE update.py's full-mode cleanup
DELETE so resolved edges survive; plus a conservative single-candidate cross-kind
call/export sweep fallback and `DERIVER_VERSION` 3→4 for auto full-rebuild.

## What Changed

- **import_scan.py**: added `resolve_js_import_file(spec, importing_file, repo_root)` and
  `resolve_python_import_file(module_str, repo_root, pkg_rows)` returning repo-relative
  FILE paths; factored the JS relative-candidate logic into `_js_relative_candidates` /
  `_first_existing_rel` (now matches FILES not directories, so `./sub` → `./sub/index.js`).
  Existing `_match_js_import` / `scan_*` signatures unchanged.
- **resolve.py**: added `resolve_file_imports` — selects specifier-stub `imports` edges
  (`dst.uri IS NULL AND dst.name != dst.path`), resolves the raw specifier to the real
  file node, repoints (exact / ambiguous), leaves external specifiers `unresolved`,
  preserves the imported symbol in `attrs.symbol`, and cleans up orphaned stubs scoped to
  the collected stub ids. Extended `sweep` with a conservative single-candidate cross-kind
  fallback (resolve a path-less code placeholder to the ONE graph-wide function/method/class
  with that name; 0 or 2+ stay unresolved).
- **update.py**: call `resolve.resolve_file_imports(conn, repo_root)` after `builtins.refresh`
  and BEFORE the `if full:` cleanup DELETE.
- **schema.py**: `DERIVER_VERSION` 3 → 4.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import**
- **Found during:** Task 3 (full suite)
- **Issue:** `resolve` importing `import_scan` at module top created the cycle
  `import_scan → structural_nodes → update → resolve` (collection-time ImportError).
- **Fix:** Import `import_scan` lazily inside `resolve_file_imports`; keep `_JS_EXTENSIONS`
  as a local tuple in resolve.py.
- **Commit:** 7a2b213

**2. [Rule 1 - Bug] Imported-symbol loss + shared CLI-smoke fixture encoded the bug**
- **Found during:** Task 3 (full suite)
- **Issue:** `test_cli_smoke` `imported-by` tests relied on the old behavior where the
  imports edge pointed at a raw-specifier stub node whose `name` was the imported symbol.
  Post-fix the edge points at the real file node, so symbol-level filtering broke.
- **Fix:** Preserve the imported symbol on the repointed edge in `attrs.symbol`
  (queries.py left out of scope per constraints). Reworked the demo fixture to be genuinely
  first-party-importable (`src/demo/__init__.py`) so resolution actually fires; query
  `imported-by` by the resolved repo-relative path; symbol-filter test now reflects
  file-level resolution semantics.
- **Commit:** 7a2b213

**3. [Rule 1 - Bug] Idempotency regression across repeat full builds**
- **Found during:** Task 3 (live re-audit)
- **Issue:** `_process_files` re-upserts file nodes with `uri=NULL` (uri is re-attached
  later by `structural_nodes.emit`). On a repeat full build, already-resolved real file
  nodes transiently had `uri IS NULL`, so the stub-selection query mistook them for
  specifier stubs and flipped their resolved edges back to `unresolved` (live: 822 exact
  collapsed to 244 exact / 578 unresolved on the 2nd full build).
- **Fix:** Added `dst.name != dst.path` to the stub-selection predicate — real file nodes
  always have `name == path` (verified 1464/1464 on the live db); specifier stubs have
  `name`=symbol, `path`=specifier. This discriminator is independent of the transient uri
  state. Idempotent across repeat full + incremental afterward.
- **Commit:** b15d433

## Live Re-Audit (mono-repo)

- Source repo: `/Users/pat/Personal/mono-repo`
- Workspace: `/Users/pat/Personal/graph-wiki/mono-repo-live` (db: `<ws>/.graph/code.db`)
- Audit: `scripts/graph_health.py` + direct sqlite resolution counts.

| Scenario | imports total | exact | ambiguous | unresolved | NULL-uri file nodes |
|----------|--------------:|------:|----------:|-----------:|--------------------:|
| **PRE-FIX** full (deriver 3, stale db) | 0 | 0 | 0 | 0 | 0 (import graph destroyed) |
| **PRE-FIX** scan/incremental (plan baseline) | ~5602 | 0 | 0 | ~5602 | 3003 |
| **POST-FIX** full (clean) | 822 | 822 | 0 | 0 | 0 |
| **POST-FIX** full (repeat ×2/×3 — idempotent) | 822 | 822 | 0 | 0 | 0 |
| **POST-FIX** incremental (no-op, same HEAD) | 822 | 822 | 0 | 0 | 0 |
| **POST-FIX** fresh scan (full=False) | 5165 | 822 | 0 | 4168 | 2176 |

Notes:
- POST-FIX full: every surviving import edge resolves exactly; NULL-uri file nodes = 0
  (the must-have for full mode). Idempotent — repeat full and incremental hold at 822/822/0.
- POST-FIX fresh scan: the same 822 in-repo specifiers resolve exact; the 4168 unresolved
  and 2176 NULL-uri stubs are genuinely external/third-party specifiers (`react`,
  `@electron-forge/*`, bare first-party scoped packages like `@psprowls/shared-auth-ts`)
  that have no in-repo FILE node — correctly left unresolved (nothing fabricated). The
  stubs are still referenced by their unresolved edges, so they are not orphans; the
  `NULL-uri ≈ 0` must-have specifically obtains after the full-mode cleanup runs.
- The handful of unresolved relative specifiers in scan mode are non-source targets
  (`.css` imports, `.http.samples.js`, files lacking a tracked file node) — not regressions.

The live db was left at the canonical clean **full** state (822/822/0).

## Verification

- `uv run --package graph-io pytest tests/ -v` → 508 passed, 3 skipped, 1 xfailed.
- `python -c "from graph_io import schema; print(schema.DERIVER_VERSION)"` → 4.
- Idempotency confirmed: repeat full + incremental hold at 822 exact / 0 unresolved / 0 NULL-uri.

## STATE.md Correction

Line-39 "Last activity" note corrected surgically: the prior "NULL-uri files 3170→0"
claim was a misread (full-rebuild deletion of stubs cascade-deleted ALL import edges,
zeroing the import graph — not a health win). The clause now records the corrected
finding, references quick-260530-nsr, and captures the post-fix audit numbers. Both prior
open questions (scan-vs-full reconciliation; cross-kind safety) marked resolved.

## Self-Check: PASSED

- SUMMARY.md present
- All 4 task commits present (43173e1, 7db81a0, 7a2b213, b15d433)
- `resolve_file_imports` present in resolve.py
- `DERIVER_VERSION = 4` present in schema.py
