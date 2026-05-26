# Phase 29: Structural Nodes + Containment Tree — Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 7 (1 new emitter, 1 source-parser extension, 3 surgical edits, 1 new test, 1 new fixture tree)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/graph-io/src/graph_io/structural_nodes.py` (NEW) | emitter module | FS walk → upsert | `packages/graph-io/src/graph_io/packages.py` | exact (same package, same pattern, same call shape) |
| `packages/graph-io/src/graph_io/update.py` (MODIFY, +1 line in `run()`) | orchestrator edit | n/a — single call insertion | `packages/graph-io/src/graph_io/update.py:236` (existing `packages.refresh(...)` call) | exact (same orchestrator) |
| `packages/graph-io/src/graph_io/resolve.py` (MODIFY, +1 clause) | SQL predicate edit | n/a — WHERE-clause change | `packages/graph-io/src/graph_io/resolve.py:53-56` (existing sweep DELETE) | exact (same statement) |
| `packages/source-parser/src/source_parser/parsers/python.py` (MODIFY) | AST extension | parse → SourceNode.attrs | existing `_all_exports_at` (lines 216-253) + `parse_errors` injection (line 279) | exact (same file, same attrs-mutation pattern) |
| `packages/graph-io/tests/test_structural_nodes.py` (NEW) | test module | seed → emit → SQL-assert | `packages/graph-io/tests/test_packages.py` + `tests/test_resolve.py` | exact (graph-io test conventions) |
| `packages/graph-io/tests/fixtures/sample_monorepo/` (NEW tree) | test fixture | static files | None in graph-io (NEW pattern for this package) | no analog — use D-22 specifics |
| `packages/source-parser/tests/test_parser_python.py` (MODIFY, +cases) | parser test | parse → assert attrs | existing `test_fixture` parametrized over `_FIXTURES` | exact (add fixture .py + expected .json pair) |

## Pattern Assignments

### `packages/graph-io/src/graph_io/structural_nodes.py` (NEW emitter — D-01..D-15, D-18, D-20, D-23)

**Analog:** `packages/graph-io/src/graph_io/packages.py`

**Imports + module conventions** (analog lines 1-17):
```python
"""Manifest scanning: pyproject.toml + package.json → kind:package nodes."""

from __future__ import annotations

import json
import sqlite3
import sys
import tomllib
from pathlib import Path
from typing import Any

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import _ignore, upsert
from graph_io.uri import RepoContext, pkg_uri
```

**For `structural_nodes.py` the imports become:**
```python
"""Structural nodes: Repository + SubPackage + File role flags (STRUCT-01..05)."""

from __future__ import annotations

import fnmatch
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import _ignore, upsert
from graph_io.uri import RepoContext, file_uri, pkg_uri, repo_uri, subpkg_uri
```

**Public function signature pattern** (analog lines 95-107) — mirror exactly for `emit()`:
```python
def refresh(conn: sqlite3.Connection, *, repo_root: Path, ctx: RepoContext) -> None:
    """Rescan manifests under `repo_root` and upsert kind:package nodes + contains edges.
    ...
    """
    repo_root = Path(repo_root).resolve()
    skip_dirs = _ignore.load_skip_dirs(repo_root)
    for pkg_dir, info in _discover_manifests(repo_root, skip_dirs):
        ...
        upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
```

**New signature per D-23** — orchestrator passes `skip_dirs` (already loaded in `update.run()` line 208), so accept it as a kwarg rather than re-loading:
```python
def emit(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    ctx: RepoContext,
    skip_dirs: frozenset[str],
) -> None:
```

**Node-construction pattern** (analog lines 114-127) — copy verbatim for Repository / SubPackage / File:
```python
nodes = [
    GraphNode(
        kind="package",
        name=info["name"],
        path=rel_prefix or None,
        line=None,
        attrs={
            "version": info["version"],
            "dependencies": info["dependencies"],
            "language": info["language"],
            "uri": pkg_uri(ctx, info["name"]),
        },
    )
]
```
- Stash the URI inside `attrs["uri"]`; `_upsert_node` (upsert.py:51) pops it to the column automatically. **Do NOT** try to write it elsewhere.
- `path=None` for Repository (D-03 says Repository carries no path); `path=rel_prefix` for SubPackage; `path=rel_path` for File.

