"""Post-upsert sweep: resolve placeholder-dst edges by joining (kind, name)."""

from __future__ import annotations

import json
import sqlite3


def _set_resolution(attrs_json: str | None, resolution: str) -> str:
    attrs: dict[str, object] = json.loads(attrs_json) if attrs_json else {}
    attrs["resolution"] = resolution
    return json.dumps(attrs, sort_keys=True)


def sweep(conn: sqlite3.Connection) -> None:
    """Resolve every edge whose dst points at a placeholder node (path IS NULL)."""
    placeholder_edges = conn.execute(
        "SELECT e.src, e.dst, e.kind, e.attrs_json, n.kind, n.name "
        "FROM edges e JOIN nodes n ON e.dst=n.id "
        "WHERE n.path IS NULL"
    ).fetchall()

    for src, old_dst, edge_kind, attrs_json, node_kind, node_name in placeholder_edges:
        matches = conn.execute(
            "SELECT id FROM nodes WHERE kind=? AND name=? AND path IS NOT NULL",
            (node_kind, node_name),
        ).fetchall()

        if not matches:
            new_attrs = _set_resolution(attrs_json, "unresolved")
            conn.execute(
                "UPDATE edges SET attrs_json=? WHERE src=? AND dst=? AND kind=?",
                (new_attrs, src, old_dst, edge_kind),
            )
            continue

        conn.execute(
            "DELETE FROM edges WHERE src=? AND dst=? AND kind=?",
            (src, old_dst, edge_kind),
        )
        resolution = "exact" if len(matches) == 1 else "ambiguous"
        for (real_dst,) in matches:
            new_attrs = _set_resolution(attrs_json, resolution)
            conn.execute(
                "INSERT INTO edges(src, dst, kind, attrs_json) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(src, dst, kind) DO UPDATE SET attrs_json=excluded.attrs_json",
                (src, real_dst, edge_kind, new_attrs),
            )

    # Delete placeholder nodes that were successfully resolved — their edges now point
    # at real nodes, so these stubs are unreferenced and would otherwise appear as
    # spurious path=None hits in `cg find` and similar queries.
    conn.execute(
        "DELETE FROM nodes WHERE path IS NULL AND kind != 'package' "
        "AND id NOT IN (SELECT dst FROM edges)"
    )
