"""Resolve sweep: unresolved edges → exact / ambiguous / unresolved."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import resolve, store, upsert


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def _seed(conn: sqlite3.Connection, nodes=(), edges=()) -> None:
    upsert.upsert_records(conn, GraphRecords(nodes=list(nodes), edges=list(edges)))


def test_sweep_resolves_exact_match(conn: sqlite3.Connection) -> None:
    _seed(
        conn,
        nodes=[
            GraphNode(kind="function", name="caller", path="a.py", line=1, attrs={}),
            GraphNode(kind="function", name="target", path="b.py", line=5, attrs={}),
        ],
        edges=[
            GraphEdge(
                src=("function", "caller", "a.py"),
                dst=("function", "target", None),
                kind="calls",
                attrs={},
            ),
        ],
    )

    resolve.sweep(conn)

    rows = conn.execute(
        "SELECT n2.path, e.attrs_json FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id JOIN nodes n2 ON e.dst=n2.id "
        "WHERE e.kind='calls'"
    ).fetchall()
    assert len(rows) == 1
    path, attrs_json = rows[0]
    assert path == "b.py"
    assert json.loads(attrs_json)["resolution"] == "exact"


def test_sweep_fans_out_ambiguous(conn: sqlite3.Connection) -> None:
    _seed(
        conn,
        nodes=[
            GraphNode(kind="function", name="caller", path="a.py", line=1, attrs={}),
            GraphNode(kind="function", name="target", path="b.py", line=5, attrs={}),
            GraphNode(kind="function", name="target", path="c.py", line=7, attrs={}),
        ],
        edges=[
            GraphEdge(
                src=("function", "caller", "a.py"),
                dst=("function", "target", None),
                kind="calls",
                attrs={},
            ),
        ],
    )

    resolve.sweep(conn)

    rows = conn.execute(
        "SELECT n2.path, e.attrs_json FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id JOIN nodes n2 ON e.dst=n2.id "
        "WHERE e.kind='calls' ORDER BY n2.path"
    ).fetchall()
    assert len(rows) == 2
    paths = [r[0] for r in rows]
    assert paths == ["b.py", "c.py"]
    for _, attrs_json in rows:
        assert json.loads(attrs_json)["resolution"] == "ambiguous"


def test_sweep_leaves_unresolved_alone(conn: sqlite3.Connection) -> None:
    _seed(
        conn,
        nodes=[GraphNode(kind="function", name="caller", path="a.py", line=1, attrs={})],
        edges=[
            GraphEdge(
                src=("function", "caller", "a.py"),
                dst=("function", "missing", None),
                kind="calls",
                attrs={},
            ),
        ],
    )

    resolve.sweep(conn)

    rows = conn.execute(
        "SELECT n2.path, e.attrs_json FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id JOIN nodes n2 ON e.dst=n2.id "
        "WHERE e.kind='calls'"
    ).fetchall()
    assert len(rows) == 1
    path, attrs_json = rows[0]
    assert path is None
    assert json.loads(attrs_json)["resolution"] == "unresolved"


def test_sweep_deletes_resolved_placeholders(conn: sqlite3.Connection) -> None:
    _seed(
        conn,
        nodes=[
            GraphNode(kind="function", name="caller", path="a.py", line=1, attrs={}),
            GraphNode(kind="function", name="target", path="b.py", line=5, attrs={}),
        ],
        edges=[
            GraphEdge(
                src=("function", "caller", "a.py"),
                dst=("function", "target", None),
                kind="calls",
                attrs={},
            ),
        ],
    )

    resolve.sweep(conn)

    null_nodes = conn.execute("SELECT COUNT(*) FROM nodes WHERE path IS NULL").fetchone()[0]
    assert null_nodes == 0


def test_sweep_keeps_unresolved_placeholders(conn: sqlite3.Connection) -> None:
    _seed(
        conn,
        nodes=[GraphNode(kind="function", name="caller", path="a.py", line=1, attrs={})],
        edges=[
            GraphEdge(
                src=("function", "caller", "a.py"),
                dst=("function", "missing", None),
                kind="calls",
                attrs={},
            ),
        ],
    )

    resolve.sweep(conn)

    null_nodes = conn.execute("SELECT COUNT(*) FROM nodes WHERE path IS NULL").fetchone()[0]
    assert null_nodes == 1


def test_sweep_preserves_uri_bearing_structural_nodes(conn: sqlite3.Connection) -> None:
    """STRUCT-06 / D-17: Repository (path=NULL, uri='repo:...') survives sweep;
    orphan AST node (path=NULL, uri=NULL) is deleted."""
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[
                GraphNode(
                    kind="repository", name="x", path=None, line=None,
                    attrs={"uri": "repo:test/x"},
                ),
                GraphNode(
                    kind="function", name="orphan", path=None, line=None, attrs={},
                ),
            ],
            edges=[],
        ),
    )
    resolve.sweep(conn)
    kinds = {row[0] for row in conn.execute("SELECT kind FROM nodes").fetchall()}
    assert "repository" in kinds, "Repository node was deleted by sweep (STRUCT-06 violated)"
    assert "function" not in kinds, "Orphan AST node was not cleaned by sweep"


def test_sweep_is_idempotent(conn: sqlite3.Connection) -> None:
    _seed(
        conn,
        nodes=[
            GraphNode(kind="function", name="caller", path="a.py", line=1, attrs={}),
            GraphNode(kind="function", name="target", path="b.py", line=5, attrs={}),
        ],
        edges=[
            GraphEdge(
                src=("function", "caller", "a.py"),
                dst=("function", "target", None),
                kind="calls",
                attrs={},
            ),
        ],
    )

    resolve.sweep(conn)
    resolve.sweep(conn)

    count = conn.execute("SELECT COUNT(*) FROM edges WHERE kind='calls'").fetchone()[0]
    assert count == 1


# ---------------------------------------------------------------------------
# Tests for sweep_skip_dir_files
# ---------------------------------------------------------------------------

_SKIP_DIRS: frozenset[str] = frozenset({"dist", "build", "node_modules"})


def test_sweep_skip_dir_files_deletes_target_and_edge(conn: sqlite3.Connection) -> None:
    """Test A: dist file node (uri=NULL) and its inbound imports edge are deleted."""
    # Insert a real src file node with uri set
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'src/index.ts', 'pkg/src/index.ts', 1, '{}', 'repo:org/pkg/blob/abc/pkg/src/index.ts')"
    )
    src_id = conn.execute(
        "SELECT id FROM nodes WHERE path='pkg/src/index.ts'"
    ).fetchone()[0]

    # Insert a dist file node with uri=NULL (the skip-dir target)
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pkg/dist/index.js', 'pkg/dist/index.js', NULL, '{}', NULL)"
    )
    dst_id = conn.execute(
        "SELECT id FROM nodes WHERE path='pkg/dist/index.js'"
    ).fetchone()[0]

    # Insert an imports edge from src -> dist
    conn.execute(
        "INSERT INTO edges(src, dst, kind, attrs_json) VALUES (?, ?, 'imports', '{}')",
        (src_id, dst_id),
    )

    resolve.sweep_skip_dir_files(conn, _SKIP_DIRS)

    # dist node is gone
    dist_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE path='pkg/dist/index.js'"
    ).fetchone()[0]
    assert dist_count == 0, "dist file node should have been deleted"

    # imports edge is gone (orphaned)
    edge_count = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE src=? OR dst=?", (dst_id, dst_id)
    ).fetchone()[0]
    assert edge_count == 0, "imports edge targeting dist node should have been deleted"

    # src node still there
    src_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE path='pkg/src/index.ts'"
    ).fetchone()[0]
    assert src_count == 1, "real src file node should survive"


def test_sweep_skip_dir_files_spares_uri_bearing_src_file(conn: sqlite3.Connection) -> None:
    """Test B: A file node with a non-null uri is not touched."""
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pkg/src/index.ts', 'pkg/src/index.ts', 1, '{}', 'repo:org/pkg/blob/abc/pkg/src/index.ts')"
    )

    resolve.sweep_skip_dir_files(conn, _SKIP_DIRS)

    count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE path='pkg/src/index.ts'"
    ).fetchone()[0]
    assert count == 1, "uri-bearing src file should survive sweep"


def test_sweep_skip_dir_files_spares_non_file_nodes(conn: sqlite3.Connection) -> None:
    """Test C: package node (uri=NULL) and function placeholder (path=NULL) survive."""
    # package node with uri=NULL
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('package', 'my-pkg', NULL, NULL, '{}', NULL)"
    )
    # function placeholder (path=NULL) — path is NULL so skip-dir match is N/A
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('function', 'someFn', NULL, NULL, '{}', NULL)"
    )
    # Edge referencing the function placeholder so it stays alive
    pkg_id = conn.execute("SELECT id FROM nodes WHERE kind='package'").fetchone()[0]
    fn_id = conn.execute("SELECT id FROM nodes WHERE kind='function'").fetchone()[0]
    conn.execute(
        "INSERT INTO edges(src, dst, kind, attrs_json) VALUES (?, ?, 'calls', '{}')",
        (pkg_id, fn_id),
    )

    resolve.sweep_skip_dir_files(conn, _SKIP_DIRS)

    kinds = {row[0] for row in conn.execute("SELECT kind FROM nodes").fetchall()}
    assert "package" in kinds, "package node should survive sweep_skip_dir_files"
    assert "function" in kinds, "function placeholder should survive sweep_skip_dir_files"


def test_sweep_skip_dir_files_idempotent(conn: sqlite3.Connection) -> None:
    """Test D: running sweep twice produces stable counts."""
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pkg/dist/index.js', 'pkg/dist/index.js', NULL, '{}', NULL)"
    )
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pkg/src/index.ts', 'pkg/src/index.ts', 1, '{}', 'repo:x')"
    )

    resolve.sweep_skip_dir_files(conn, _SKIP_DIRS)
    count_after_first = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    resolve.sweep_skip_dir_files(conn, _SKIP_DIRS)
    count_after_second = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    assert count_after_first == count_after_second, "sweep should be idempotent"


def test_sweep_skip_dir_files_spares_non_skip_dir_null_uri_file(conn: sqlite3.Connection) -> None:
    """Test E: a file node with uri=NULL but NO skip-dir component is untouched."""
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) "
        "VALUES ('file', 'pkg/src/generated.ts', 'pkg/src/generated.ts', NULL, '{}', NULL)"
    )

    resolve.sweep_skip_dir_files(conn, _SKIP_DIRS)

    count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE path='pkg/src/generated.ts'"
    ).fetchone()[0]
    assert count == 1, "non-skip-dir NULL-uri file should survive sweep"
