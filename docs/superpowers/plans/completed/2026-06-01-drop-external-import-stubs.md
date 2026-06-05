# Drop External Import Stubs (Option A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `gw scan` from polluting the code graph with bogus `kind='file'` nodes that are actually unresolved external/stdlib import targets (e.g. `os`, `contextlib`, `langchain_aws`).

**Architecture:** The graph projection emits every `import` ref as an edge whose dst is a `('file', symbol, module)` tuple (`source_parser/projections/graph.py:78`), which the upsert materializes as a NULL-uri `file` node ("specifier stub"). `resolve_file_imports` (`graph_io/resolve.py`) already repoints *first-party* imports to real file nodes, but currently **parks** unresolvable (external/third-party/stdlib) imports on the stub with `resolution="unresolved"`, and **never even looks at** plain `import X` stubs (its `dst.name != dst.path` query guard skips them). We change `resolve_file_imports` to (1) **delete** the edge for any import with no in-repo file target, and (2) broaden its scan to plain-import stubs while using `(repo_root / specifier).is_file()` — not `name != path` — to spare real files. Orphaned stubs are then removed by the existing cleanup at the end of the function. stdlib usage remains captured separately by `builtins.refresh` as `kind='builtin'` + `used_by` edges.

**Tech Stack:** Python 3.11+, SQLite (`sqlite3`), `pytest` (run via `uv`), `graph_io` workspace package.

---

## Background (read before starting)

Facts established from the live DB (`/Users/pat/Personal/graph-wiki/agent-research-live/.graph/code.db`) and the code:

- These stubs are **only** a problem in **incremental** mode. `gw scan` → `graph_wiki_core/commands/scan.py:494` → `update.run(repo, full=False)`. In `full=True` mode the blanket cleanup at `update.py:300-307` (`DELETE FROM nodes WHERE kind NOT IN ('package','app','builtin') AND path IS NOT NULL AND path NOT IN (tracked_paths)`) already deletes them; that block is gated behind `if full:` so incremental scans keep them.
- There are **two** stub classes: `name != path` from-imports (`from contextlib import contextmanager` → `('file','contextmanager','contextlib')`) which the resolver's query *does* select, and `name == path` plain imports (`import os` → `('file','os','os')`) which its `dst.name != dst.path` guard *skips* entirely.
- **Landmine:** at the point `resolve_file_imports` runs (`update.py:292`), `structural_nodes.emit` has **not yet** attached `file:` URIs — so *every real file node transiently has `uri IS NULL`*. That is why the existing code uses `name != path` rather than `uri IS NULL` to find stubs. There are also real, on-disk files that end up permanently NULL-uri (orphan parser nodes outside any package, e.g. `plugins/.../scripts/_config.py`). A correct fix must **not** delete these. The robust discriminator is `(repo_root / specifier).is_file()`: a stub's path is a bare module specifier with no corresponding file; a real file's path is an on-disk file.
- Nothing consumes the unresolved external edges productively. The three `imports`-edge query consumers (`queries.py:imports`, `queries.py:imported_by`, `describe`) all apply `_RESOLVED_FILTER`. `derived_edges.py` computes from a regex scan (`import_scan`), **not** from these graph edges, so deleting them is safe there.

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `packages/graph-io/src/graph_io/resolve.py` | `resolve_file_imports` — repoint/clean import-edge stubs | **Modify** `resolve_file_imports` (docstring, comment, query, two branch bodies, add `is_file` guard) |
| `packages/graph-io/tests/test_resolve.py` | Unit + small-repo tests for `resolve` | **Modify** one test (`test_resolve_file_imports_external_unresolved`), **add** two tests + one Python-repo helper |

No new files. No changes to the projection, the upsert, the query layer, or the CLI — the stub is killed at the one place that already owns stub lifecycle.

**Run command (from repo root), used in every "run tests" step:**

```bash
uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py -v
```

---

## Task 1: Drop external (unresolvable) import edges instead of parking them

Covers the `name != path` from-import class. Change the two branches in `resolve_file_imports` that currently `UPDATE ... resolution="unresolved"` so they `DELETE` the edge, letting the existing end-of-function cleanup remove the now-orphaned stub.

**Files:**
- Modify: `packages/graph-io/src/graph_io/resolve.py:104-121`
- Test: `packages/graph-io/tests/test_resolve.py:434-454`

