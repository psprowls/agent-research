"""Manifest scanning: pyproject.toml + package.json → kind:package nodes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from graph_io import packages, store, upsert
from graph_io.uri import RepoContext
from source_parser.projections.graph import GraphNode, GraphRecords


_CTX = RepoContext(org="test", repo="repo")


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def _seed_file_node(conn: sqlite3.Connection, path: str) -> None:
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[GraphNode(kind="file", name=path, path=path, line=None, attrs={})],
            edges=[],
        ),
    )


def test_refresh_pyproject(tmp_path: Path, conn: sqlite3.Connection) -> None:
    pkg_dir = tmp_path / "packages" / "alpha"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "alpha"\nversion = "0.1.0"\ndependencies = ["beta"]\n'
    )
    _seed_file_node(conn, "packages/alpha/src/a.py")

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    row = conn.execute(
        "SELECT name, attrs_json FROM nodes WHERE kind='package'"
    ).fetchone()
    assert row[0] == "alpha"
    attrs = json.loads(row[1])
    assert attrs["version"] == "0.1.0"
    assert attrs["dependencies"] == ["beta"]
    assert attrs["language"] == "python"


def test_refresh_package_json(tmp_path: Path, conn: sqlite3.Connection) -> None:
    pkg_dir = tmp_path / "frontend"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(
        json.dumps({"name": "frontend", "version": "1.0.0", "dependencies": {"x": "1"}})
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    row = conn.execute(
        "SELECT name, attrs_json FROM nodes WHERE kind='package'"
    ).fetchone()
    assert row[0] == "frontend"
    attrs = json.loads(row[1])
    assert attrs["language"] == "javascript"
    assert attrs["dependencies"] == ["x"]


def test_refresh_creates_contains_edges(tmp_path: Path, conn: sqlite3.Connection) -> None:
    pkg_dir = tmp_path / "alpha"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text('[project]\nname = "alpha"\nversion = "0.1.0"\n')
    _seed_file_node(conn, "alpha/src/a.py")
    _seed_file_node(conn, "alpha/src/b.py")
    _seed_file_node(conn, "outside/c.py")

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    rows = conn.execute(
        "SELECT n2.name FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id "
        "JOIN nodes n2 ON e.dst=n2.id "
        "WHERE n1.kind='package' AND n1.name='alpha' AND e.kind='contains'"
    ).fetchall()
    file_names = {row[0] for row in rows}
    assert file_names == {"alpha/src/a.py", "alpha/src/b.py"}


def test_refresh_skips_venv_manifests(tmp_path: Path, conn: sqlite3.Connection) -> None:
    venv_pkg = tmp_path / ".venv" / "lib" / "python3.12" / "site-packages" / "foo"
    venv_pkg.mkdir(parents=True)
    (venv_pkg / "pyproject.toml").write_text('[project]\nname = "foo"\nversion = "0.0.0"\n')

    real_pkg = tmp_path / "pkg"
    real_pkg.mkdir(parents=True)
    (real_pkg / "pyproject.toml").write_text('[project]\nname = "real-pkg"\nversion = "0.1.0"\n')

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    rows = conn.execute("SELECT name FROM nodes WHERE kind='package'").fetchall()
    names = {row[0] for row in rows}
    assert names == {"real-pkg"}
    assert "foo" not in names


def test_refresh_skips_cgignore_manifests(tmp_path: Path, conn: sqlite3.Connection) -> None:
    (tmp_path / ".cgignore").write_text("generated\n")

    generated_pkg = tmp_path / "packages" / "generated" / "fake"
    generated_pkg.mkdir(parents=True)
    (generated_pkg / "pyproject.toml").write_text('[project]\nname = "fake"\nversion = "0.0.0"\n')

    real_pkg = tmp_path / "packages" / "real"
    real_pkg.mkdir(parents=True)
    (real_pkg / "pyproject.toml").write_text('[project]\nname = "real"\nversion = "0.1.0"\n')

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    names = {row[0] for row in conn.execute("SELECT name FROM nodes WHERE kind='package'").fetchall()}
    assert names == {"real"}
    assert "fake" not in names


def test_refresh_skips_broken_pyproject(tmp_path: Path, conn: sqlite3.Connection, capsys) -> None:
    pkg_dir = tmp_path / "alpha"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text("not valid toml [[[[")

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    captured = capsys.readouterr()
    assert "alpha" in captured.err or "pyproject.toml" in captured.err
    count = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='package'").fetchone()[0]
    assert count == 0


def test_refresh_writes_pkg_uri_on_package_nodes(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """SC#1: every Package node has a non-NULL pkg:org/repo/name uri."""
    pkg_dir = tmp_path / "foo_pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text('[project]\nname = "foo"\nversion = "0.1.0"\n')

    packages.refresh(conn, repo_root=tmp_path, ctx=RepoContext("myorg", "myrepo"))

    row = conn.execute(
        "SELECT uri, attrs_json FROM nodes WHERE kind='package' AND name='foo'"
    ).fetchone()
    assert row is not None
    uri, attrs_json = row
    assert uri == "pkg:myorg/myrepo/foo"
    # PITFALL 4 lock: uri must NOT leak into attrs_json.
    if attrs_json is not None:
        assert "uri" not in json.loads(attrs_json)


