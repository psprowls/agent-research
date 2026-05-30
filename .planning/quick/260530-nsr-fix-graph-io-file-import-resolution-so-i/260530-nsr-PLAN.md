---
phase: quick-260530-nsr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/graph-io/src/graph_io/resolve.py
  - packages/graph-io/src/graph_io/update.py
  - packages/graph-io/src/graph_io/schema.py
  - packages/graph-io/src/graph_io/import_scan.py
  - packages/graph-io/tests/test_resolve.py
  - packages/graph-io/tests/test_import_scan.py
  - .planning/STATE.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "After a full rebuild, `imports` edges count is > 0 and the majority resolve to real file nodes (resolution=exact/ambiguous), not 0 as before."
    - "After an incremental (full=False) build, `imports` edges no longer point at NULL-uri specifier-path stubs; in-repo specifiers resolve to real file nodes."
    - "A path-less ('function', name, None) call/export placeholder resolves to a real code node ONLY when exactly one node graph-wide has that name and a non-null path; 0 or 2+ candidates stay unresolved (no fabricated/ambiguous cross-kind edges)."
    - "Genuinely external/third-party import specifiers (no matching in-repo file) remain resolution=unresolved — nothing fabricated."
    - "Specifier-path file stubs left unreferenced after resolution are cleaned up; NULL-uri/attr-less file nodes ≈ 0 in a live re-audit."
    - "schema.DERIVER_VERSION is 4, so existing graphs auto-full-rebuild via the iqo mechanism."
    - "STATE.md line-39 'Last activity' note no longer claims a full rebuild is healthy / NULL-uri 3170→0; it records the corrected finding (full rebuild ZEROES the import graph pre-fix)."
  artifacts:
    - path: "packages/graph-io/src/graph_io/resolve.py"
      provides: "resolve_file_imports() pass (repoints imports edges to real file nodes) + cross-kind single-candidate extension to sweep()"
      contains: "def resolve_file_imports"
    - path: "packages/graph-io/src/graph_io/import_scan.py"
      provides: "Generalized JS/python specifier→repo-relative-FILE resolution reused by resolve_file_imports"
      min_lines: 200
    - path: "packages/graph-io/src/graph_io/update.py"
      provides: "Pipeline ordering where resolved imports edges survive the full-mode cleanup DELETE"
      contains: "resolve_file_imports"
    - path: "packages/graph-io/src/graph_io/schema.py"
      provides: "DERIVER_VERSION = 4"
      contains: "DERIVER_VERSION = 4"
    - path: "packages/graph-io/tests/test_resolve.py"
      provides: "RED/GREEN coverage for file-import resolution + single-candidate cross-kind resolution"
      contains: "resolve_file_imports"
  key_links:
    - from: "packages/graph-io/src/graph_io/update.py"
      to: "packages/graph-io/src/graph_io/resolve.py"
      via: "resolve.resolve_file_imports(conn, repo_root) called in run()"
      pattern: "resolve\\.resolve_file_imports"
    - from: "packages/graph-io/src/graph_io/resolve.py"
      to: "packages/graph-io/src/graph_io/import_scan.py"
      via: "reuses generalized _match_js_import / _match_python_import file-resolution"
      pattern: "import_scan\\."
    - from: "packages/graph-io/src/graph_io/resolve.py"
      to: "nodes (kind='file')"
      via: "repoints imports edge dst to the real repo-relative file node id"
      pattern: "kind\\s*=\\s*'file'"
---

<objective>
Fix graph-io file-import resolution so `imports` edges resolve to real file nodes
instead of unresolved raw-specifier stubs, and add a conservative single-candidate
cross-kind resolution for call/export placeholders.