- [ ] **Step 1: Rewrite the existing external-import test to expect deletion**

In `packages/graph-io/tests/test_resolve.py`, replace the whole `test_resolve_file_imports_external_unresolved` function (currently lines 434-454) with:

```python
def test_resolve_file_imports_external_dropped(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """Option A: an external (third-party) import edge and its specifier stub are
    DELETED, not parked on the stub as resolution='unresolved'."""
    repo = _make_js_repo(tmp_path)
    _seed_file_import(
        conn,
        importing_path="packages/jspkg-a/src/index.js",
        specifier="react",
        target_path=None,
    )

    resolve.resolve_file_imports(conn, repo)

    # The unresolvable edge is gone entirely.
    edge_count = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE kind='imports'"
    ).fetchone()[0]
    assert edge_count == 0

    # The orphaned specifier stub is gone too.
    stub_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE path='react'"
    ).fetchone()[0]
    assert stub_count == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py::test_resolve_file_imports_external_dropped -v`
Expected: FAIL — current code keeps the edge with `resolution="unresolved"` and keeps the stub, so `edge_count == 1` (assert fails).

- [ ] **Step 3: Change both unresolvable branches to delete the edge**

In `packages/graph-io/src/graph_io/resolve.py`, find this block (the `rel is None` branch, currently lines 104-110):

```python
        if rel is None:
            # External/third-party — do NOT fabricate; mark unresolved.
            conn.execute(
                "UPDATE edges SET attrs_json=? WHERE src=? AND dst=? AND kind='imports'",
                (_set_resolution(attrs_json, "unresolved"), src_id, stub_id),
            )
            continue
```

Replace it with:

```python
        if rel is None:
            # External / third-party / stdlib specifier with no in-repo file.
            # Option A: drop the edge entirely instead of parking it on the stub
            # as resolution="unresolved". The orphaned stub is removed by the
            # cleanup at the end of this function, so external imports never leave
            # a kind='file' node behind. (stdlib usage is still recorded by
            # builtins.refresh as kind='builtin' + used_by edges.)
            conn.execute(
                "DELETE FROM edges WHERE src=? AND dst=? AND kind='imports'",
                (src_id, stub_id),
            )
            continue
```

Then find this block (the `if not real` branch, currently lines 116-121):

```python
        if not real:
            conn.execute(
                "UPDATE edges SET attrs_json=? WHERE src=? AND dst=? AND kind='imports'",
                (_set_resolution(attrs_json, "unresolved"), src_id, stub_id),
            )
            continue
```

Replace it with:

```python
        if not real:
            # Specifier resolved to a repo-relative path but no file node exists
            # there (untracked / ignored target). Same as external — drop the
            # edge so no stub survives.
            conn.execute(
                "DELETE FROM edges WHERE src=? AND dst=? AND kind='imports'",
                (src_id, stub_id),
            )
            continue
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py::test_resolve_file_imports_external_dropped -v`
Expected: PASS

- [ ] **Step 5: Run the full resolve suite to confirm no regressions**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py -v`
Expected: PASS (the `exact` and `ambiguous` resolve tests are unaffected — they hit the repoint path, not the dropped branches).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-io/src/graph_io/resolve.py packages/graph-io/tests/test_resolve.py
git commit -m "fix(graph-io): drop unresolvable import edges instead of parking them on stubs"
```

---

## Task 2: Catch plain `import X` stubs and spare real NULL-uri files

The resolver's query still has `AND dst.name != dst.path`, so plain `import X` stubs (`name == path`, e.g. `('file','os','os')`) are never processed. Remove that guard and replace it with a working-tree probe (`is_file`) so the pass also handles plain imports while never mistaking a real (transiently NULL-uri) file for a stub.

**Files:**
- Modify: `packages/graph-io/src/graph_io/resolve.py:31-50` (docstring), `:54-67` (guard comment), `:68-78` (query), `:91-93` (loop head — add `is_file` skip)
- Test: `packages/graph-io/tests/test_resolve.py` (add `_make_py_repo` helper + `test_resolve_file_imports_drops_plain_import_stubs`)

- [ ] **Step 1: Add a Python-repo helper next to `_make_js_repo`**

