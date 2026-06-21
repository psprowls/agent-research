"""Unit tests for graph_io.resources.emit (architecture-resource-nodes Phase 1)."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from graph_io import packages, resources, store
from graph_io.uri import RepoContext

CTX = RepoContext(org="testorg", repo="testrepo")


def _write_pkg(root: Path, name: str) -> None:
    pkg_dir = root / "packages" / name
    src_dir = pkg_dir / "src" / name.replace("-", "_")
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("")
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.0.0"\nrequires-python = ">=3.11"\n'
        f'[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    )


def _setup(tmp_path: Path) -> sqlite3.Connection:
    conn = store.connect(tmp_path / "code.db", create=True)
    return conn


def _refresh_packages(conn: sqlite3.Connection, repo_root: Path) -> None:
    with store.transaction(conn):
        packages.refresh(conn, repo_root=repo_root, ctx=CTX)


def _insert_dependency(conn: sqlite3.Connection, name: str) -> None:
    # Dependency nodes normally come from packages.refresh; insert directly so
    # the consumer-is-a-dependency test does not depend on manifest dep parsing.
    with conn:
        conn.execute(
            "INSERT INTO nodes (kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
            ("dependency", name, None, None, None, f"dependency:pypi/{name}"),
        )


def _count_kind(conn: sqlite3.Connection, kind: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM nodes WHERE kind=?", (kind,)).fetchone()[0]


def _count_edges(conn: sqlite3.Connection, kind: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM edges WHERE kind=?", (kind,)).fetchone()[0]


def _resource_attrs(conn: sqlite3.Connection, name: str) -> dict:
    # `uri` lives in the dedicated nodes.uri column (upsert pops it out of
    # attrs_json), so fold it back in for assertion convenience — mirrors how
    # domains nodes are read in test_domains.py.
    row = conn.execute("SELECT attrs_json, uri FROM nodes WHERE kind='resource' AND name=?", (name,)).fetchone()
    if not row:
        return {}
    attrs = json.loads(row[0]) if row[0] else {}
    if row[1] is not None:
        attrs["uri"] = row[1]
    return attrs


# ---------- empty / None ----------


def test_none_config_zero_resources(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mypkg")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    resources.emit(conn, resources_config=None, ctx=CTX)
    assert _count_kind(conn, "resource") == 0


def test_empty_config_zero_resources(tmp_path: Path) -> None:
    conn = _setup(tmp_path)
    resources.emit(conn, resources_config={}, ctx=CTX)
    assert _count_kind(conn, "resource") == 0


# ---------- internal resource: provides + consumes ----------


def test_internal_resource_edges_and_scope(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "location-aws-node-ts")
    _write_pkg(tmp_path, "location-data-node-ts")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    resources.emit(
        conn,
        resources_config={
            "location-service": {
                "resource_kind": "api",
                "description": "Location HTTP API",
                "provided_by": "location-aws-node-ts",
                "consumed_by": ["location-data-node-ts"],
            }
        },
        ctx=CTX,
    )
    assert _count_kind(conn, "resource") == 1
    assert _count_edges(conn, "provides") == 1
    assert _count_edges(conn, "consumes") == 1
    attrs = _resource_attrs(conn, "location-service")
    assert attrs["uri"] == "resource:testorg/testrepo/location-service"
    assert attrs["resource_kind"] == "api"
    assert attrs["description"] == "Location HTTP API"
    assert attrs["scope"] == "internal"  # derived: provided_by present


# ---------- external resource: consumers only, derived external ----------


def test_external_scope_derived(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "model-adapter")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    _insert_dependency(conn, "boto3")
    resources.emit(
        conn,
        resources_config={
            "aws-bedrock": {
                "resource_kind": "cloud_service",
                "provider": "aws",
                "consumed_by": ["model-adapter", "boto3"],
            }
        },
        ctx=CTX,
    )
    assert _resource_attrs(conn, "aws-bedrock")["scope"] == "external"
    assert _count_edges(conn, "consumes") == 2  # package + dependency
    assert _count_edges(conn, "provides") == 0
    # The dependency node is a consumes source.
    src_kinds = conn.execute(
        "SELECT n.kind FROM edges e JOIN nodes n ON e.src=n.id WHERE e.kind='consumes' ORDER BY n.kind"
    ).fetchall()
    assert ("dependency",) in src_kinds and ("package",) in src_kinds


def test_explicit_scope_override(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "p")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    resources.emit(
        conn,
        resources_config={"r": {"resource_kind": "api", "scope": "external", "provided_by": "p"}},
        ctx=CTX,
    )
    assert _resource_attrs(conn, "r")["scope"] == "external"  # explicit wins over derived internal


# ---------- typed dependency form ----------


def test_typed_dependency_form(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "mongodb")  # a package ALSO named mongodb (collision)
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    _insert_dependency(conn, "mongodb")
    resources.emit(
        conn,
        resources_config={"mongo-db-server": {"resource_kind": "database", "consumed_by": [{"dependency": "mongodb"}]}},
        ctx=CTX,
    )
    src = conn.execute("SELECT n.kind FROM edges e JOIN nodes n ON e.src=n.id WHERE e.kind='consumes'").fetchone()
    assert src == ("dependency",)  # typed form forced dependency, not the package


# ---------- orphan warn + skip ----------


def test_unknown_consumer_warned_and_skipped(tmp_path: Path, caplog) -> None:
    conn = _setup(tmp_path)
    with caplog.at_level(logging.WARNING, logger="graph_io.resources"):
        resources.emit(conn, resources_config={"r": {"resource_kind": "api", "consumed_by": ["ghost"]}}, ctx=CTX)
    assert _count_kind(conn, "resource") == 1  # node still emitted
    assert _count_edges(conn, "consumes") == 0  # edge skipped
    assert "ghost" in caplog.text


# ---------- idempotency ----------


def test_idempotent(tmp_path: Path) -> None:
    _write_pkg(tmp_path, "p")
    conn = _setup(tmp_path)
    _refresh_packages(conn, tmp_path)
    cfg = {"r": {"resource_kind": "api", "provided_by": "p", "consumed_by": ["p"]}}
    resources.emit(conn, resources_config=cfg, ctx=CTX)
    resources.emit(conn, resources_config=cfg, ctx=CTX)
    assert _count_kind(conn, "resource") == 1
    assert _count_edges(conn, "provides") == 1
    assert _count_edges(conn, "consumes") == 1
