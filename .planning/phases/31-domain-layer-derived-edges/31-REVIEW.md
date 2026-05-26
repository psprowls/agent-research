---
status: clean
phase: 31-domain-layer-derived-edges
depth: standard
reviewed: 2026-05-26
files_reviewed: 7
critical: 0
warning: 0
info: 3
---

# Phase 31 Code Review

## Scope

7 source files reviewed at `standard` depth:

- `packages/graph-io/pyproject.toml`
- `packages/graph-io/src/graph_io/uri.py`
- `packages/graph-io/src/graph_io/import_scan.py`
- `packages/graph-io/src/graph_io/test_suites.py`
- `packages/graph-io/src/graph_io/domains.py`
- `packages/graph-io/src/graph_io/derived_edges.py`
- `packages/graph-io/src/graph_io/update.py`

Test files in scope are intentionally excluded from per-file analysis — their correctness is verified by the test suite passing.

## Findings

### Critical

None.

### Warning

None.

### Info

#### I-01: Unused intermediate `all_pkg_keys` variable in `derived_edges._compute_references_and_depends_on`

**File:** `packages/graph-io/src/graph_io/derived_edges.py`
**Lines:** 80-85

```python
pkg_rows = conn.execute(
    "SELECT name, path FROM nodes WHERE kind=?", (_PACKAGE_KIND,),
).fetchall()
all_pkg_keys: list[tuple[str, str | None]] = [
    (name, path) for name, path in pkg_rows
]
```

`all_pkg_keys` is built but the subsequent loop on line 108 destructures `pkg_rows` directly (`for pkg_name, pkg_path in all_pkg_keys`). The intermediate variable can be elided — iterate `pkg_rows` directly. Minor; not bug-worthy.

#### I-02: Unused `ctx` parameter in private helpers

**File:** `packages/graph-io/src/graph_io/derived_edges.py`
**Lines:** 66-70 (`_compute_references_and_depends_on`), 159-162 (`_compute_testsuite_domain`)

Both helpers accept `ctx: RepoContext` but don't use it. The symmetry with other emitter signatures (`structural_nodes.emit`, `domains.emit`, etc. all take `ctx`) makes this defensible — future fields on Domain/TestSuite/edge nodes may need URI composition. Leave as-is.

#### I-03: Repeated `pkg_domains` build in two functions

**File:** `packages/graph-io/src/graph_io/derived_edges.py`
**Lines:** 92-102 (in `_compute_references_and_depends_on`), 180-188 (in `_compute_testsuite_domain`)

Both helpers execute the same `belongs_to_domain` JOIN query and build the same `pkg_domains` map. They could share a single pre-computed map passed from `compute()`. The cost is one extra SQL query per `compute()` call — acceptable for the current scale (single-digit Domain count expected). Not worth refactoring now; revisit if the membership_rows query becomes a bottleneck.

## Security

- **SQL injection:** All queries use parameterized SQL via `conn.execute(sql, params)`. No string concatenation of user input into query bodies. Pass.
- **YAML parsing:** `domains._load_domains_yaml` uses `yaml.safe_load`, never `yaml.load`. Pass.
- **Path traversal:** `import_scan.scan_files_imports` builds `repo_root / rel` from DB-stored paths; the DB paths come from `packages.refresh` and `structural_nodes.emit` which scope to the workspace. `_match_js_import` calls `resolve()` then checks `.relative_to(repo_root)` — escapes return None instead of leaking. Pass.
- **File reads:** `Path.read_text(errors='ignore')` handles malformed bytes safely. `OSError` is caught and swallowed in the scanner loop. Pass.

## Correctness Highlights

- **D-09 self-loops:** `if b_name != d_name` (derived_edges.py:132) prevents Domain → Domain self-edges. Test `test_no_self_loops_in_depends_on` covers.
- **D-08 cross-domain only:** `if d_name not in tgt_domains` (line 128) prevents Domain → intra-Pkg references. Same test covers.
- **D-12 single-pkg suites:** `if len(pkg_keys) < 2` (line 192) skips unit suites correctly.
- **D-13 multi-domain spans:** `if len(intersection) != 1` (line 200) plus `if any(ds != intersection ...)` (line 203) implement the "all-packages-share-exactly-one-Domain" gate.
- **D-15 surgical cycle recovery:** `domains._emit_containment_edges` checks `scc_of[child] == scc_of[parent]` (line 130 in domains.py) — only intra-SCC edges are skipped; out-of-SCC edges (including legitimate transitive descendants) are preserved.
- **D-17 idempotency:** `compute()` opens with three DELETE statements in the same transaction; re-running produces identical edge set. Test `test_idempotency` + `test_update_run_end_to_end`'s second-run check both pass.

## Quality Highlights

- Module docstrings clearly state purpose and call-order requirements.
- Kind constants (e.g. `_REFERENCES_KIND = "references"`) prevent stringly-typed bugs.
- Type hints comprehensive throughout.
- No raw INSERTs into nodes/edges tables — all writes go through `upsert.upsert_records`, preserving the dedupe semantics.
- The `import_scan` extraction (Plan 31-02) removed ~76 lines of duplicated regex/scan logic from `test_suites.py` — single source of truth for import-graph traversal now lives in one module.

## Verdict

**status: clean** — no Critical or Warning findings. Three Info items are minor and don't block phase completion. No fix recommended.