In `packages/graph-io/tests/test_resolve.py`, immediately after the `_make_js_repo` function (ends at line 359), add:

```python
def _make_py_repo(tmp_path: Path) -> Path:
    """Build a tiny Python package on disk so resolve_file_imports can probe the
    working tree for first-party resolution and is_file() discrimination.

    pypkg/src/pypkg/{__init__.py, app.py, helper.py, orphan.py} all exist.
    """
    pkg = tmp_path / "pypkg" / "src" / "pypkg"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "app.py").write_text(
        "import os\nfrom pypkg.helper import helper_fn\n"
    )
    (pkg / "helper.py").write_text("def helper_fn():\n    return 1\n")
    (pkg / "orphan.py").write_text("x = 1\n")
    (tmp_path / "pypkg" / "pyproject.toml").write_text(
        '[project]\nname = "pypkg"\n'
    )
    return tmp_path
```

- [ ] **Step 2: Add the failing test for plain-import stubs + real-file sparing**

In `packages/graph-io/tests/test_resolve.py`, after the test you renamed in Task 1 (`test_resolve_file_imports_external_dropped`), add:

```python
def test_resolve_file_imports_drops_plain_import_stubs(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """Plain `import X` stubs (name == path) are processed too:
      - external plain import (os)        -> edge + stub deleted
      - first-party plain import (pypkg)  -> edge repointed to the real __init__.py
      - a real file with uri IS NULL      -> SPARED (is_file() discriminator)
    """
    repo = _make_py_repo(tmp_path)

    # Package node so resolve_python_import_file can map 'pypkg' -> its import root.
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('package', 'pypkg', 'pypkg', NULL, ?, 'repo:org/x/pkg/pypkg')",
        (json.dumps({"language": "python"}),),
    )
    # Real importer file (uri set).
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pypkg/src/pypkg/app.py', 'pypkg/src/pypkg/app.py', "
        "NULL, '{}', 'repo:org/x/app')"
    )
    # Real first-party target that `import pypkg` resolves to (uri set).
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pypkg/src/pypkg/__init__.py', "
        "'pypkg/src/pypkg/__init__.py', NULL, '{}', 'repo:org/x/init')"
    )
    # Real file that is currently a NULL-uri node (orphan parser node). It is an
    # imports-edge dst and MUST survive — is_file() is True for it.
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pypkg/src/pypkg/orphan.py', "
        "'pypkg/src/pypkg/orphan.py', NULL, '{}', NULL)"
    )
    app_id = conn.execute(
        "SELECT id FROM nodes WHERE path='pypkg/src/pypkg/app.py'"
    ).fetchone()[0]

    # Plain external stub: ('file','os','os')  (name == path)
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'os', 'os', NULL, '{}', NULL)"
    )
    os_id = conn.execute(
        "SELECT id FROM nodes WHERE kind='file' AND path='os'"
    ).fetchone()[0]
    # Plain first-party stub: ('file','pypkg','pypkg')  (name == path)
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pypkg', 'pypkg', NULL, '{}', NULL)"
    )
    fp_id = conn.execute(
        "SELECT id FROM nodes WHERE kind='file' AND path='pypkg' AND uri IS NULL"
    ).fetchone()[0]
    orphan_id = conn.execute(
        "SELECT id FROM nodes WHERE path='pypkg/src/pypkg/orphan.py'"
    ).fetchone()[0]
    for dst in (os_id, fp_id, orphan_id):
        conn.execute(
            "INSERT INTO edges(src, dst, kind, attrs_json) "
            "VALUES (?, ?, 'imports', NULL)",
            (app_id, dst),
        )

    resolve.resolve_file_imports(conn, repo)

    # External plain stub deleted.
    assert conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='file' AND path='os'"
    ).fetchone()[0] == 0
    # First-party plain stub deleted...
    assert conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='file' AND path='pypkg' AND uri IS NULL"
    ).fetchone()[0] == 0
    # ...and its edge repointed to the real __init__.py file node (exact).
    repointed = conn.execute(
        "SELECT e.attrs_json FROM edges e JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='imports' AND d.path='pypkg/src/pypkg/__init__.py'"
    ).fetchall()
    assert len(repointed) == 1
    assert json.loads(repointed[0][0])["resolution"] == "exact"
    # Real NULL-uri orphan file is SPARED, and its edge is untouched.
    assert conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE path='pypkg/src/pypkg/orphan.py'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM edges e JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='imports' AND d.path='pypkg/src/pypkg/orphan.py'"
    ).fetchone()[0] == 1
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py::test_resolve_file_imports_drops_plain_import_stubs -v`
Expected: FAIL — the current query's `AND dst.name != dst.path` guard skips the `os` and `pypkg` plain-import stubs, so they (and their edges) survive: `COUNT(... path='os') == 1` (assert fails).

