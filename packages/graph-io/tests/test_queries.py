"""Query layer: find, callers, callees, imports, describe_package, describe_path."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import queries, resolve, store, upsert


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def _seed_call_chain(conn: sqlite3.Connection) -> None:
    nodes = [
        GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
        GraphNode(kind="function", name="alpha", path="a.py", line=1, attrs={}),
        GraphNode(kind="function", name="beta", path="a.py", line=5, attrs={}),
        GraphNode(kind="function", name="gamma", path="a.py", line=10, attrs={}),
    ]
    edges = [
        GraphEdge(src=("function", "alpha", "a.py"), dst=("function", "beta", None), kind="calls", attrs={}),
        GraphEdge(src=("function", "beta", "a.py"), dst=("function", "gamma", None), kind="calls", attrs={}),
    ]
    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
    resolve.sweep(conn)


def test_find_by_name(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="class", name="foo", path="b.py", line=2, attrs={}),
        ],
        edges=[],
    ))
    rows = queries.find(conn, name="foo")
    assert {(r.kind, r.path) for r in rows} == {("function", "a.py"), ("class", "b.py")}


def test_find_by_name_and_kind(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="class", name="foo", path="b.py", line=2, attrs={}),
        ],
        edges=[],
    ))
    rows = queries.find(conn, name="foo", kind="function")
    assert [(r.kind, r.path) for r in rows] == [("function", "a.py")]


def test_callers_depth_bounded(conn: sqlite3.Connection) -> None:
    _seed_call_chain(conn)
    rows = queries.callers(conn, name="gamma", depth=1)
    names = {r.name for r in rows}
    assert names == {"beta"}

    rows = queries.callers(conn, name="gamma", depth=3)
    names = {r.name for r in rows}
    assert names == {"alpha", "beta"}


def test_callees_depth_bounded(conn: sqlite3.Connection) -> None:
    _seed_call_chain(conn)
    rows = queries.callees(conn, name="alpha", depth=1)
    assert {r.name for r in rows} == {"beta"}

    rows = queries.callees(conn, name="alpha", depth=3)
    assert {r.name for r in rows} == {"beta", "gamma"}


def test_imports_returns_resolved_only(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "missing", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imports(conn, path="a.py")
    assert [r.path for r in rows] == ["b.py"]


def test_describe_package(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="package", name="alpha", path="alpha", line=None, attrs={"language": "python", "version": "0.1.0"}),
            GraphNode(kind="file", name="alpha/a.py", path="alpha/a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="alpha/a.py", line=1, attrs={}),
        ],
        edges=[
            GraphEdge(src=("package", "alpha", "alpha"), dst=("file", "alpha/a.py", "alpha/a.py"), kind="contains", attrs={}),
            GraphEdge(src=("file", "alpha/a.py", "alpha/a.py"), dst=("function", "foo", "alpha/a.py"), kind="contains", attrs={}),
        ],
    ))
    desc = queries.describe_package(conn, name="alpha")
    assert desc.name == "alpha"
    assert desc.language == "python"
    assert desc.version == "0.1.0"
    assert "alpha/a.py" in desc.files
    assert desc.counts["function"] == 1


def test_describe_path(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", "a.py"), kind="contains", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    desc = queries.describe_path(conn, path="a.py")
    assert desc.path == "a.py"
    assert any(c.name == "foo" for c in desc.children)
    assert any(i.path == "b.py" for i in desc.imports)


def test_describe_package_returns_none_for_missing(conn: sqlite3.Connection) -> None:
    assert queries.describe_package(conn, name="no-such-package") is None


def test_describe_path_returns_none_for_missing(conn: sqlite3.Connection) -> None:
    assert queries.describe_path(conn, path="no/such/path.py") is None


def test_imported_by_returns_importers_with_symbols(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="file", name="c.py", path="c.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="c.py", line=1, attrs={}),
            GraphNode(kind="function", name="bar", path="c.py", line=5, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "bar", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("function", "foo", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imported_by(conn, path="c.py")
    by_path = {r.path: r for r in rows}
    assert set(by_path) == {"a.py", "b.py"}
    assert by_path["a.py"].symbols == ("bar", "foo")
    assert by_path["b.py"].symbols == ("foo",)
    assert by_path["a.py"].depth == 1


def test_imported_by_symbol_filter_narrows(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="file", name="c.py", path="c.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="c.py", line=1, attrs={}),
            GraphNode(kind="function", name="bar", path="c.py", line=5, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("function", "bar", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imported_by(conn, path="c.py", symbol="foo")
    assert [r.path for r in rows] == ["a.py"]
    assert rows[0].symbols == ("foo",)


def test_imported_by_depth_walks_transitively(conn: sqlite3.Connection) -> None:
    # a.py imports b.py; b.py imports c.py — depth=2 from c.py reaches a.py.
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="file", name="c.py", path="c.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("file", "c.py", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    direct = queries.imported_by(conn, path="c.py", depth=1)
    assert {r.path for r in direct} == {"b.py"}
    transitive = queries.imported_by(conn, path="c.py", depth=2)
    by_path = {r.path: r for r in transitive}
    assert set(by_path) == {"a.py", "b.py"}
    assert by_path["b.py"].depth == 1
    assert by_path["a.py"].depth == 2


def test_imported_by_excludes_unresolved(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "missing", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imported_by(conn, path="b.py")
    assert [r.path for r in rows] == ["a.py"]


def test_exports_returns_exported_symbols(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=10, attrs={}),
            GraphNode(kind="function", name="bar", path="a.py", line=20, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="exports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "bar", None), kind="exports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.exports(conn, path="a.py")
    by_name = {r.name: r for r in rows}
    assert set(by_name) == {"foo", "bar"}
    assert by_name["foo"].kind == "function"
    assert by_name["foo"].line == 10


def test_exported_by_returns_owning_files(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="function", name="foo", path="b.py", line=1, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="exports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("function", "foo", None), kind="exports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.exported_by(conn, name="foo")
    assert sorted(r.path for r in rows) == ["a.py", "b.py"]
    assert all(r.name == "foo" for r in rows)
