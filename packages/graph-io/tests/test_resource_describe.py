"""describe surfacing for resource nodes + package provides/consumes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from graph_io import packages, queries, resources, store
from graph_io.uri import RepoContext

CTX = RepoContext(org="testorg", repo="testrepo")


def _write_pkg(root: Path, name: str) -> None:
    d = root / "packages" / name / "src" / name.replace("-", "_")
    d.mkdir(parents=True, exist_ok=True)
    (d / "__init__.py").write_text("")
    (root / "packages" / name / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.0.0"\nrequires-python = ">=3.11"\n'
        f'[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    )


def _build(tmp_path: Path) -> sqlite3.Connection:
    _write_pkg(tmp_path, "svc-pkg")
    _write_pkg(tmp_path, "client-pkg")
    conn = store.connect(tmp_path / "code.db", create=True)
    with store.transaction(conn):
        packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    resources.emit(
        conn,
        resources_config={"r": {"resource_kind": "api", "provided_by": "svc-pkg", "consumed_by": ["client-pkg"]}},
        ctx=CTX,
    )
    return conn


def _id(conn: sqlite3.Connection, kind: str, name: str) -> int:
    return conn.execute("SELECT id FROM nodes WHERE kind=? AND name=?", (kind, name)).fetchone()[0]


def test_describe_resource_lists_providers_and_consumers(tmp_path: Path) -> None:
    conn = _build(tmp_path)
    rows = queries._direct_children(conn, _id(conn, "resource", "r"), "resource")
    names = {r[5] for r in rows}
    assert {"svc-pkg", "client-pkg"} <= names


def test_describe_package_lists_resources(tmp_path: Path) -> None:
    conn = _build(tmp_path)
    rows = queries._direct_children(conn, _id(conn, "package", "client-pkg"), "package")
    assert "r" in {r[5] for r in rows if r[1] == "resource"}


def test_resource_is_leaf_depth(tmp_path: Path) -> None:
    assert queries.default_child_depth("resource") == 2
    assert "resource" not in queries._CONTAINER_KINDS
