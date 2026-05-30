---
phase: quick-260530-jap
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/graph-io/src/graph_io/resolve.py
  - packages/graph-io/src/graph_io/update.py
  - packages/graph-io/src/graph_io/schema.py
  - packages/graph-io/tests/test_resolve.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "After enrichment, file nodes whose path has a skip-dir component AND uri IS NULL are deleted from the graph"
    - "Edges orphaned by those deletions (src or dst no longer exists) are removed"
    - "Real scanned src/ file nodes (uri IS NOT NULL) survive the new sweep"
    - "Non-file external/placeholder nodes (kind != 'file') survive the new sweep, even when uri IS NULL"
    - "A fresh re-scan of a repo with dist/build/.vite import targets no longer materializes those file nodes"
  artifacts:
    - path: "packages/graph-io/src/graph_io/resolve.py"
      provides: "sweep_skip_dir_files(conn, skip_dirs) — post-pass cleanup of skip-dir NULL-uri file nodes + orphaned edges"
      contains: "def sweep_skip_dir_files"
    - path: "packages/graph-io/tests/test_resolve.py"
      provides: "Unit coverage for sweep_skip_dir_files (deletes targets + orphaned edges; spares src nodes + non-file nodes)"
      contains: "sweep_skip_dir_files"
  key_links:
    - from: "packages/graph-io/src/graph_io/update.py"
      to: "resolve.sweep_skip_dir_files"
      via: "call inside transaction after resolve.sweep(conn)"
      pattern: "resolve\\.sweep_skip_dir_files"
    - from: "packages/graph-io/src/graph_io/resolve.py"
      to: "graph_io._ignore.should_skip"
      via: "path-component skip-dir match (reuse existing semantics)"
      pattern: "should_skip"
---

<objective>
Stop the graph from retaining `file` nodes for compiled build artifacts (`dist/**`, `build/**`, `*.d.ts`, `apps/*/.vite/build/main.js`) that enter the graph as **import-edge targets**, bypassing the walk's skip-dir respect.

Root cause is ALREADY VERIFIED (do not re-investigate): `_upsert_edge` → `_ensure_node` (`upsert.py:62-66`) materializes edge endpoints via `_insert_node` with `uri=NULL`, and `_ensure_node` never consults `skip_dirs`. So `dist`/`build` (already in `DEFAULT_SKIP_DIRS`) are honored by the walk but bypassed for edge endpoints. ~166 such nodes were observed in the `mono-repo` scan.

Implement the **post-pass cleanup sweep** (lowest-risk option): after enrichment, delete `file` nodes whose path has a `skip_dirs` component AND that have `uri IS NULL`, then drop edges orphaned by those deletions. This is the intended backstop; the deeper JS-dependency-resolution fix is a SEPARATE session — do NOT attempt it here.

Purpose: shrink the graph to genuinely-scanned source, eliminating duplicate/inflated `function`/`class`/`method` counts that hang off built-artifact file nodes.
Output: a new `resolve.sweep_skip_dir_files` function, wired into `update.run`, with a `DERIVER_VERSION` bump so existing graphs auto-rebuild, plus unit coverage.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@packages/graph-io/CLAUDE.md

<interfaces>
<!-- Existing contracts the executor builds against. No codebase exploration needed. -->

From packages/graph-io/src/graph_io/resolve.py (existing placeholder-prune sweep — mirror its style/placement):
```python
def sweep(conn: sqlite3.Connection) -> None:
    """Resolve every edge whose dst points at a placeholder node (path IS NULL)."""
    # ... reroutes placeholder-dst edges to real (kind, name) matches, then:
    # DELETE FROM nodes WHERE path IS NULL AND uri IS NULL AND kind != 'package'
    #   AND id NOT IN (SELECT dst FROM edges)
```

From packages/graph-io/src/graph_io/_ignore.py (REUSE — do not reinvent path matching):
```python
DEFAULT_SKIP_DIRS: frozenset[str]  # incl. "dist", "build", "node_modules", ...
def should_skip(rel_path: str, skip_dirs: frozenset[str]) -> bool:
    return any(part in skip_dirs for part in Path(rel_path).parts)
```