**Skip-list filtering pattern** (analog `_should_skip` lines 20-27) — reuse `_ignore.should_skip` for FS walk:
```python
if _ignore.should_skip(str(manifest_path), skip_dirs):
    return True
```

**Package-language read pattern (D-18)** — query Package node attrs that `packages.refresh` already wrote (analog line 124 sets `"language": info["language"]`). Read with:
```python
rows = conn.execute(
    "SELECT name, path, attrs_json FROM nodes WHERE kind='package'"
).fetchall()
for name, rel_path, attrs_json in rows:
    attrs = json.loads(attrs_json) if attrs_json else {}
    language = attrs.get("language")
    if language == "python":
        # walk for SubPackages
    # else: emit Files directly under Package
```

**Edge-emission pattern** (analog lines 128-138) — `physically_contains` edges follow the same tuple-key shape:
```python
GraphEdge(
    src=("package", info["name"], rel_prefix or None),
    dst=("file", file_path, file_path),
    kind="contains",
    attrs={},
)
```
For Phase 29, `kind="physically_contains"` and `src` cycles through Repository / Package / SubPackage tuples; `dst` is the contained child's `(kind, name, path)` triple. Note `_upsert_edge` (upsert.py:69) does `_ensure_node` on both endpoints, so edges can be emitted in any order relative to node upserts within the same `upsert_records` call.

**Git subprocess pattern for D-01 (`default_branch`, `url`)** — reuse `update._git` directly:
```python
# In structural_nodes.py
from graph_io.update import _git, NotInGitRepoError

def _detect_default_branch(repo_root: Path) -> str | None:
    try:
        out = _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo_root).strip()
    except NotInGitRepoError:
        try:
            out = _git(["symbolic-ref", "--short", "HEAD"], cwd=repo_root).strip()
        except NotInGitRepoError:
            return None  # detached HEAD
    return out.removeprefix("origin/") or None
```
Mirrors `update._derive_repo_context` (update.py:141-157) — try-remote, fall back, return None on failure. **Do NOT** import `subprocess` directly; reuse `_git` so the `NotInGitRepoError` translation is consistent.