- [ ] **Step 4: Replace the guard comment with the new is_file() rationale**

In `packages/graph-io/src/graph_io/resolve.py`, find this comment block (currently lines 54-67):

```python
    # Specifier-stub imports edges: dst is a file node materialised from the
    # edge dst-key ('file', symbol, raw_specifier) — so dst.name is the imported
    # symbol and dst.path is the raw specifier. Real file nodes always have
    # name == path (set by the projection / structural_nodes), so `dst.name !=
    # dst.path` cleanly distinguishes a specifier stub from a real file node.
    #
    # The name!=path guard is essential: _process_files re-upserts file nodes
    # with uri=NULL (uri is re-attached later by structural_nodes.emit), so on a
    # repeat build real file nodes transiently have uri IS NULL too — without the
    # name!=path guard this pass would mistake an already-resolved real file node
    # for a stub and flip its resolved edges back to unresolved (idempotency bug).
    #
    # dst.name (the imported symbol) is preserved in edge attrs so per-symbol
    # information is not lost once the edge points at the (multi-symbol) file.
```

Replace it with:

```python
    # Specifier-stub imports edges: dst is a file node materialised from the
    # edge dst-key ('file', symbol, raw_specifier) — dst.name is the imported
    # symbol and dst.path is the raw specifier. This includes BOTH from-imports
    # (name != path, e.g. ('file','contextmanager','contextlib')) AND plain
    # imports (name == path, e.g. ('file','os','os')).
    #
    # We cannot key on uri IS NULL alone, nor on name != path: at this point in
    # update.run, structural_nodes.emit has not yet attached file: URIs, so every
    # REAL file node also transiently has uri IS NULL, and plain-import stubs have
    # name == path just like real files. The reliable discriminator is the
    # working tree — a stub's path is a bare module specifier ("os", "contextlib")
    # with no corresponding file, whereas a real file's path is an on-disk file.
    # The loop below skips any dst whose path is a real file (see is_file() check).
    #
    # dst.name (the imported symbol) is preserved in edge attrs so per-symbol
    # information is not lost once the edge points at the (multi-symbol) file.
```

- [ ] **Step 5: Remove the `name != path` guard from the query**

In `packages/graph-io/src/graph_io/resolve.py`, find the query (currently lines 68-78):

```python
    rows = conn.execute(
        "SELECT e.src, e.dst, e.attrs_json, src.path AS importing_path, "
        "dst.path AS specifier, dst.name AS symbol "
        "FROM edges e "
        "JOIN nodes src ON e.src = src.id "
        "JOIN nodes dst ON e.dst = dst.id "
        "WHERE e.kind = 'imports' "
        "AND dst.kind = 'file' AND dst.uri IS NULL AND dst.path IS NOT NULL "
        "AND dst.name != dst.path "
        "AND src.path IS NOT NULL"
    ).fetchall()
```

Replace it with (drop only the `AND dst.name != dst.path` line):

```python
    rows = conn.execute(
        "SELECT e.src, e.dst, e.attrs_json, src.path AS importing_path, "
        "dst.path AS specifier, dst.name AS symbol "
        "FROM edges e "
        "JOIN nodes src ON e.src = src.id "
        "JOIN nodes dst ON e.dst = dst.id "
        "WHERE e.kind = 'imports' "
        "AND dst.kind = 'file' AND dst.uri IS NULL AND dst.path IS NOT NULL "
        "AND src.path IS NOT NULL"
    ).fetchall()
```

- [ ] **Step 6: Add the is_file() skip at the top of the loop**

In `packages/graph-io/src/graph_io/resolve.py`, find the loop head (currently lines 91-93):

```python
    stub_ids: set[int] = set()
    for src_id, stub_id, attrs_json, importing_path, specifier, symbol in rows:
        stub_ids.add(stub_id)
