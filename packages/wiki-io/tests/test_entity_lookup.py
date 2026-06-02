from __future__ import annotations

"""Unit tests for wiki_io.entity_lookup — Bedrock-free graph lookups + the
URI→entity-filename mapping shared by run_ingest_source and the plugin prep
(Slice 4)."""

from pathlib import Path

import pytest


def _seed_db(workspace: Path, packages, extra_nodes=None) -> Path:
    """Create <workspace>/.graph/code.db with package + optional extra nodes.

    `packages`: list of (name, uri, rel_file_path | None).
    `extra_nodes`: list of (kind, name, path | None, uri | None).
    URI is written to the dedicated nodes.uri column.
    """
    from graph_io.store import connect
    from workspace_io.paths import graph_dir

    db = graph_dir(workspace) / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db, create=True)
    try:
        nid = 1
        for name, uri, rel_path in packages:
            pkg_id = nid
            nid += 1
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                "VALUES (?, 'package', ?, NULL, NULL, NULL, ?)",
                (pkg_id, name, uri),
            )
            if rel_path is not None:
                file_id = nid
                nid += 1
                conn.execute(
                    "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                    "VALUES (?, 'file', ?, ?, NULL, NULL, NULL)",
                    (file_id, Path(rel_path).name, rel_path),
                )
                conn.execute(
                    "INSERT INTO edges (src, dst, kind, attrs_json) "
                    "VALUES (?, ?, 'contains', NULL)",
                    (pkg_id, file_id),
                )
        for kind, name, path, uri in extra_nodes or []:
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                "VALUES (?, ?, ?, ?, NULL, NULL, ?)",
                (nid, kind, name, path, uri),
            )
            nid += 1
    finally:
        conn.close()
    return db


def test_lookup_entity_by_path_returns_uri_and_name(tmp_path: Path) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_path

    rel = "packages/graph-io/src/graph_io/store.py"
    db = _seed_db(tmp_path, [("graph-io", "pkg:o/r/graph-io", rel)])
    conn = read_only_connect(db)
    try:
        result = lookup_entity_by_path(conn, tmp_path, tmp_path / rel)
    finally:
        conn.close()
    assert result == ("pkg:o/r/graph-io", "graph-io")


def test_lookup_entity_by_name_unique_match(tmp_path: Path) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_name

    db = _seed_db(tmp_path, [("graph-io", "pkg:o/r/graph-io", None)])
    conn = read_only_connect(db)
    try:
        result = lookup_entity_by_name(conn, "graph-io")
    finally:
        conn.close()
    assert result == ("pkg:o/r/graph-io", "graph-io")


def test_lookup_entity_by_name_multi_match_returns_none(tmp_path: Path) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_name

    db = _seed_db(
        tmp_path,
        [],
        extra_nodes=[
            ("class", "Helper", "a/helper.py", "cls:o/a/Helper"),
            ("class", "Helper", "b/helper.py", "cls:o/b/Helper"),
        ],
    )
    conn = read_only_connect(db)
    try:
        result = lookup_entity_by_name(conn, "Helper")
    finally:
        conn.close()
    assert result is None


def test_entity_filename_for_uri_package_matches_short_filename() -> None:
    from wiki_io.entity_lookup import entity_filename_for_uri
    from wiki_io.entity_writer import short_filename

    uri = "pkg:o/r/graph-io"
    assert entity_filename_for_uri(uri) == short_filename(uri, frozenset())
    assert entity_filename_for_uri(uri) == "pkg_graph-io"


def test_entity_filename_for_uri_non_entity_prefix_returns_none() -> None:
    from wiki_io.entity_lookup import entity_filename_for_uri

    # cls:/fn:/method: have no entity page → no wikilink target.
    assert entity_filename_for_uri("cls:subagent_runtime.pool.SubagentPool") is None
    assert entity_filename_for_uri("") is None
