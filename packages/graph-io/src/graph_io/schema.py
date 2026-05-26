"""SQLite schema for the code graph.

Schema is intentionally minimal: two tables (nodes, edges) plus metadata.
Per-language detail lives in `attrs_json` blobs. Bumping SCHEMA_VERSION
forces a full rebuild via `cg update --full`.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 2

_DDL_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS nodes (
        id          INTEGER PRIMARY KEY,
        kind        TEXT NOT NULL,
        name        TEXT NOT NULL,
        path        TEXT,
        line        INTEGER,
        attrs_json  TEXT,
        uri         TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_nodes_kind_name ON nodes(kind, name)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path)",
    "CREATE INDEX IF NOT EXISTS idx_nodes_uri ON nodes(uri)",
    """
    CREATE TABLE IF NOT EXISTS edges (
        src         INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        dst         INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
        kind        TEXT NOT NULL,
        attrs_json  TEXT,
        PRIMARY KEY (src, dst, kind)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_edges_dst_kind ON edges(dst, kind)",
    "CREATE INDEX IF NOT EXISTS idx_edges_src_kind ON edges(src, kind)",
    """
    CREATE TABLE IF NOT EXISTS metadata (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
)


def apply_schema(conn: sqlite3.Connection) -> None:
    """Apply the schema and ensure metadata.schema_version is set.

    Idempotent: safe to call on an already-initialized DB.
    """
    with conn:
        for stmt in _DDL_STATEMENTS:
            conn.execute(stmt)
        conn.execute(
            "INSERT INTO metadata(key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