```

Replace it with:

```python
    stub_ids: set[int] = set()
    for src_id, stub_id, attrs_json, importing_path, specifier, symbol in rows:
        # Spare real files. A real source file transiently has uri IS NULL here
        # (structural_nodes.emit attaches the uri later), and plain-import stubs
        # share the name == path shape of real files — so probe the working tree.
        # If `specifier` is an actual file under repo_root it is NOT a stub: leave
        # its node and edges untouched (and out of stub_ids, so cleanup spares it).
        if (repo_root / specifier).is_file():
            continue
        stub_ids.add(stub_id)
```

- [ ] **Step 7: Update the function docstring to describe the final behavior**

In `packages/graph-io/src/graph_io/resolve.py`, replace the `resolve_file_imports` docstring (currently lines 32-50, the triple-quoted block) with:

```python
    """Resolve `imports` edges from raw-specifier stub nodes; drop unresolvable ones.

    The graph projection emits each import ref as dst=('file', target_name,
    raw_specifier), which materialises a `file` node with path=raw_specifier and
    uri IS NULL — a "specifier stub" (both `from X import y` and plain `import X`).
    `sweep` only reconciles path-IS-NULL placeholders, so these stubs (non-null
    path) survive untouched. This pass handles them:

      - exactly one real file node at the resolved path  -> repoint edge,
        resolution="exact"
      - multiple real file nodes at the resolved path     -> fan out,
        resolution="ambiguous"
      - no in-repo file (external / third-party / stdlib) -> DELETE the edge
        (Option A): the stub is then orphaned and removed by the cleanup below.
        stdlib usage is still recorded by builtins.refresh as kind='builtin'
        + used_by edges, so no information is lost.

    Real files are identified by (repo_root / specifier).is_file() and skipped —
    NOT by name != path or uri IS NULL, both of which a real file can match at
    this stage of update.run (uri is attached later by structural_nodes.emit).

    After processing, specifier stubs left unreferenced (no inbound edge) are
    deleted. Runs inside update's open transaction — does not open a new
    connection.
    """
```

- [ ] **Step 8: Run the new test to verify it passes**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py::test_resolve_file_imports_drops_plain_import_stubs -v`
Expected: PASS

- [ ] **Step 9: Run the full resolve suite (idempotency + exact/ambiguous still green)**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py -v`
Expected: PASS — `test_resolve_file_imports_exact` and `test_resolve_file_imports_ambiguous` still resolve via the working tree (their `../../jspkg-b/foo` specifier is not a file under `repo_root`, so the is_file() skip does not fire).

- [ ] **Step 10: Commit**

```bash
git add packages/graph-io/src/graph_io/resolve.py packages/graph-io/tests/test_resolve.py
git commit -m "fix(graph-io): drop plain-import stubs too, use is_file() to spare real files"
```

---

## Task 3: End-to-end regression — an incremental scan leaves no external stubs

Prove the fix end-to-end through the real `update.run(full=False)` pipeline (the `gw scan` path), where the full-mode blanket delete does NOT run, so `resolve_file_imports` is the only thing cleaning stubs.

**Files:**
- Test: `packages/graph-io/tests/test_resolve.py` (add `test_incremental_scan_leaves_no_external_import_stubs`)

- [ ] **Step 1: Add the end-to-end regression test**

In `packages/graph-io/tests/test_resolve.py`, add this test at the end of the file:

```python
def test_incremental_scan_leaves_no_external_import_stubs(tmp_path: Path) -> None:
    """End-to-end: `gw scan` == update.run(full=False). After it, no NULL-uri
    kind='file' stub may exist for a stdlib/third-party import, and a first-party
    submodule import must resolve to the real file node."""
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace
    from workspace_io.paths import graph_dir

    import _git_repo  # tests/ is on sys.path via conftest

    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo.init_repo(repo)
    _git_repo.write_and_commit(
        repo,
        {
            "mypkg/pyproject.toml": '[project]\nname = "mypkg"\n',
            "mypkg/src/mypkg/__init__.py": "",
            "mypkg/src/mypkg/app.py": (
                "import os\n"
                "import json\n"
                "from contextlib import contextmanager\n"
                "from mypkg.helper import helper_fn\n"
            ),
            "mypkg/src/mypkg/helper.py": "def helper_fn():\n    return 1\n",
        },
        "init",
    )

    update.run(repo, full=False)

    ws = resolve_workspace(repo, require_manifest=False).workspace
    db = graph_dir(ws) / "code.db"
    conn = sqlite3.connect(db)
    try:
        # No external/stdlib import stub file nodes survive.
        stubs = conn.execute(
            "SELECT name, path FROM nodes "
            "WHERE kind='file' AND uri IS NULL "
            "AND path IN ('os', 'json', 'contextlib')"
        ).fetchall()
        assert stubs == [], f"external import stubs survived: {stubs}"

        # The first-party submodule import resolved to the real helper.py node.
        resolved = conn.execute(
            "SELECT COUNT(*) FROM edges e "
            "JOIN nodes s ON e.src=s.id JOIN nodes d ON e.dst=d.id "
            "WHERE e.kind='imports' "
            "AND s.path='mypkg/src/mypkg/app.py' "
            "AND d.path='mypkg/src/mypkg/helper.py' "
            "AND d.uri IS NOT NULL"
        ).fetchone()[0]
        assert resolved == 1, "first-party import did not resolve to helper.py"
    finally:
        conn.close()
