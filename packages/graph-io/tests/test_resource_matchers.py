"""Unit tests for graph_io.resource_matchers.compute_suggestions (Phase 2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from graph_io import packages, resource_matchers, store
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


def _setup(tmp_path: Path) -> sqlite3.Connection:
    _write_pkg(tmp_path, "model-adapter")
    conn = store.connect(tmp_path / "code.db", create=True)
    with store.transaction(conn):
        packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    return conn


def _node_id(conn: sqlite3.Connection, kind: str, name: str) -> int:
    return conn.execute("SELECT id FROM nodes WHERE kind=? AND name=?", (kind, name)).fetchone()[0]


def _insert_node(
    conn: sqlite3.Connection, kind: str, name: str, path: str | None = None, uri: str | None = None
) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO nodes (kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
            (kind, name, path, None, None, uri),
        )
    return cur.lastrowid


def _insert_edge(conn: sqlite3.Connection, src: int, dst: int, kind: str) -> None:
    with conn:
        conn.execute("INSERT INTO edges (src, dst, kind, attrs_json) VALUES (?,?,?,?)", (src, dst, kind, None))


def test_consumer_depends_on_rule(tmp_path: Path) -> None:
    conn = _setup(tmp_path)
    dep_id = _insert_node(conn, "dependency", "boto3", uri="dependency:pypi/boto3")
    _insert_edge(conn, _node_id(conn, "package", "model-adapter"), dep_id, "used_by")
    matchers = [
        {
            "name": "boto3-clients",
            "when": {"consumer_depends_on": "boto3"},
            "emit": {"resource": "aws", "resource_kind": "cloud_service", "scope": "external", "role": "consumes"},
        }
    ]
    sugg = resource_matchers.compute_suggestions(conn, matchers)
    assert len(sugg) == 1
    s = sugg[0]
    assert s.resource == "aws" and s.role == "consumes" and s.source_name == "model-adapter"
    assert s.resource_kind == "cloud_service" and s.scope == "external"


def test_package_glob_has_file_rule(tmp_path: Path) -> None:
    conn = _setup(tmp_path)
    aws_id = _insert_node(conn, "package", "location-aws-node-ts", path="packages/location-aws-node-ts")
    file_id = _insert_node(
        conn, "file", "location-service.ts", path="packages/location-aws-node-ts/cdk/location-service.ts"
    )
    _insert_edge(conn, aws_id, file_id, "physically_contains")
    matchers = [
        {
            "name": "aws-cdk-service",
            "when": {"package_glob": "*-aws-node-ts", "has_file": "cdk/*.ts"},
            "emit": {"resource_kind": "api", "scope": "internal", "role": "provides"},
        }
    ]
    sugg = resource_matchers.compute_suggestions(conn, matchers)
    keys = {(s.resource, s.role, s.source_name) for s in sugg}
    assert ("location-service", "provides", "location-aws-node-ts") in keys


def test_dedupe(tmp_path: Path) -> None:
    conn = _setup(tmp_path)
    dep_id = _insert_node(conn, "dependency", "boto3", uri="dependency:pypi/boto3")
    _insert_edge(conn, _node_id(conn, "package", "model-adapter"), dep_id, "used_by")
    rule = {"name": "r", "when": {"consumer_depends_on": "boto3"}, "emit": {"resource": "aws", "role": "consumes"}}
    sugg = resource_matchers.compute_suggestions(conn, [rule, rule])
    assert len(sugg) == 1  # deduped on (resource, role, source_name)