# ============================================================================
# Phase 43 Plan 01 Task 2: dependency ingestion from [project.dependencies] +
# [dependency-groups], with used_by edges.
# ============================================================================


import pytest as _pytest


@_pytest.mark.parametrize(
    "spec, expected",
    [
        ("boto3>=1.38", "boto3"),
        ("langchain-aws[bedrock]>=1.4.6", "langchain-aws"),
        ("foo; python_version >= '3.11'", "foo"),
        ("foo", "foo"),
        ("Foo", "foo"),
        ("", None),
        ("git+https://example.com/x#egg=mypkg", None),
    ],
)
def test_pep_508_name_extraction(spec: str, expected: str | None) -> None:
    assert packages._extract_dep_name(spec) == expected


def test_dependency_ingestion_from_workspace(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """D-02: refresh emits dependency nodes + used_by edges across all manifests."""
    pkg_a = tmp_path / "pkg-a"
    pkg_a.mkdir()
    (pkg_a / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\nversion = "0.1.0"\n'
        'dependencies = ["boto3>=1.38", "langchain-aws>=1.4"]\n'
    )
    pkg_b = tmp_path / "pkg-b"
    pkg_b.mkdir()
    (pkg_b / "pyproject.toml").write_text(
        '[project]\nname = "pkg-b"\nversion = "0.1.0"\n'
        'dependencies = ["boto3==1.40.0"]\n'
        '[dependency-groups]\ndev = ["pytest>=8"]\n'
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    # 3 distinct deps emitted as nodes: boto3, langchain-aws, pytest
    dep_rows = conn.execute(
        "SELECT name, attrs_json, uri FROM nodes WHERE kind='dependency' ORDER BY name"
    ).fetchall()
    names = [r[0] for r in dep_rows]
    assert names == ["boto3", "langchain-aws", "pytest"]
    # boto3 attrs.versions_in_use collects both PEP 508 strings (sorted)
    boto3_row = dep_rows[0]
    boto3_attrs = json.loads(boto3_row[1])
    assert boto3_attrs["ecosystem"] == "pypi"
    assert boto3_attrs["versions_in_use"] == sorted(
        ["boto3>=1.38", "boto3==1.40.0"]
    )
    assert boto3_row[2] == "dependency:pypi/boto3"
    # used_by edges from both consumer packages to boto3
    boto3_used_by = conn.execute(
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes dep ON e.dst = dep.id "
        "WHERE e.kind='used_by' AND dep.kind='dependency' AND dep.name='boto3'"
    ).fetchone()[0]
    assert boto3_used_by == 2
    pytest_used_by = conn.execute(
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes dep ON e.dst = dep.id "
        "WHERE e.kind='used_by' AND dep.kind='dependency' AND dep.name='pytest'"
    ).fetchone()[0]
    assert pytest_used_by == 1


def test_used_by_edge_dedupes_per_consumer(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """A dep listed in both [project.dependencies] and [dependency-groups] for the
    same consumer produces exactly ONE used_by edge from that consumer to that dep.
    """
    pkg_c = tmp_path / "pkg-c"
    pkg_c.mkdir()
    (pkg_c / "pyproject.toml").write_text(
        '[project]\nname = "pkg-c"\nversion = "0.1.0"\n'
        'dependencies = ["boto3>=1.38"]\n'
        '[dependency-groups]\nextra = ["boto3>=1.40"]\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    count = conn.execute(
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes src ON e.src = src.id "
        "JOIN nodes dst ON e.dst = dst.id "
        "WHERE e.kind='used_by' AND src.name='pkg-c' AND dst.name='boto3'"
    ).fetchone()[0]
    assert count == 1