```

- [ ] **Step 2: Run the end-to-end test to verify it passes**

Run: `uv run --package graph-io pytest packages/graph-io/tests/test_resolve.py::test_incremental_scan_leaves_no_external_import_stubs -v`
Expected: PASS. (Sanity check the regression value: `git stash` the `resolve.py` changes, rerun — it FAILS with `os`/`json`/`contextlib` stubs surviving — then `git stash pop`.)

- [ ] **Step 3: Run the entire graph-io test suite**

Run: `uv run --package graph-io pytest packages/graph-io/tests -q`
Expected: PASS — full suite green, confirming no other test depended on external import stubs or unresolved import edges.

- [ ] **Step 4: Commit**

```bash
git add packages/graph-io/tests/test_resolve.py
git commit -m "test(graph-io): end-to-end regression for external import stub cleanup in scan"
```

---

## After the plan (not tasks — follow-ups to mention)

- Rebuild the live graph to confirm in the real DB: `gw scan` in `/Users/pat/Personal/graph-wiki/agent-research-live`, then
  `sqlite3 .graph/code.db "SELECT COUNT(*) FROM nodes WHERE kind='file' AND uri IS NULL AND path NOT LIKE '%/%';"` should drop to ~0 (only genuine on-disk orphan files with `/` in their path may remain — out of scope here).
- The memory note "scan leaves NULL-uri stub cruft" (`graph-io-imports-unresolved-specifier-dst`) becomes stale after this ships; update it.
- `_RESOLVED_FILTER` in `queries.py` is now effectively a no-op for `imports` edges (none are left as `unresolved`), but it remains correct and harmless — leave it (YAGNI).

## Self-Review

1. **Spec coverage (Option A = "don't pollute the graph with false `file` nodes"):**
   - From-import external stubs (`name != path`) → Task 1 (delete edge → orphan cleanup). ✓
   - Plain-import stubs (`name == path`) → Task 2 (query guard removed). ✓
   - Real NULL-uri files not deleted → Task 2 (is_file() skip; asserted by `orphan.py` survival). ✓
   - First-party imports still resolve (incl. plain `import pkg`) → Task 2 (`pypkg` repoint) + Task 3 (`helper.py`). ✓
   - Works in the actual `gw scan` (incremental) path → Task 3 (`update.run(full=False)`). ✓
   - stdlib value not lost → unchanged `builtins.refresh`; noted in docstring. ✓

2. **Placeholder scan:** No TBD/TODO/"handle edge cases" — every code step contains full code and exact commands. ✓

3. **Type/name consistency:** `_make_py_repo` / `_make_js_repo` (helpers), `resolve.resolve_file_imports(conn, repo)` (existing signature), `update.run(repo, full=False)` (matches `update.py:232`), `_git_repo.init_repo` / `write_and_commit` (match `tests/_git_repo.py`), `resolve_workspace(...).workspace` + `graph_dir(ws)` (match `conftest.py:52-53`). Test renamed `test_resolve_file_imports_external_unresolved` → `test_resolve_file_imports_external_dropped` consistently (no other references to the old name in the file). ✓
