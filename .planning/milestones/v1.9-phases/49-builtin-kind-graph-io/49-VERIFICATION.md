---
phase: 49-builtin-kind-graph-io
verified: 2026-05-27T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
gaps: []
deferred: []
human_verification: []
---

# Phase 49: Builtin Kind (graph-io) Verification Report

**Phase Goal:** The graph cleanly represents Python and Node.js stdlib imports as `Builtin` nodes, keeping them out of the dependency/symbol pool and making them inspectable via CLI.
**Verified:** 2026-05-27
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | `cg update` on a Python project that imports `pathlib` and `os` produces `builtin:python/pathlib` and `builtin:python/os` nodes instead of unresolved Symbol nodes | VERIFIED | `test_python_stdlib_emits_builtin_nodes` (test_builtins.py:116) runs `update.run(repo, full=True)` and asserts both nodes present; `test_e2e_python_and_node_builtins_emitted` (test_e2e_builtins.py:64) passes |
| SC-2 | `cg update` on a Node.js project that imports `fs` and `path` produces `builtin:javascript/fs` and `builtin:javascript/path` nodes; an npm package like `express` remains classified as `dependency` | VERIFIED | `test_node_dependency_vs_builtin_classification` (test_builtins.py:294) asserts `express` has zero builtin nodes; `test_e2e_express_remains_dependency_not_builtin` (test_e2e_builtins.py:94) returns GENERIC for `builtin:javascript/express`; Node tests gated with `pytest.skip` when Node not on PATH |
| SC-3 | `cg list-builtins` lists all builtin nodes in the current workspace; `cg describe-builtin builtin:python/pathlib` shows which packages use it via `used_by` edge count | VERIFIED | `q_list_builtins.run()` calls `queries.list_builtins(conn)` (q_list_builtins.py:30); `q_describe_builtin.run()` calls `queries.describe_builtin(conn, ...)` with `used_by` field (q_describe_builtin.py:40); both registered in `main._SUBCOMMANDS` (main.py:57,63); `cg --help` output contains both subcommands |
| SC-4 | Each builtin node carries `language` and `module_name` attributes inspectable via `cg describe-builtin` | VERIFIED | `BuiltinDescription` dataclass (queries.py:138-144) has `language`, `module_name`, `uri`, `used_by`; `builtins.py` emits `attrs={"uri": ..., "language": lang, "module_name": module_name}` (builtins.py:407-409); `test_builtin_node_attrs_and_uri` (test_builtins.py) covers BUILTIN-04/D-15 |
| SC-5 | `Builtin` is listed in `_VALID_KINDS` and in `ADMITTED_KINDS` with an exclusion annotation confirming it is not rendered to the wiki | VERIFIED | `"builtin"` present in `_VALID_KINDS` at queries.py:25 with D-14 reference; `ADMITTED_KINDS` in entity_writer.py:61 is a 7-element frozenset that does NOT contain `"builtin"` (runtime confirmed: `builtin in ADMITTED_KINDS == False`); Phase 49 D-16 exclusion documented in comment block at entity_writer.py:57-60 |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/graph-io/src/graph_io/builtins.py` | Core stdlib classification + emission module | VERIFIED | 426 lines; exports `refresh(conn, *, repo_root, workspace, ctx)`; implements D-01..D-09 |
| `packages/graph-io/src/graph_io/queries.py` | `_VALID_KINDS` contains `"builtin"`, `BuiltinDescription`, `describe_builtin()`, `list_builtins()` | VERIFIED | Line 25: `"builtin"` in frozenset; lines 138-144: `BuiltinDescription`; lines 609-643: `describe_builtin`; lines 708-710: `list_builtins` |
| `packages/graph-io/src/graph_io/uri.py` | `builtin_uri(language, module_name)` | VERIFIED | Line 56-57: `def builtin_uri(language: str, module_name: str) -> str: return f"builtin:{language}/{module_name}"` |
| `packages/graph-io/src/graph_io/update.py` | `builtins.refresh()` called inside transaction; `kind NOT IN ('package', 'builtin')` in DELETE | VERIFIED | Line 276: `builtins.refresh(conn, ...)` inside `store.transaction(conn)` block; lines 285,290: DELETE excludes both `package` and `builtin` |
| `packages/graph-io/src/graph_io/cli/q_list_builtins.py` | `cg list-builtins` CLI handler | VERIFIED | Mirrors `q_list_packages.py`; calls `queries.list_builtins(conn)` |
| `packages/graph-io/src/graph_io/cli/q_describe_builtin.py` | `cg describe-builtin <uri>` CLI handler | VERIFIED | Parses `builtin:<lang>/<mod>` URI; delegates to `queries.describe_builtin()` |
| `packages/graph-io/src/graph_io/cli/main.py` | Both subcommands registered | VERIFIED | `"describe-builtin"` at line 57; `"list-builtins"` at line 63 |
| `packages/wiki-io/src/wiki_io/entity_writer.py` | D-16 exclusion annotation | VERIFIED | Comment at lines 57-60 documents D-16; `"builtin"` absent from `ADMITTED_KINDS` frozenset |
| `packages/graph-io/tests/test_builtins.py` | 11 unit tests covering D-01..D-09 + cache + idempotency + wiring | VERIFIED | All 11 tests pass |
| `packages/graph-io/tests/integration/test_e2e_builtins.py` | 5 e2e integration tests | VERIFIED | All 5 tests pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `update.run()` | `builtins.refresh()` | import + function call at line 276 | WIRED | Inside `store.transaction(conn)` block; after `packages.refresh()` |
| `builtins.refresh()` | `upsert.upsert_records()` | call at builtins.py:425 | WIRED | Emits `GraphRecords(nodes=builtin_nodes, edges=builtin_edges)` |
| `q_list_builtins.run()` | `queries.list_builtins(conn)` | call at q_list_builtins.py:30 | WIRED | Returns `list[NodeRecord]`; iterates to print names |
| `q_describe_builtin.run()` | `queries.describe_builtin(conn, ...)` | call at q_describe_builtin.py:40 | WIRED | Parses URI → `(language, module_name)` → SQL query |
| `main._SUBCOMMANDS` | `q_list_builtins`, `q_describe_builtin` | dict at main.py:57,63 | WIRED | Imported and registered; `cg --help` confirms both visible |
| `builtins.py node emission` | `path=lang` discriminator | builtins.py:403 | WIRED | Prevents `(kind='builtin', name='os', path=None)` collision between Python and JS |
| `describe_builtin SQL` | `WHERE name=? AND path=?` | queries.py:622-624 | WIRED | `path=language` used as discriminator; validated by `test_describe_builtin_filters_by_language` |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `q_list_builtins.py` | `records` from `queries.list_builtins(conn)` | `SELECT kind, name, ... WHERE kind='builtin'` via `_list_by_kind` (queries.py:670-675) | Yes — DB query | FLOWING |
| `q_describe_builtin.py` | `desc` from `queries.describe_builtin(conn, ...)` | `SELECT id, name, attrs_json, uri FROM nodes WHERE kind='builtin' AND name=? AND path=?` (queries.py:621-625) + used_by JOIN (lines 626-632) | Yes — DB query + JOIN | FLOWING |
| `builtins.refresh()` | `builtin_nodes` / `builtin_edges` | scans `nodes WHERE kind='file'` per package; reads actual source files via `fpath.read_text()`; extracts stdlib imports via regex | Yes — file system scan | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `cg list-builtins` subcommand exists | `uv run cg --help 2>&1 \| grep list-builtins` | "list-builtins" present in help output | PASS |
| `cg describe-builtin` subcommand exists | `uv run cg --help 2>&1 \| grep describe-builtin` | "describe-builtin" present in help output | PASS |
| `SCHEMA_VERSION` unchanged at 2 | `grep SCHEMA_VERSION packages/graph-io/src/graph_io/schema.py` | `SCHEMA_VERSION = 2` | PASS |
| `builtin` absent from ADMITTED_KINDS | `uv run python3 -c "from wiki_io.entity_writer import ADMITTED_KINDS; print('builtin' in ADMITTED_KINDS)"` | `False` | PASS |
| Full test suite | `uv run --package graph-io pytest packages/graph-io/tests/ -q` | 409 passed, 1 skipped, 1 xfailed | PASS |

---

## Probe Execution

Step 7c: No `probe-*.sh` files declared in any PLAN or SUMMARY for Phase 49. Conventional probe path `scripts/*/tests/` does not exist in this repo. SKIPPED — no probes to run.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| BUILTIN-01 | 49-02 | Python stdlib imports → `Builtin` nodes | SATISFIED | `_PYTHON_STDLIB = sys.stdlib_module_names`; `_is_python_stdlib()` checks top-level segment; `test_python_stdlib_emits_builtin_nodes` passes |
| BUILTIN-02 | 49-02 | Node.js stdlib imports → `Builtin` nodes | SATISFIED | `_load_node_builtins()` with per-major cache; `test_node_stdlib_emits_builtin_nodes` passes (skipped when node not on PATH per D-03); `test_node_dependency_vs_builtin_classification` passes |
| BUILTIN-03 | 49-02 | npm packages remain `dependency` (no false-positive) | SATISFIED | Classification requires membership in Node builtin list; `test_node_dependency_vs_builtin_classification` asserts express has zero builtin nodes; e2e test `test_e2e_express_remains_dependency_not_builtin` confirms |
| BUILTIN-04 | 49-01/49-03 | Builtin nodes carry `language` and `module_name` attrs; URI scheme `builtin:<language>/<module_name>` | SATISFIED | `BuiltinDescription` fields at queries.py:141-143; `builtin_uri(language, module_name)` at uri.py:56; `test_builtin_node_attrs_and_uri` covers all URI examples |
| BUILTIN-05 | 49-02 | `used_by` edges from packages to Builtins; no `requires`/`imports` edges | SATISFIED | Edge emitted with `kind="used_by"` at builtins.py:419; `imported_symbols` attr in `attrs_json`; one edge per (package, builtin) per D-09; `test_used_by_edge_dedup_and_symbol_union` passes |
| BUILTIN-06 | 49-01/49-03 | `cg list-builtins` and `cg describe-builtin <uri>` CLI surfaces | SATISFIED | Both handlers implemented and registered; `test_cg_list_builtins_smoke`, `test_cg_describe_builtin_smoke` pass; `cg --help` shows both subcommands |

All 6 BUILTIN-XX requirements satisfied. No orphaned requirements (APP-01..PKGFAM requirements belong to Phases 50-51).

---

## Decision Coverage Check

| Decision | Description | Implementation Status |
|----------|-------------|----------------------|
| D-01/D-04 | Python stdlib from `sys.stdlib_module_names`; drift across versions accepted | `_PYTHON_STDLIB: frozenset[str] = sys.stdlib_module_names` (builtins.py:48) |
| D-02 | Node builtins cached per workspace at `<workspace>/.graph/cache/node-builtins-<major>.json` | `_load_node_builtins(cache_dir)` (builtins.py:170-199); cache key `node-builtins-{major}.json`; `test_node_builtins_cache_lifecycle` passes |
| D-03 | Silent skip when `node` not on PATH | `except (FileNotFoundError, subprocess.TimeoutExpired): return None` pattern at builtins.py:123,155; `test_silent_skip_when_node_missing` asserts zero stderr |
| D-05 | Top-level module only (`os.path` → `os`) | `top = module_str.split(".", 1)[0]` (builtins.py:83); `test_python_stdlib_top_level_only` asserts `os.path` not in DB |
| D-06 | Collapse `node:fs`, `import 'node:fs'`, `node:fs/promises` all to `builtin:javascript/fs` | `_normalize_node_spec()` (builtins.py:92-102); `test_node_spec_normalization` covers three cases |
| D-07 | Module-level edges only — no Function/Symbol nodes for stdlib calls | No Function/Symbol emission in `builtins.py`; docstring explicitly documents the constraint |
| D-08 | `imported_symbols` attr = sorted union of named imports across the package | `edge_acc[(pkg_name, lang, module_name)].update(symbols)` + `sorted(symbols)` at builtins.py:388-389,422 |
| D-09 | One `used_by` edge per (package, builtin) | Accumulator key `(pkg_name, lang, module_name)`; collapses all files in same package |
| **D-10** | **`SCHEMA_VERSION` stays at 2** | **`SCHEMA_VERSION = 2`** (schema.py:12) — **CONFIRMED, not bumped** |
| D-11 | Pre-v1.9 unresolved Symbol nodes not cleaned up; user runs `cg update --full` | Documented in CONTEXT.md deferred; no cleanup code in Phase 49 |
| D-12/D-13 | `cg list-builtins` / `cg describe-builtin` mirror dependency CLI shape | `q_list_builtins.py` mirrors `q_list_packages.py`; `q_describe_builtin.py` mirrors `q_describe_dependency.py` |
| D-14 | `"builtin"` added to `_VALID_KINDS` | queries.py:25; inline comment references D-14 |
| D-15 | Builtin nodes carry `language` and `module_name` attributes | `BuiltinDescription` at queries.py:138-144; `attrs={"uri": ..., "language": lang, "module_name": module_name}` at builtins.py:406-409 |
| **D-16** | **`builtin` excluded from `wiki_io.entity_writer.ADMITTED_KINDS`** | **`ADMITTED_KINDS` (entity_writer.py:61) is a 7-element frozenset without `"builtin"`; comment at lines 57-60 references Phase 49 D-16 — CONFIRMED** |

All locked decisions confirmed in implementation. No violations.

---

## Deviation Review

### Deviation 1: Path=Language Discriminator (49-03 bug fix)

**What happened:** Plan 02 used `path=None` for all Builtin nodes. This created a `(kind, name, path)` upsert key collision when two languages share the same module name (e.g., Python's `os` and Node.js's `os`).

**Fix applied in 49-03:** Changed `builtins.py` to use `path=lang` as the upsert key discriminator. Updated `queries.describe_builtin()` to use `WHERE kind='builtin' AND name=? AND path=?` (path=language). Updated `update.py` DELETE to exclude `kind='builtin'` from full-rebuild cleanup (since `path=language` is not a file path).

**Assessment:** CORRECT fix. The path column is repurposed as a language discriminator — an intentional, documented design choice. The fix prevents silent data corruption (second-language upsert overwriting first-language node). Test `test_describe_builtin_filters_by_language` validates coexistence of same-named Python and JS builtins.

**Regression risk:** None. The discriminator is used consistently in emission (builtins.py:403), querying (queries.py:622-624), and DELETE exclusion (update.py:285,290). All 409 tests pass.

### Deviation 2: `_SCAN_EXTENSIONS_JS` defined inline in builtins.py (circular import fix)

**What happened:** Plan 02 intended to import `_SCAN_EXTENSIONS_JS` from `import_scan`. This caused a circular import: `update → builtins → import_scan → structural_nodes → update`.

**Fix applied in 49-02:** `_SCAN_EXTENSIONS_JS` defined inline in `builtins.py` with the same frozenset value: `frozenset((".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs"))`.

**Assessment:** CORRECT fix per Karpathy guidelines (surgical change; minimum change needed). The value is a stable constant. No test coverage gap — the constant's correctness is validated implicitly by all Node JS scan tests.

### Deviation 3: `update.py` DELETE excludes `kind='builtin'`

**What happened:** Before the path=language fix, only `kind='package'` was excluded from the full-rebuild DELETE. After the fix, `kind NOT IN ('package', 'builtin')` is used.

**Assessment:** CORRECT. Without this exclusion, a full rebuild `cg update --full` would DELETE all builtin nodes (whose `path=language` is not a tracked file path) before builtins.refresh re-emits them. The exclusion ensures builtin nodes are managed exclusively by `builtins.refresh()`, not the file-path-based cleanup pass.

---

## Anti-Patterns Found

Scanned all 7 files modified by Phase 49:
- `packages/graph-io/src/graph_io/builtins.py`
- `packages/graph-io/src/graph_io/queries.py`
- `packages/graph-io/src/graph_io/uri.py`
- `packages/graph-io/src/graph_io/update.py`
- `packages/graph-io/src/graph_io/cli/q_list_builtins.py`
- `packages/graph-io/src/graph_io/cli/q_describe_builtin.py`
- `packages/wiki-io/src/wiki_io/entity_writer.py`

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none found) | — | — | — | — |

No debt markers (TBD, FIXME, XXX), no placeholder returns, no stub implementations. One documented open assumption in `builtins.py` docstring (multi-line `from x import (...)` may produce incomplete `imported_symbols` list) — acknowledged, non-blocking, and the edge itself is always correct per the comment.

---

## Human Verification Required

None. All success criteria are programmatically verifiable and confirmed by the automated test suite. The phase has no UI component.

---

## Test Execution Summary

```
uv run --package graph-io pytest packages/graph-io/tests/ -q
409 passed, 1 skipped, 1 xfailed in 24.20s

  - Skipped: test_domain_depends_on_no_self_loop (pre-existing; seeded_db has no domain with depends_on edges)
  - xfailed: pre-existing known failure unrelated to Phase 49

Phase 49 specific tests:
  - test_builtins.py: 11/11 passed
  - integration/test_e2e_builtins.py: 5/5 passed
  - test_queries.py: 4 new builtin tests pass (within the 409 total)
  - test_cli_describe.py: 4 new builtin tests pass (within 409 total)
  - test_cli_smoke.py: 3 new builtin tests pass (within 409 total)
```

---

## Gaps Summary

No gaps. All 5 success criteria are VERIFIED, all 6 BUILTIN-XX requirements are SATISFIED, all 16 locked decisions are reflected in the implementation, both deviations from the original plan are correct bug fixes (not regressions), the test suite passes cleanly, and no anti-patterns were found.

---

## VERIFICATION COMPLETE

_Verified: 2026-05-27_
_Verifier: Claude (gsd-verifier)_
