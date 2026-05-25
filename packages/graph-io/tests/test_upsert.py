"""Upsert: GraphRecords → SQLite rows; tuple-key dedup; attrs_json round-trip."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import store, upsert


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def _records(nodes=(), edges=()) -> GraphRecords:
    return GraphRecords(nodes=tuple(nodes), edges=tuple(edges))


def test_upsert_inserts_nodes(conn: sqlite3.Connection) -> None:
    records = _records(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=10, attrs={"is_async": True}),
        ],
    )
    upsert.upsert_records(conn, records)
    rows = conn.execute("SELECT kind, name, path, line FROM nodes ORDER BY kind, name").fetchall()
    assert rows == [
        ("file", "a.py", "a.py", None),
        ("function", "foo", "a.py", 10),
    ]


def test_upsert_is_idempotent_on_tuple_key(conn: sqlite3.Connection) -> None:
    records = _records(
        nodes=[GraphNode(kind="function", name="foo", path="a.py", line=10, attrs={})],
    )
    upsert.upsert_records(conn, records)
    upsert.upsert_records(conn, records)
    count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    assert count == 1


def test_upsert_attrs_json_round_trip(conn: sqlite3.Connection) -> None:
    records = _records(
        nodes=[GraphNode(kind="function", name="foo", path="a.py", line=10, attrs={"is_async": True, "decorators": ["x"]})],
    )
    upsert.upsert_records(conn, records)
    row = conn.execute("SELECT attrs_json FROM nodes WHERE name='foo'").fetchone()
    assert json.loads(row[0]) == {"is_async": True, "decorators": ["x"]}


def test_upsert_creates_edges(conn: sqlite3.Connection) -> None:
    records = _records(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=10, attrs={}),
        ],
        edges=[
            GraphEdge(
                src=("file", "a.py", "a.py"),
                dst=("function", "foo", "a.py"),
                kind="contains",
                attrs={},
            ),
        ],
    )
    upsert.upsert_records(conn, records)
    edges = conn.execute(
        "SELECT n1.name, n2.name, e.kind FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id JOIN nodes n2 ON e.dst=n2.id"
    ).fetchall()
    assert edges == [("a.py", "foo", "contains")]


def test_upsert_unresolved_edge_creates_placeholder(conn: sqlite3.Connection) -> None:
    records = _records(
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
    upsert.upsert_records(conn, records)
    placeholder = conn.execute(
        "SELECT kind, name, path FROM nodes WHERE name='missing'"
    ).fetchone()
    assert placeholder == ("function", "missing", None)
    edge = conn.execute(
        "SELECT attrs_json FROM edges WHERE kind='calls'"
    ).fetchone()
    assert json.loads(edge[0]) == {"resolution": "unresolved"}