Purpose: Today `projections/graph.py::_walk` emits each import ref as
`dst=("file", target_name, raw_specifier)`. Nothing maps the raw specifier
(e.g. "../../config/api", a bare npm/python module) to the real repo-relative
file node. `resolve.sweep` only reconciles `path IS NULL` placeholders, so these
specifier-path stubs survive on incremental builds (3003 NULL-uri file stubs +
5602 unresolved imports edges) and on `--full` builds the cleanup DELETE
(update.py:285-299) purges them as collateral, cascade-deleting ALL 5602 imports
edges → file-to-file import graph = 0. The prior STATE.md "full rebuild healthy"
note is wrong and must be corrected.

Output: a new `resolve.resolve_file_imports` pass (reusing generalized
import_scan resolution), correct pipeline ordering in update.run() so resolved
edges survive the full cleanup, a conservative single-candidate cross-kind
extension to `resolve.sweep`, DERIVER_VERSION bumped 3→4, RED/GREEN tests, a
live-repo before/after re-audit, and a surgical STATE.md correction.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@packages/graph-io/CLAUDE.md
@.planning/STATE.md

@packages/graph-io/src/graph_io/resolve.py
@packages/graph-io/src/graph_io/import_scan.py
@packages/graph-io/src/graph_io/update.py
@packages/graph-io/src/graph_io/schema.py
@packages/graph-io/src/graph_io/upsert.py
@packages/source-parser/src/source_parser/projections/graph.py
@packages/graph-io/tests/test_resolve.py
@packages/graph-io/tests/test_import_scan.py

<interfaces>
<!-- Key contracts the executor needs. Extracted from the codebase. Use directly — no exploration needed. -->

projections/graph.py::_walk emits import refs as:
  GraphEdge(src=parent_key, dst=("file", ref.target_name, ref.target_module), kind="imports", attrs=dict(ref.attrs))
  where ref.target_module is the RAW specifier (relative path, dotted python module, or bare npm/python pkg).
upsert._upsert_edge: when dst[2] is None it sets attrs.resolution="unresolved"; specifier-path dsts have a non-null path so they are NOT touched by sweep.

resolve.sweep(conn): resolves edges whose dst node has path IS NULL by matching (node_kind, node_name) → real nodes; sets resolution exact (1 match) / ambiguous (>1) / unresolved (0); then deletes orphan placeholder nodes via:
  DELETE FROM nodes WHERE path IS NULL AND uri IS NULL AND kind != 'package' AND id NOT IN (SELECT dst FROM edges)
resolve._set_resolution(attrs_json, resolution) -> json str with attrs["resolution"]=resolution (sort_keys).

import_scan helpers (reuse, generalize to return the FILE not just the package):
  _build_pkg_index(pkg_rows) -> [(pkg_prefix, pkg_name, pkg_rel)] sorted deepest-first
  _build_importable_maps(pkg_rows) -> (py_map, js_map)
  _match_js_import(spec, importing_file: Path, repo_root: Path, js_map, pkg_index) -> (pkg_name, pkg_rel) | None
     — for relative/absolute specs it ALREADY computes candidate Paths (resolved, with each _JS_EXTENSIONS suffix, and _JS_INDEX_SUFFIXES) and checks cand.exists(); it currently returns _owning_package(rel,...). The repo-relative `rel` (cand.relative_to(repo_root).as_posix()) is the FILE we need.
  _match_python_import(module_str, py_map) -> (pkg_name, pkg_rel) | None — dotted top segment → package only; does NOT locate the file.
  _JS_EXTENSIONS = (".ts",".js",".tsx",".jsx",".mjs",".cjs"); _JS_INDEX_SUFFIXES = ("index.ts","index.js","index.tsx","index.jsx")
  PkgRow = (pkg_name, pkg_rel, pkg_attrs_json). pkg_rows in graph-io come from: SELECT name, path, attrs_json FROM nodes WHERE kind IN ('package','app').

upsert._node_id(conn, key) — resolves a NodeKey to an id (path IS NULL handled).
Schema: nodes(id, kind, name, path, line, attrs_json, uri); edges(src, dst, kind, attrs_json) PK (src,dst,kind) ON DELETE CASCADE.
queries: imports/imported_by/describe_path gate imports edges on `e.kind='imports' AND n.path IS NOT NULL AND _RESOLVED_FILTER` — confirms resolved imports edges MUST point at real file nodes with non-null path and resolution != 'unresolved'.

