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
