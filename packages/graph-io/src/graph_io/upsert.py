"""Upsert GraphRecords into SQLite. Tuple-keyed; idempotent."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

NodeKey = tuple[str, str, str | None]


def _serialize(attrs: dict[str, Any]) -> str | None:
    return json.dumps(attrs, sort_keys=True) if attrs else None


def _node_id(conn: sqlite3.Connection, key: NodeKey) -> int | None:
    kind, name, path = key
    if path is None:
        row = conn.execute(
            "SELECT id FROM nodes WHERE kind=? AND name=? AND path IS NULL",
            (kind, name),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM nodes WHERE kind=? AND name=? AND path=?",
            (kind, name, path),
        ).fetchone()
    return row[0] if row else None


def _insert_node(
    conn: sqlite3.Connection,
    key: NodeKey,
    line: int | None,
    attrs_json: str | None,
    uri: str | None,
) -> int:
    kind, name, path = key
    cursor = conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?, ?, ?, ?, ?, ?)",
        (kind, name, path, line, attrs_json, uri),
    )
    return cursor.lastrowid


def _upsert_node(conn: sqlite3.Connection, node: GraphNode) -> int:
    key: NodeKey = (node.kind, node.name, node.path)
    attrs_for_json = dict(node.attrs)
    uri_value = attrs_for_json.pop("uri", None)
    nid = _node_id(conn, key)
    if nid is not None:
        conn.execute(
            "UPDATE nodes SET line=?, attrs_json=?, uri=? WHERE id=?",
            (node.line, _serialize(attrs_for_json), uri_value, nid),
        )
        return nid
    return _insert_node(conn, key, node.line, _serialize(attrs_for_json), uri_value)


def _ensure_node(conn: sqlite3.Connection, key: NodeKey) -> int:
    nid = _node_id(conn, key)
    if nid is not None:
        return nid
    return _insert_node(conn, key, None, None, None)


def _upsert_edge(conn: sqlite3.Connection, edge: GraphEdge) -> None:
    src_id = _ensure_node(conn, edge.src)
    dst_id = _ensure_node(conn, edge.dst)
    attrs = dict(edge.attrs)
    if edge.dst[2] is None:
        attrs.setdefault("resolution", "unresolved")
    attrs_json = _serialize(attrs)
    conn.execute(
        "INSERT INTO edges(src, dst, kind, attrs_json) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(src, dst, kind) DO UPDATE SET attrs_json=excluded.attrs_json",
        (src_id, dst_id, edge.kind, attrs_json),
    )


def upsert_records(conn: sqlite3.Connection, records: GraphRecords) -> None:
    """Upsert nodes and edges from a parser GraphRecords."""
    for node in records.nodes:
        _upsert_node(conn, node)
    for edge in records.edges:
        _upsert_edge(conn, edge)