**URI helpers in use** (uri.py:15-37):
- `repo_uri(ctx)` → `repo:org/repo`
- `pkg_uri(ctx, name)` already on Package (don't re-write)
- `subpkg_uri(ctx, pkg_name, dotted_path)` → `subpkg:org/repo/pkg/dotted.path` for each SubPackage
- `file_uri(ctx, rel_path)` → `file:org/repo/rel/path.py` for each File

**Module-private constants pattern** — `packages._SKIP_REPO_PREFIXES = ("lattice/",)` (packages.py:17) is the model for D-10/D-11/D-12 allow-lists. Put them at module top:
```python
_CONFIG_FILENAMES: frozenset[str] = frozenset({
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "pytest.ini",
    "mypy.ini", ".flake8", "ruff.toml", "uv.toml",
    "package.json", ".eslintrc", ".prettierrc",
    "Cargo.toml", "go.mod", "Makefile", "Justfile", ".editorconfig",
})
_CONFIG_GLOBS: tuple[str, ...] = (
    "tsconfig*.json", "*.config.js", "*.config.ts", "*.config.mjs", "*.config.cjs",
    ".eslintrc.*", ".prettierrc.*", "babel.config.*",
)
_GENERATED_FILENAME_PATTERNS: tuple[str, ...] = (
    "*_pb2.py", "*_pb2_grpc.py", "*.pb.go", "*.gen.ts", "*.gen.go",
    "*.generated.ts", "*.generated.go",
)
_SHEBANG_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".rb", ".pl", "",
})
```
Use `fnmatch.fnmatch(name, pattern)` for glob matching (stdlib, no new deps per STACK.md).

**File-reading safety pattern (D-11 content-marker scan)** — open with `errors="ignore"` to tolerate the occasional binary that slipped past `_ignore`:
```python
def _has_generated_marker(path: Path) -> bool:
    if path.stat().st_size > 1_000_000:
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh):
                if i >= 20:
                    break
                if "@generated" in line:
                    return True
                low = line.lower()
                if "code generated by" in low or "do not edit" in low:
                    return True
    except OSError:
        return False
    return False
```

**Source-parser attrs read (D-20)** — Python file SourceNode.attrs are surfaced via `_process_files` (update.py:125-128) which does `node.attrs.setdefault("language", tree.language)`. The Phase 29 emit step runs AFTER `_process_files` and reads what landed in the DB:
```python
row = conn.execute(
    "SELECT attrs_json FROM nodes WHERE kind='file' AND path=?", (rel,)
).fetchone()
attrs = json.loads(row[0]) if row and row[0] else {}
has_main = bool(attrs.get("_has_main_block"))
is_importable = bool(attrs.get("_has_importable_symbols"))
```
For JS/TS files (per D-20): `has_main=False`, `is_importable=True` (defaults, no parser attr read needed).

---

### `packages/graph-io/src/graph_io/update.py` (MODIFY — D-23 single-line insertion)

**Analog:** the existing `packages.refresh` call inside `update.run()`.

**Existing context** (lines 234-252) — the `with store.transaction(conn):` block:
```python
with store.transaction(conn):
    _process_files(conn, repo_root, changed, skip_dirs)
    packages.refresh(conn, repo_root=repo_root, ctx=ctx)
    if full:
        tracked_paths = [
            rel for _, rel in changed
            if _is_parseable(rel) and not _ignore.should_skip(rel, skip_dirs)
        ]
        ...
    resolve.sweep(conn)
    _set_metadata(conn, "last_indexed_commit", head)
    _set_metadata(conn, "last_indexed_at", _dt.datetime.now(_dt.UTC).isoformat())
```

**Edit per D-23:**
1. Add import: `from graph_io import _ignore, packages, resolve, schema, store, structural_nodes, upsert`
2. Insert after `packages.refresh(...)`, before the `if full:` block (so it runs on incremental updates too; the `if full:` deletion happens BEFORE structural_nodes.emit only if order matters — verify with planner):

```python
packages.refresh(conn, repo_root=repo_root, ctx=ctx)
structural_nodes.emit(conn, repo_root=repo_root, ctx=ctx, skip_dirs=skip_dirs)
```

The `ctx` and `skip_dirs` locals are already bound at update.py:207-208 — zero new plumbing.

---

### `packages/graph-io/src/graph_io/resolve.py` (MODIFY — D-16 one-clause SQL edit)

**Analog:** the existing `sweep()` DELETE statement.

**Existing pattern** (lines 53-56):
```python
conn.execute(
    "DELETE FROM nodes WHERE path IS NULL AND kind != 'package' "
    "AND id NOT IN (SELECT dst FROM edges)"
)
```

**Edit per D-16** — append `AND uri IS NULL` to the WHERE clause:
```python
conn.execute(
    "DELETE FROM nodes WHERE path IS NULL AND uri IS NULL AND kind != 'package' "
    "AND id NOT IN (SELECT dst FROM edges)"
)
```

Rationale (D-16): structural nodes always carry a non-NULL `uri` (written by `structural_nodes.emit` via the `attrs["uri"]` → column pop in upsert.py:51); orphan AST nodes never have a `uri`. Self-maintaining — adding new structural kinds in v1.7 needs no further sweep edit.

**Idempotency note** — the test `test_sweep_is_idempotent` (test_resolve.py:159) must still pass after the edit. Add the D-17 sentinel test alongside it (see test patterns below).

---

### `packages/source-parser/src/source_parser/parsers/python.py` (MODIFY — SPARSER-01 / D-19)

**Analog within the same file:** `_collect_parse_errors` (lines 27-44) returns metadata that is stuffed onto `file_node.attrs["parse_errors"]` at line 279. `_all_exports_at` (lines 216-253) shows the file-root-children walk pattern.

**Existing pattern for attrs injection** (line 277-279):
```python
errors = _collect_parse_errors(root)
if errors:
    file_node.attrs["parse_errors"] = errors
```

**For SPARSER-01 add two helpers + two attr writes:**
```python
def _has_main_block(file_root: tree_sitter.Node, source: bytes) -> bool:
    """Detect `if __name__ == "__main__":` at file scope."""
    for child in file_root.children:
        if child.type == "if_statement":
            cond = child.child_by_field_name("condition")
            if cond is not None and "__name__" in _text(cond, source) and "__main__" in _text(cond, source):
                return True
    return False


def _has_importable_symbols(file_root: tree_sitter.Node, source: bytes) -> bool:
    """Detect public top-level defs (function/class/assignment whose name does not start with _)."""
    for child in file_root.children:
        if child.type in {"function_definition", "class_definition"}:
            name = _name_of(child, source)
            if name and not name.startswith("_"):
                return True
        elif child.type == "decorated_definition":
            inner = child.child_by_field_name("definition")
            if inner is not None:
                name = _name_of(inner, source)
                if name and not name.startswith("_"):
                    return True
        elif child.type == "assignment":
            left = child.child_by_field_name("left")
            if left is not None:
                txt = _text(left, source)
                if txt and not txt.startswith("_") and txt.isidentifier():
                    return True
    return False
```

**Inside `PythonParser.parse` after the `errors` assignment (around line 279):**
```python
file_node.attrs["_has_main_block"] = _has_main_block(root, source)
file_node.attrs["_has_importable_symbols"] = _has_importable_symbols(root, source)
```

Names prefixed with `_` to signal "consumed by graph-io, not for end-users" — matches the SourceNode internal-attrs convention referenced in CONTEXT.md D-19.

**Test fixture pattern** (source-parser tests use `_fixture_loader.fixtures_for` — see `test_parser_python.py:11-12`). Add two new fixture pairs under `packages/source-parser/tests/fixtures/python/`:
- `has_main_block.py` + `has_main_block.json` (expected serialization with `_has_main_block: true`)
- `importable_symbols.py` + `importable_symbols.json` (expected `_has_importable_symbols: true`)

---

### `packages/graph-io/tests/test_structural_nodes.py` (NEW — D-17 sentinel + D-22 strict-tree invariant)

**Analog:** `packages/graph-io/tests/test_resolve.py` (in-memory DB fixture pattern) + `packages/graph-io/tests/test_packages.py` (RepoContext + structured assertions) + `packages/graph-io/tests/test_store.py:95-109` (`_seed_v1_db` for low-level node insertion).

**Imports pattern** (test_resolve.py:1-12 + test_packages.py:1-16):
```python
"""Structural nodes: Repository, SubPackage, File role flags (STRUCT-01..06)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import resolve, store, structural_nodes, upsert
from graph_io.uri import RepoContext

_CTX = RepoContext(org="test", repo="repo")
```

**conn fixture** (verbatim from test_resolve.py:15-20):
```python
@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()
```

**D-17 sentinel test** — `resolve.sweep` must NOT delete URI-carrying structural nodes:
```python
def test_sweep_preserves_uri_bearing_structural_nodes(conn: sqlite3.Connection) -> None:
    """STRUCT-06 / D-17: Repository (path=NULL, uri='repo:...') survives sweep."""
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[
                GraphNode(
                    kind="repository", name="x", path=None, line=None,
                    attrs={"uri": "repo:test/x"},
                ),
                # orphan AST node — path=NULL, uri=NULL → must be deleted
                GraphNode(
                    kind="function", name="orphan", path=None, line=None, attrs={},
                ),
            ],
            edges=[],
        ),
    )
    resolve.sweep(conn)
    kinds = {row[0] for row in conn.execute("SELECT kind FROM nodes").fetchall()}
    assert "repository" in kinds
    assert "function" not in kinds
```

**D-22 strict-tree fixture test** — uses `_run_cli` helper (look for it in `test_cli_*.py`; pattern below references `init_repo` + `write_and_commit` from `_git_repo.py`):
```python
def test_physically_contains_is_strict_tree(tmp_path: Path) -> None:
    """STRUCT-04: every node has exactly one structural parent."""
    # Either: copy fixtures/sample_monorepo/ into tmp_path, init_repo, commit, run cg update
    # Or: use _run_cli helper if it exists in test_cli_smoke.py / test_e2e.py
    fixture_src = Path(__file__).parent / "fixtures" / "sample_monorepo"
    # ... copy tree, git init, commit, run update.run(tmp_path, full=True) ...

    ws = resolve_workspace(tmp_path, require_manifest=False).workspace
    with sqlite3.connect(graph_dir(ws) / "code.db") as probe:
        rows = probe.execute(
            "SELECT dst, COUNT(*) FROM edges WHERE kind='physically_contains' "
            "GROUP BY dst HAVING COUNT(*) > 1"
        ).fetchall()
    assert rows == [], f"Nodes with multiple structural parents: {rows}"
```

**Test-naming convention** (from test_packages.py / test_resolve.py): `test_<verb>_<subject>` — keep flat module-level functions, no test classes.

---

### `packages/graph-io/tests/fixtures/sample_monorepo/` (NEW — D-22)

**No analog in graph-io.** Use the layout suggested in CONTEXT.md specifics block (lines 185-206) verbatim as the starting point:
```
tests/fixtures/sample_monorepo/
  pyproject.toml                          # root manifest
  packages/
    mypkg/
      pyproject.toml
      src/mypkg/__init__.py
      src/mypkg/foo.py
      src/mypkg/sub/__init__.py
      src/mypkg/sub/bar.py
      src/mypkg/sub/deep/__init__.py
      src/mypkg/sub/deep/baz.py
      tests/test_foo.py
    jspkg/
      package.json
      index.js
      types.d.ts
      gen/data.gen.ts
  tests/
    integration/test_top.py
```

Add for heuristic coverage breadth (Claude's Discretion per CONTEXT.md):
- `packages/mypkg/scripts/run.sh` with shebang `#!/bin/bash\n` (D-12 shebang detection)
- `packages/mypkg/src/mypkg/proto/data_pb2.py` (D-11 `is_generated` filename pattern)

File contents should be MINIMAL — single-line `pass` or `# placeholder` per `.py` file is sufficient since the test asserts on graph structure, not parsed function bodies.

---

## Shared Patterns

### URI emission → column (NOT attrs_json)
**Source:** `packages/graph-io/src/graph_io/upsert.py:48-59`
**Apply to:** every node `structural_nodes.emit` creates
```python
def _upsert_node(conn: sqlite3.Connection, node: GraphNode) -> int:
    key: NodeKey = (node.kind, node.name, node.path)
    attrs_for_json = dict(node.attrs)
    uri_value = attrs_for_json.pop("uri", None)  # <-- pops uri from attrs to column
    ...
```
Always set `attrs["uri"] = <composed_uri>` on the GraphNode; upsert handles the column landing. This was locked in Phase 28 D-10 and has a sentinel test (`test_refresh_writes_pkg_uri_on_package_nodes` in test_packages.py:159-177).

### Skip-list propagation
**Source:** `packages/graph-io/src/graph_io/update.py:208` + `packages/graph-io/src/graph_io/_ignore.py:32-33`
**Apply to:** every FS walk in `structural_nodes.emit`
```python
# update.run() already loads it:
skip_dirs = _ignore.load_skip_dirs(repo_root)
# ... passes to packages.refresh via internal call; structural_nodes.emit receives via kwarg per D-23
```
Walk pattern:
```python
for path in repo_root.rglob("*"):
    rel = path.relative_to(repo_root).as_posix()
    if _ignore.should_skip(rel, skip_dirs):
        continue
    ...
```
**Do NOT** re-implement directory filtering; `should_skip` already handles `.git`, `.venv`, `node_modules`, `__pycache__`, etc., plus user `.cgignore` extensions.

### Transaction scope
**Source:** `packages/graph-io/src/graph_io/update.py:234`
**Apply to:** `structural_nodes.emit` is invoked INSIDE the `with store.transaction(conn):` block — emit must NOT open its own transaction. Single sqlite write per `cg update` call is the invariant (Phase 28 D-11).

### Test conn fixture
**Source:** `packages/graph-io/tests/test_resolve.py:15-20` (also test_packages.py:19-24)
**Apply to:** every new test in `test_structural_nodes.py`
```python
@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()
```
`store.connect(... create=True)` already runs the v2 schema DDL, so the `uri` column exists from t=0.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `packages/graph-io/tests/fixtures/sample_monorepo/` | hand-curated multi-package tree | static | First multi-package fixture tree in graph-io; existing tests build tmp trees programmatically via `tmp_path` + `write_and_commit`. Use the D-22 spec literally. |

---

## Metadata

**Analog search scope:** `packages/graph-io/src/graph_io/`, `packages/graph-io/tests/`, `packages/source-parser/src/source_parser/`, `packages/source-parser/tests/`
**Files scanned:** 12 (6 source, 6 test)
**Pattern extraction date:** 2026-05-26
