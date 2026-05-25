"""Schema apply + idempotency + metadata initialization."""

from __future__ import annotations

import sqlite3

import pytest

from graph_io import schema


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def test_apply_schema_creates_tables(conn: sqlite3.Connection) -> None:
    schema.apply_schema(conn)
    assert _table_names(conn) == {"nodes", "edges", "metadata"}


def test_apply_schema_creates_indexes(conn: sqlite3.Connection) -> None:
    schema.apply_schema(conn)
    assert _index_names(conn) == {
        "idx_nodes_kind_name",
        "idx_nodes_path",
        "idx_edges_dst_kind",
        "idx_edges_src_kind",
    }


def test_apply_schema_inserts_schema_version(conn: sqlite3.Connection) -> None:
    schema.apply_schema(conn)
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = 'schema_version'"
    ).fetchone()
    assert row == (str(schema.SCHEMA_VERSION),)


def test_apply_schema_is_idempotent(conn: sqlite3.Connection) -> None:
    schema.apply_schema(conn)
    schema.apply_schema(conn)
    assert _table_names(conn) == {"nodes", "edges", "metadata"}
    rows = conn.execute("SELECT COUNT(*) FROM metadata").fetchone()
    assert rows == (1,)


def test_schema_version_is_one() -> None:
    assert schema.SCHEMA_VERSION == 1