From packages/graph-io/src/graph_io/update.py run() — the enrichment pipeline tail (inside `with store.transaction(conn):`):
```python
    domains.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
    resolve.sweep(conn)                       # <-- NEW sweep goes right AFTER this
    _enforce_strict_tree_invariant(conn)
    derived_edges.compute(conn, repo_root=repo_root, ctx=ctx)
    _set_metadata(conn, "last_indexed_commit", head)
    ...
    _set_metadata(conn, "deriver_version", str(schema.DERIVER_VERSION))
```
`skip_dirs` is already in scope in run() (computed at line ~247 via `_ignore.load_skip_dirs`).

From packages/graph-io/src/graph_io/schema.py:
```python
DERIVER_VERSION = 1   # bump → update.run() forces full rebuild on existing graphs (iqo mechanism)
```

From packages/graph-io/tests/test_resolve.py (fixture + seed helper to reuse):
```python
@pytest.fixture()
def conn(tmp_path): ...   # store.connect(db, create=True)
def _seed(conn, nodes=(), edges=()):
    upsert.upsert_records(conn, GraphRecords(nodes=list(nodes), edges=list(edges)))
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add resolve.sweep_skip_dir_files + unit tests</name>
  <files>packages/graph-io/src/graph_io/resolve.py, packages/graph-io/tests/test_resolve.py</files>
  <behavior>
    New function `sweep_skip_dir_files(conn: sqlite3.Connection, skip_dirs: frozenset[str]) -> None`.
    - Selects every node where `kind = 'file' AND uri IS NULL AND path IS NOT NULL`, then keeps only those whose `path` matches `_ignore.should_skip(path, skip_dirs)` (path-component match — REUSE should_skip, do not write new glob logic).
    - DELETEs those file nodes.
    - DELETEs any edge whose `src` or `dst` references a now-deleted node id (i.e. `src NOT IN (SELECT id FROM nodes) OR dst NOT IN (SELECT id FROM nodes)`), so no orphaned edges remain.
    Tests to write FIRST (RED), seeding via `_seed` / direct INSERT then asserting:
    - Test A (deletes target + orphaned edge): seed a `file` node at `pkg/dist/index.js` with uri=NULL and an inbound `imports` edge from a real src file node; after sweep the dist file node AND the import edge are gone.
    - Test B (spares real src file): seed a `file` node at `pkg/src/index.ts` WITH a non-null uri; after sweep it survives.
    - Test C (spares non-file external/placeholder): seed a `package` node (kind='package', uri=NULL) and a `function` placeholder (kind='function', path=NULL, uri=NULL) whose path is under a skip dir is N/A (path NULL) — assert both survive untouched (sweep only touches kind='file').
    - Test D (idempotent): run sweep twice; counts stable.
    - Test E (non-skip-dir NULL-uri file untouched): seed a `file` node at `pkg/src/generated.ts` with uri=NULL but NO skip-dir component; assert it survives (sweep keys on skip-dir path component, not merely uri=NULL).
  </behavior>
  <action>In `resolve.py`, add `from graph_io import _ignore` (or `from graph_io._ignore import should_skip`) and implement `sweep_skip_dir_files(conn, skip_dirs)` per the behavior block, mirroring the existing `sweep` function's plain-sqlite style (no ORM). Query candidate file nodes (`SELECT id, path FROM nodes WHERE kind='file' AND uri IS NULL AND path IS NOT NULL`), filter in Python with `should_skip`, delete the matching ids, then delete orphaned edges in a single follow-up statement. Scope the node DELETE EXACTLY to kind='file' AND uri IS NULL AND a skip-dir path component — never broaden to other kinds or to uri-bearing nodes (constraint: do not delete legitimate non-file external/placeholder nodes). Add the five tests to `test_resolve.py` reusing the existing `conn` fixture and `_seed` helper (use direct `conn.execute` INSERTs where a uri value or specific kind must be set, since `_seed` routes through upsert).</action>
  <verify>
    <automated>cd packages/graph-io && uv run --package graph-io pytest tests/test_resolve.py -v</automated>
  </verify>
  <done>`sweep_skip_dir_files` exists in resolve.py; all new tests (A–E) pass alongside the pre-existing resolve tests; no broadening of the DELETE scope beyond kind='file' AND uri IS NULL AND skip-dir component.</done>
</task>

<task type="auto">
  <name>Task 2: Wire sweep into update.run + bump DERIVER_VERSION</name>
  <files>packages/graph-io/src/graph_io/update.py, packages/graph-io/src/graph_io/schema.py</files>
  <action>In `update.py` `run()`, inside the `with store.transaction(conn):` block, add `resolve.sweep_skip_dir_files(conn, skip_dirs)` on the line immediately AFTER `resolve.sweep(conn)` and BEFORE `_enforce_strict_tree_invariant(conn)`. `skip_dirs` is already in scope (computed near line 247). Ordering matters: it must run after `resolve.sweep` so any import edges already rerouted to real nodes are settled, leaving only genuine built-artifact file nodes for this pass. In `schema.py`, bump `DERIVER_VERSION` from 1 to 2 — this is derivation-logic that changes graph output, so existing graphs must auto-rebuild via the iqo deriver-version mechanism in `run()` (the stored `deriver_version` mismatch forces `full=True`).</action>
  <verify>
    <automated>cd packages/graph-io && uv run --package graph-io pytest tests/test_update_full.py tests/test_update_incremental.py tests/test_resolve.py tests/test_schema.py -v</automated>
  </verify>
  <done>`resolve.sweep_skip_dir_files(conn, skip_dirs)` is called once in run() directly after `resolve.sweep(conn)`; `DERIVER_VERSION == 2`; update/full/incremental + schema tests pass. If any test pins the literal DERIVER_VERSION value, update that assertion to 2 (surgical, only the version literal).</done>
</task>

<task type="auto">
  <name>Task 3: Full graph-io suite regression check</name>
  <files>packages/graph-io/tests/</files>
  <action>Run the full graph-io test suite to confirm no regressions from the new sweep or the DERIVER_VERSION bump (the bump forces full rebuilds, which can surface latent ordering assumptions in update/e2e tests). Do NOT modify production code in this task except to fix a regression that the new sweep/bump directly caused; if a failure is unrelated/pre-existing, note it in the SUMMARY rather than chasing it.</action>
  <verify>
    <automated>cd packages/graph-io && uv run --package graph-io pytest tests/ -q</automated>
  </verify>
  <done>Full graph-io suite green (or only pre-existing/unrelated failures remain, documented in SUMMARY). No new failures attributable to this change.</done>
</task>

</tasks>

<verification>
- New unit tests in test_resolve.py prove the sweep deletes skip-dir NULL-uri file nodes + their orphaned edges while sparing src nodes, non-file nodes, and non-skip-dir NULL-uri files.
- update.run() calls the sweep exactly once, after resolve.sweep.
- DERIVER_VERSION bumped → next scan of an existing graph auto-rebuilds.
- Live confirmation (manual, optional — for the operator, NOT a gate): after re-scanning `mono-repo`, `SELECT count(*) FROM nodes WHERE kind='file' AND uri IS NULL AND path LIKE '%dist%';` → ~0, and `file` with_uri ≈ total.
</verification>

<success_criteria>
- `resolve.sweep_skip_dir_files` implemented and wired into the enrichment pipeline after `resolve.sweep`.
- Sweep scoped EXACTLY to `kind='file' AND uri IS NULL AND skip-dir path component`; no other node kinds touched.
- Orphaned edges (src/dst pointing at deleted nodes) removed.
- `DERIVER_VERSION` bumped so existing graphs auto-rebuild.
- Unit test coverage as specified; full graph-io suite green (modulo documented pre-existing fails).
</success_criteria>

<output>
Create `.planning/quick/260530-jap-stop-materializing-dist-build-import-tar/260530-jap-SUMMARY.md` when done.
</output>
