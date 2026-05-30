"""Post-upsert sweep: resolve placeholder-dst edges by joining (kind, name)."""

from __future__ import annotations

import json
import sqlite3

from graph_io._ignore import should_skip


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
    # D-16 / STRUCT-06: spare URI-bearing structural nodes (Repository,
    # Domain, TestSuite, EntryPoint) — they have no path but are not orphans.
    conn.execute(
        "DELETE FROM nodes WHERE path IS NULL AND uri IS NULL AND kind != 'package' "
        "AND id NOT IN (SELECT dst FROM edges)"
    )


def sweep_skip_dir_files(conn: sqlite3.Connection, skip_dirs: frozenset[str]) -> None:
    """Delete file nodes that are skip-dir build artifacts (uri IS NULL, path in skip-dir).

    Targets nodes with kind='file', uri IS NULL, path IS NOT NULL whose path has a
    component in skip_dirs (e.g. dist/, build/, node_modules/).  These are import-edge
    endpoints materialised by _ensure_node/_upsert_edge that bypassed the walk's skip-dir
    filter.  After deleting the file nodes, any edges left orphaned (src or dst no longer
    present) are removed.

    Scope is intentionally narrow: only kind='file' AND uri IS NULL AND skip-dir component.
    URI-bearing nodes, non-file nodes, and NULL-uri files outside skip-dirs are untouched.
    """
    candidates = conn.execute(
        "SELECT id, path FROM nodes WHERE kind = 'file' AND uri IS NULL AND path IS NOT NULL"
    ).fetchall()

    to_delete = [
        node_id
        for node_id, path in candidates
        if should_skip(path, skip_dirs)
    ]

    if not to_delete:
        return

    placeholders = ",".join("?" for _ in to_delete)
    conn.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", to_delete)

    # Remove edges orphaned by the node deletions (ON DELETE CASCADE is not
    # guaranteed to fire for all SQLite builds, so we do this explicitly).
    conn.execute(
        "DELETE FROM edges "
        "WHERE src NOT IN (SELECT id FROM nodes) OR dst NOT IN (SELECT id FROM nodes)"
    )
