"""Unit tests for wiki_io.entity_lookup — Bedrock-free graph lookups + the
URI→entity-filename mapping shared by run_ingest_source and the plugin prep
(Slice 4)."""

from __future__ import annotations

from pathlib import Path


def _seed_db(workspace: Path, packages, extra_nodes=None) -> Path:
    """Create <workspace>/.graph-wiki/code.db with package + optional extra nodes.

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
                    "INSERT INTO edges (src, dst, kind, attrs_json) VALUES (?, ?, 'contains', NULL)",
                    (pkg_id, file_id),
                )
        for kind, name, path, uri in extra_nodes or []:
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) VALUES (?, ?, ?, ?, NULL, NULL, ?)",
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


def test_lookup_entity_by_path_outside_repo_returns_none(tmp_path: Path) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_path

    rel = "packages/graph-io/src/graph_io/store.py"
    db = _seed_db(tmp_path, [("graph-io", "pkg:o/r/graph-io", rel)])
    conn = read_only_connect(db)
    try:
        # A path that is not under repo_root triggers the `except ValueError` branch.
        outside = tmp_path.parent / "elsewhere" / "store.py"
        result = lookup_entity_by_path(conn, tmp_path, outside)
    finally:
        conn.close()
    assert result is None


def test_lookup_entity_by_path_no_containing_package_returns_none(
    tmp_path: Path,
) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_path

    # Empty graph: no file/package nodes, so the join yields no row.
    db = _seed_db(tmp_path, [])
    conn = read_only_connect(db)
    try:
        result = lookup_entity_by_path(conn, tmp_path, tmp_path / "anything/file.py")
    finally:
        conn.close()
    assert result is None


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


def _seed_pkgdir_db(workspace, nodes, edges):
    """Seed code.db with arbitrary (id, kind, name, path, attrs_json, uri) node
    tuples and (src, dst, kind) edge tuples. Used for directory-resolution tests."""
    from graph_io.store import connect
    from workspace_io.paths import graph_dir

    db = graph_dir(workspace) / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db, create=True)
    try:
        for nid, kind, name, path, attrs_json, uri in nodes:
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) VALUES (?, ?, ?, ?, NULL, ?, ?)",
                (nid, kind, name, path, attrs_json, uri),
            )
        for src, dst, kind in edges:
            conn.execute(
                "INSERT INTO edges (src, dst, kind, attrs_json) VALUES (?, ?, ?, NULL)",
                (src, dst, kind),
            )
    finally:
        conn.close()
    return db


def test_lookup_package_by_dir_exact_match(tmp_path):
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_package_by_dir

    db = _seed_pkgdir_db(
        tmp_path,
        nodes=[
            (
                1,
                "package",
                "financial-tools-py",
                "domains/financial/financial-tools-py",
                None,
                "pkg:o/r/financial-tools-py",
            )
        ],
        edges=[],
    )
    conn = read_only_connect(db)
    try:
        result = lookup_package_by_dir(conn, tmp_path, tmp_path / "domains/financial/financial-tools-py")
    finally:
        conn.close()
    assert result == ("pkg:o/r/financial-tools-py", "financial-tools-py", 1)


def test_lookup_package_by_dir_nested_subdir_walks_to_enclosing(tmp_path):
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_package_by_dir

    db = _seed_pkgdir_db(
        tmp_path,
        nodes=[
            (
                1,
                "package",
                "financial-tools-py",
                "domains/financial/financial-tools-py",
                None,
                "pkg:o/r/financial-tools-py",
            )
        ],
        edges=[],
    )
    conn = read_only_connect(db)
    try:
        result = lookup_package_by_dir(conn, tmp_path, tmp_path / "domains/financial/financial-tools-py/src/sub")
    finally:
        conn.close()
    assert result == ("pkg:o/r/financial-tools-py", "financial-tools-py", 1)


def test_lookup_package_by_dir_app_kind(tmp_path):
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_package_by_dir

    db = _seed_pkgdir_db(
        tmp_path,
        nodes=[(1, "app", "app-electron-ts", "apps/app-electron-ts", None, "app:o/r/app-electron-ts")],
        edges=[],
    )
    conn = read_only_connect(db)
    try:
        result = lookup_package_by_dir(conn, tmp_path, tmp_path / "apps/app-electron-ts")
    finally:
        conn.close()
    assert result == ("app:o/r/app-electron-ts", "app-electron-ts", 1)


def test_lookup_package_by_dir_outside_repo_returns_none(tmp_path):
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_package_by_dir

    db = _seed_pkgdir_db(
        tmp_path,
        nodes=[(1, "package", "p", "packages/p", None, "pkg:o/r/p")],
        edges=[],
    )
    conn = read_only_connect(db)
    try:
        result = lookup_package_by_dir(conn, tmp_path, tmp_path.parent / "elsewhere/p")
    finally:
        conn.close()
    assert result is None


def test_lookup_package_by_dir_no_package_ancestor_returns_none(tmp_path):
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_package_by_dir

    db = _seed_pkgdir_db(
        tmp_path,
        nodes=[(1, "package", "p", "packages/p", None, "pkg:o/r/p")],
        edges=[],
    )
    conn = read_only_connect(db)
    try:
        result = lookup_package_by_dir(conn, tmp_path, tmp_path / "docs/notes")
    finally:
        conn.close()
    assert result is None


def test_files_in_package_returns_contained_file_rows(tmp_path):
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import files_in_package

    db = _seed_pkgdir_db(
        tmp_path,
        nodes=[
            (1, "package", "p", "packages/p", None, "pkg:o/r/p"),
            (2, "file", "a.py", "packages/p/a.py", '{"language": "python"}', None),
            (3, "file", "b.py", "packages/p/b.py", '{"language": "python"}', None),
            (4, "file", "outside.py", "packages/other/x.py", '{"language": "python"}', None),
        ],
        edges=[(1, 2, "contains"), (1, 3, "contains")],
    )
    conn = read_only_connect(db)
    try:
        rows = files_in_package(conn, 1)
    finally:
        conn.close()
    paths = sorted(r["path"] for r in rows)
    assert paths == ["packages/p/a.py", "packages/p/b.py"]
    # attrs_json is carried through for language derivation downstream.
    assert all("language" in (r["attrs_json"] or "") for r in rows)


def test_files_in_package_empty_when_no_files(tmp_path):
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import files_in_package

    db = _seed_pkgdir_db(
        tmp_path,
        nodes=[(1, "package", "p", "packages/p", None, "pkg:o/r/p")],
        edges=[],
    )
    conn = read_only_connect(db)
    try:
        rows = files_in_package(conn, 1)
    finally:
        conn.close()
    assert rows == []