update.run() pipeline order (lines 281-323): _process_files → packages.refresh → builtins.refresh → [if full: cleanup DELETE 285-299] → structural_nodes.emit → plugins.emit → entry_points.emit → test_suites.emit → domains.emit → resolve.sweep (317) → resolve.sweep_skip_dir_files (318) → _enforce_strict_tree_invariant → derived_edges.compute (320). NOTE: sweep at 317 runs AFTER the full cleanup at 285-299 — that ordering is part of the imports bug.

Live re-audit target: mono-repo at /Users/pat/Personal/mono-repo; workspace /Users/pat/Personal/graph-wiki/mono-repo-live; db at <workspace>/.graph/code.db. Audit script: scripts/graph_health.py <db>.

Fixture in-repo imports (tests/fixtures/sample_monorepo): packages/mypkg/src/mypkg/foo.py does `from commonlib import common` (cross-package python). jspkg/index.js has no relative import. To exercise relative JS + intra-package python resolution, the executor MAY add small fixture files OR construct an in-memory/seeded graph in test_resolve.py mirroring the existing _seed pattern (preferred — matches test_sweep_* style and avoids fixture drift).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED + GREEN — file-import resolution pass (FIX #1)</name>
  <files>packages/graph-io/src/graph_io/resolve.py, packages/graph-io/src/graph_io/import_scan.py, packages/graph-io/tests/test_resolve.py, packages/graph-io/tests/test_import_scan.py</files>
  <behavior>
    - test_import_scan: a new helper that resolves a JS relative specifier to a repo-relative FILE path (not just the owning package). Given an importing file and a sibling target file that exists on disk under repo_root, the helper returns the target's repo-relative path. Bare/third-party specifier with no matching in-repo file returns None.
    - test_import_scan: a python helper resolves a first-party dotted module to the repo-relative file node for that module when an in-repo file matches (package importable → its __init__.py / module file); third-party/stdlib returns None.
    - test_resolve (file-import, exact): seed a `file` src node, a real `file` dst node (non-null path), plus an `imports` edge pointing at a specifier-path STUB file node (path = raw specifier, uri NULL). After resolve_file_imports, the edge dst is repointed to the real file node, attrs.resolution == "exact", and the now-unreferenced specifier stub node is deleted.
    - test_resolve (file-import, external/unresolved): an `imports` edge whose specifier matches no in-repo file stays pointing at its stub OR is marked resolution="unresolved" per the existing sweep convention — and is NOT fabricated to a wrong file. (Mirror sweep's unresolved branch.)
    - test_resolve (file-import, ambiguous): if a specifier resolves to >1 candidate file, attrs.resolution == "ambiguous" (do not drop the edge).
  </behavior>
  <action>
    Write the failing tests FIRST (mirror tests/test_resolve.py `_seed` / `conn` fixture and tests/test_import_scan.py style), run them to confirm RED, then implement.

    In import_scan.py, generalize the existing relative/extension/index candidate logic in `_match_js_import` so the repo-relative FILE path is obtainable WITHOUT changing the existing `(pkg_name, pkg_rel)` return for current callers. Add a sibling function (e.g. `resolve_js_import_file(spec, importing_file, repo_root) -> str | None`) that returns the repo-relative posix path of the first existing candidate (reuse `_JS_EXTENSIONS` / `_JS_INDEX_SUFFIXES` and the existing `candidates` construction — factor the candidate-building into a small shared helper rather than duplicating). For python, add `resolve_python_import_file(module_str, repo_root, pkg_rows) -> str | None` that maps the dotted module via the py_map package, then probes `<pkg_dir>/src/<importable>/...` and flat-layout (reuse the `_resolve_import_root` pattern already imported from structural_nodes) to the module file (`.py` or package `__init__.py`); return the repo-relative path or None. Do NOT add dependencies. Keep existing public functions' signatures/behavior intact (scan_files_imports / scan_package_imports are used by Phase 30/31).

    In resolve.py, add `resolve_file_imports(conn, repo_root: Path) -> None`. It: (1) selects `imports` edges whose dst is a file node with `uri IS NULL AND path IS NOT NULL` (the specifier-path stubs) joined to the src file node (for importing_file path) — query `e.src, e.dst, e.attrs_json, src.path AS importing_path, dst.path AS specifier`; (2) loads pkg_rows once via `SELECT name, path, attrs_json FROM nodes WHERE kind IN ('package','app')`; (3) for each, picks the JS resolver when the importing file has a JS/TS extension else the python resolver, passing the raw specifier; (4) on a single resolved repo-relative file path that has a real `file` node (path not null), DELETE the stub edge and INSERT/UPSERT an edge to the real file node id with attrs.resolution="exact" (reuse `_set_resolution`); on multiple candidate file nodes, fan out with resolution="ambiguous" (mirror sweep); on no in-repo match, leave the edge but set resolution="unresolved" (mirror sweep's unresolved branch) — do NOT fabricate. After processing, delete now-orphaned specifier stub nodes using the SAME orphan-cleanup predicate sweep uses (`path IS NOT NULL? ` — note: these stubs have a non-null specifier path, so extend the cleanup to also remove `kind='file' AND uri IS NULL AND <was a specifier stub> AND id NOT IN (SELECT dst FROM edges)`; scope narrowly to the stub ids you collected, do NOT broaden to all NULL-uri files). Match existing style and the read-only/transaction conventions (this runs inside update's open transaction; do not open new connections).
  </action>
  <verify>
    <automated>cd packages/graph-io && uv run --package graph-io pytest tests/test_resolve.py tests/test_import_scan.py -v</automated>
  </verify>
  <done>New file-import resolution tests pass (GREEN); `resolve_file_imports` repoints stub-pointed imports edges to real file nodes with resolution=exact/ambiguous, leaves external specifiers unresolved without fabrication, and cleans up orphaned specifier stubs; existing test_resolve.py / test_import_scan.py tests still pass; no new dependencies.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: RED + GREEN — pipeline ordering + single-candidate cross-kind resolution + DERIVER bump (FIX #2)</name>
  <files>packages/graph-io/src/graph_io/update.py, packages/graph-io/src/graph_io/resolve.py, packages/graph-io/src/graph_io/schema.py, packages/graph-io/tests/test_resolve.py</files>
  <behavior>
    - test_resolve (cross-kind single candidate): seed a `calls` (or `exports`) edge whose dst is a path-less ("function", name, None) placeholder, and EXACTLY ONE real code node graph-wide with that name and non-null path but a DIFFERENT kind (e.g. kind='method' or 'class'). After sweep, the edge resolves to that node, resolution="exact".
    - test_resolve (cross-kind zero candidates): placeholder name matching no real code node → stays unresolved (unchanged behavior).
    - test_resolve (cross-kind collision): placeholder name matching 2+ real code nodes (any kinds) → stays unresolved, NO ambiguous cross-kind edges created.
    - test_resolve (same-kind still works): existing exact/ambiguous same-kind sweep tests remain green (no regression).
    - Pipeline: after a full=True update.run, imports edges count > 0 and not all collateral-deleted (covered by the integration assertion in Task 3); the file-import pass runs at a point where resolved edges survive the full cleanup DELETE.
  </behavior>
  <action>
    Write/extend failing tests FIRST in test_resolve.py (mirror existing `_seed`/`conn` patterns), confirm RED, then implement.

    (a) Cross-kind, conservative (D-3): extend `resolve.sweep`'s placeholder-resolution. Today sweep matches `WHERE kind=? AND name=? AND path IS NOT NULL` (same kind). Add a conservative cross-kind fallback: when the same-kind match yields ZERO results for a path-less placeholder, look up ALL code-kind nodes (function/method/class) with that name and non-null path graph-wide; resolve to it ONLY when EXACTLY ONE exists (resolution="exact"). 0 candidates → unresolved (unchanged). 2+ candidates (any kinds) → unresolved, do NOT create ambiguous edges (bare-name collisions like get/render/update must not produce false edges). Restrict the cross-kind fallback to placeholders whose own kind is a code kind (the ("function", name, None) call/export placeholders) — do NOT apply it to the file-import stubs (those are handled by Task 1's pass). Keep the same-kind exact/ambiguous behavior unchanged.

    (b) Pipeline ordering (D-2, critical): wire `resolve.resolve_file_imports(conn, repo_root)` into update.run() so resolved imports edges point at TRACKED real-file paths that SURVIVE the full-mode cleanup DELETE (lines 285-299). The cleanup deletes `kind NOT IN ('package','app','builtin') AND path IS NOT NULL AND path NOT IN (tracked_paths)`. Real file nodes are in tracked_paths and survive; specifier-path stubs are NOT in tracked_paths and get deleted — so resolve_file_imports MUST run BEFORE the cleanup DELETE so edges are already repointed to surviving real file nodes (the stubs being deleted is then fine — they're orphaned). Place the call after `_process_files`/`packages.refresh`/`builtins.refresh` (so package/app nodes and file nodes exist for resolution) and BEFORE the `if full:` cleanup block. Re-confirm by reading the current ordering; do not move resolve.sweep (it still runs at 317 for placeholder edges). Ensure resolve_file_imports is import-safe in update.py (resolve is already imported at module top — verify and reuse).

    (c) Bump `schema.DERIVER_VERSION` 3 → 4 so existing graphs auto-full-rebuild via the iqo mechanism (update.py:270-276).
  </action>
  <verify>
    <automated>cd packages/graph-io && uv run --package graph-io pytest tests/test_resolve.py -v && python3 -c "from graph_io import schema; assert schema.DERIVER_VERSION == 4, schema.DERIVER_VERSION; print('DERIVER_VERSION', schema.DERIVER_VERSION)"</automated>
  </verify>
  <done>Single-candidate cross-kind resolution works and refuses 0/2+ candidate cases; same-kind sweep behavior unchanged; resolve_file_imports is wired into update.run() before the full-mode cleanup DELETE so resolved imports edges survive; DERIVER_VERSION == 4.</done>
</task>

<task type="auto">
  <name>Task 3: Full suite + live-repo before/after re-audit + STATE.md correction</name>
  <files>.planning/STATE.md</files>
  <action>
    Run the FULL graph-io suite. Then perform the live-repo re-audit and capture before/after numbers, then make the surgical STATE.md correction.

    Full suite: from packages/graph-io run `pytest tests/ -v` (or `uv run --package graph-io pytest tests/ -v`). All must pass — fix any regressions in graph-io introduced by Tasks 1-2 (do NOT refactor unrelated code).

    Live re-audit (mono-repo). Capture BEFORE numbers first if a stale db exists: `python3 scripts/graph_health.py /Users/pat/Personal/graph-wiki/mono-repo-live/.graph/code.db` (record imports-edge count + resolution split + NULL-uri/attr-less file-node counts). Then run BOTH build modes against /Users/pat/Personal/mono-repo into workspace /Users/pat/Personal/graph-wiki/mono-repo-live via the library API — `from graph_io import update; update.run(Path('/Users/pat/Personal/mono-repo'), full=True)` then a second run with `full=False` (incremental). After EACH, run `python3 scripts/graph_health.py <workspace>/.graph/code.db`. Assert and record: (1) imports edges > 0 on BOTH modes (previously 0 on full / all-unresolved on scan); (2) the majority of imports edges are resolved (resolution exact/ambiguous, not unresolved); (3) NULL-uri / attr-less `file` nodes ≈ 0. If the repo paths differ at execution time, discover the correct workspace via the same mechanism the conftest uses (workspace_io resolve + graph_dir) and note the actual paths in the SUMMARY. Capture the concrete before/after numbers in the SUMMARY.

    STATE.md correction (D-5, surgical): edit ONLY the line-39 "Last activity" note's specific claim. The note currently asserts the v2 full rebuild was "healthy / NULL-uri files 3170→0". Annotate/replace that specific clause with the corrected finding: a full rebuild PRE-FIX zeroed the import graph (the 3170→0 drop was stub DELETION, not resolution; ALL imports edges cascade-deleted). Reference this fix (quick-260530-nsr) and the corrected post-fix audit numbers. Do NOT rewrite the rest of STATE.md.
  </action>
  <verify>
    <automated>cd packages/graph-io && uv run --package graph-io pytest tests/ -v 2>&1 | tail -5</automated>
  </verify>
  <done>Full graph-io suite passes; live re-audit run for BOTH full and incremental modes with before/after numbers captured in SUMMARY showing imports edges > 0 and mostly resolved and NULL-uri/attr-less file nodes ≈ 0; STATE.md line-39 note corrected surgically (no broad rewrite).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| import specifier → file-node repointing | Raw, attacker-irrelevant but correctness-critical: a wrong resolution fabricates a false edge in the graph |
| filesystem probe (cand.exists()) | resolve_file_imports probes the repo working tree to resolve specifiers; must stay within repo_root |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-nsr-01 | Tampering | resolve_file_imports specifier resolution | mitigate | Only repoint to file nodes whose repo-relative path resolves via relative_to(repo_root); never fabricate an edge when 0 candidates (mark unresolved); fan out only on genuine multi-match (ambiguous) |
| T-nsr-02 | Tampering | cross-kind sweep fallback | mitigate | Resolve ONLY on exactly-one graph-wide name match; 2+ candidates stay unresolved to prevent bare-name-collision false edges (D-3) |
| T-nsr-03 | Information disclosure | orphan stub cleanup DELETE | mitigate | Scope deletion to the specifier-stub ids collected during the pass (kind='file' AND uri IS NULL AND id NOT IN (SELECT dst FROM edges)); do NOT broaden to all NULL-uri files (would delete legitimate placeholders) |
| T-nsr-SC | Tampering | npm/pip/cargo installs | accept | No new dependencies added (constraint); no install tasks |
</threat_model>

<verification>
- `uv run --package graph-io pytest tests/ -v` — full graph-io suite green.
- `python3 -c "from graph_io import schema; print(schema.DERIVER_VERSION)"` → 4.
- Live re-audit: `python3 scripts/graph_health.py <workspace>/.graph/code.db` after full=True AND full=False: imports edges > 0, mostly resolved, NULL-uri/attr-less file nodes ≈ 0.
- STATE.md line-39 note no longer claims full-rebuild-healthy / 3170→0 as success.
</verification>

<success_criteria>
- imports edges resolve to real file nodes (resolution exact/ambiguous) on both full and incremental builds; no collateral zeroing on full.
- External/third-party specifiers stay unresolved; nothing fabricated.
- Single-candidate cross-kind call/export resolution works; 0/2+ candidates stay unresolved.
- Specifier stubs cleaned up; NULL-uri/attr-less file nodes ≈ 0 in live audit.
- DERIVER_VERSION == 4.
- Code changes confined to graph-io (+ import_scan), no new deps, existing style matched.
- STATE.md correction is surgical to the line-39 note only.
</success_criteria>

<output>
Create `.planning/quick/260530-nsr-fix-graph-io-file-import-resolution-so-i/260530-nsr-SUMMARY.md` when done.
Capture the before/after live-audit numbers (imports-edge count + resolution split + NULL-uri file-node counts) for BOTH full and incremental modes in the SUMMARY.
</output>
