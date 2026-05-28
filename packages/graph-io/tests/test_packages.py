"""Manifest scanning: pyproject.toml + package.json → kind:package / kind:app nodes."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from graph_io import packages, store, upsert
from graph_io.uri import RepoContext
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords


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


def test_refresh_pyproject_stores_description(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """Phase 56 D-06/SCAN-02: pyproject [project].description lands in attrs_json."""
    pkg_dir = tmp_path / "packages" / "alpha"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "alpha"\nversion = "0.1.0"\n'
        'description = "A test package."\n'
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='package' AND name=?", ("alpha",)
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs["description"] == "A test package."


def test_refresh_pyproject_absent_description_is_empty(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """Phase 56 D-06: no [project].description -> empty string, not a placeholder."""
    pkg_dir = tmp_path / "packages" / "beta"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "beta"\nversion = "0.1.0"\n'
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='package' AND name=?", ("beta",)
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs["description"] == ""


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


# ============================================================================
# Phase 55 Plan 01 Task 2: workspace-name suppression (CLASS-01), the
# depends_on_package edge + retargeted used_by (CLASS-02 / D-04/D-06/D-07), and
# the external-dep regression.
# ============================================================================


def test_workspace_dep_suppressed_and_depends_on_package_emitted(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """CLASS-01 + CLASS-02 / D-02/D-04/D-07.

    `beta` declares workspace package `graph-io` (hyphen) whose own manifest
    name is `graph_io` (underscore) to exercise D-02 normalization, plus a
    genuine external dep `boto3`.
    """
    internal = tmp_path / "graph_io"
    internal.mkdir()
    (internal / "pyproject.toml").write_text(
        '[project]\nname = "graph_io"\nversion = "0.1.0"\n'
    )
    consumer = tmp_path / "beta"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        '[project]\nname = "beta"\nversion = "0.1.0"\n'
        'dependencies = ["graph-io>=0.1", "boto3>=1.38"]\n'
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    # CLASS-01: no `dependency` node for the normalized workspace name
    # (declared as `graph-io`, normalizes to `graph_io`).
    for candidate in ("graph_io", "graph-io"):
        count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE kind='dependency' AND name=?",
            (candidate,),
        ).fetchone()[0]
        assert count == 0, f"workspace dep should be suppressed, found {candidate!r}"

    # CLASS-01 regression: the external dep STILL has a `dependency` node + used_by.
    boto3_node = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='dependency' AND name='boto3'"
    ).fetchone()[0]
    assert boto3_node == 1
    boto3_used_by = conn.execute(
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes dep ON e.dst = dep.id "
        "WHERE e.kind='used_by' AND dep.kind='dependency' AND dep.name='boto3'"
    ).fetchone()[0]
    assert boto3_used_by == 1

    # CLASS-02 / D-04: exactly one depends_on_package edge, src=beta dst=graph_io,
    # both endpoints resolving to package/app nodes (never `dependency`).
    dop_rows = conn.execute(
        "SELECT src.kind, src.name, dst.kind, dst.name FROM edges e "
        "JOIN nodes src ON e.src = src.id "
        "JOIN nodes dst ON e.dst = dst.id "
        "WHERE e.kind='depends_on_package'"
    ).fetchall()
    assert len(dop_rows) == 1
    src_kind, src_name, dst_kind, dst_name = dop_rows[0]
    assert src_kind in ("package", "app") and src_name == "beta"
    assert dst_kind in ("package", "app") and dst_name == "graph_io"

    # CLASS-02 / D-07: the used_by edge for the internal pair points at the
    # package/app node, NOT a `dependency` node.
    internal_used_by = conn.execute(
        "SELECT dst.kind FROM edges e "
        "JOIN nodes src ON e.src = src.id "
        "JOIN nodes dst ON e.dst = dst.id "
        "WHERE e.kind='used_by' AND src.name='beta' AND dst.name='graph_io'"
    ).fetchall()
    assert len(internal_used_by) == 1
    assert internal_used_by[0][0] in ("package", "app")


def test_internal_dep_edges_dedupe_per_consumer(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-07 dedupe: an internal package declared in both [project.dependencies]
    and a [dependency-groups] group yields exactly ONE used_by and ONE
    depends_on_package edge for that pair.
    """
    internal = tmp_path / "alpha"
    internal.mkdir()
    (internal / "pyproject.toml").write_text(
        '[project]\nname = "alpha"\nversion = "0.1.0"\n'
    )
    consumer = tmp_path / "beta"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        '[project]\nname = "beta"\nversion = "0.1.0"\n'
        'dependencies = ["alpha>=0.1"]\n'
        '[dependency-groups]\ndev = ["alpha>=0.1"]\n'
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    used_by_count = conn.execute(
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes src ON e.src = src.id "
        "JOIN nodes dst ON e.dst = dst.id "
        "WHERE e.kind='used_by' AND src.name='beta' AND dst.name='alpha'"
    ).fetchone()[0]
    assert used_by_count == 1
    dop_count = conn.execute(
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes src ON e.src = src.id "
        "JOIN nodes dst ON e.dst = dst.id "
        "WHERE e.kind='depends_on_package' AND src.name='beta' AND dst.name='alpha'"
    ).fetchone()[0]
    assert dop_count == 1


def test_internal_dep_on_app_target_resolves_app_kind(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-07 stored-kind resolution: when the internal target is classified as an
    `app` (has [project.scripts]), both edges' dst resolve to kind='app'.
    """
    app_target = tmp_path / "mytool"
    app_target.mkdir()
    (app_target / "pyproject.toml").write_text(
        '[project]\nname = "mytool"\nversion = "0.1.0"\n'
        '[project.scripts]\nmytool = "mytool.cli:main"\n'
    )
    consumer = tmp_path / "beta"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        '[project]\nname = "beta"\nversion = "0.1.0"\n'
        'dependencies = ["mytool>=0.1"]\n'
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    for kind in ("used_by", "depends_on_package"):
        dst_kind = conn.execute(
            "SELECT dst.kind FROM edges e "
            "JOIN nodes src ON e.src = src.id "
            "JOIN nodes dst ON e.dst = dst.id "
            "WHERE e.kind=? AND src.name='beta' AND dst.name='mytool'",
            (kind,),
        ).fetchall()
        assert len(dst_kind) == 1, f"expected one {kind} edge to mytool"
        assert dst_kind[0][0] == "app", f"{kind} dst should resolve to app"


# ============================================================================
# Phase 50 Plan 01 Task 2: scripts_present / bin_present manifest reader fields.
# ============================================================================


def test_read_pyproject_scripts_present_true_when_section_nonempty(tmp_path: Path) -> None:
    """Phase 50 D-03: [project.scripts] with at least one entry → scripts_present=True."""
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        '[project]\n'
        'name = "alpha"\n'
        'version = "0.1.0"\n'
        '[project.scripts]\n'
        'alpha-cli = "alpha.cli:main"\n'
    )
    info = packages._read_pyproject(manifest)
    assert info is not None
    assert info["scripts_present"] is True
    # Legacy keys preserved.
    assert info["name"] == "alpha"
    assert info["version"] == "0.1.0"
    assert info["language"] == "python"
    assert info["dependencies"] == []
    assert info["dep_groups"] == {}


def test_read_pyproject_scripts_present_false_for_empty_or_missing(tmp_path: Path) -> None:
    """Phase 50 D-03: missing or empty [project.scripts] → scripts_present=False."""
    # Missing section.
    missing = tmp_path / "missing" / "pyproject.toml"
    missing.parent.mkdir()
    missing.write_text('[project]\nname = "alpha"\nversion = "0.1.0"\n')
    info_missing = packages._read_pyproject(missing)
    assert info_missing is not None
    assert info_missing["scripts_present"] is False

    # Empty table.
    empty = tmp_path / "empty" / "pyproject.toml"
    empty.parent.mkdir()
    empty.write_text(
        '[project]\nname = "beta"\nversion = "0.1.0"\n[project.scripts]\n'
    )
    info_empty = packages._read_pyproject(empty)
    assert info_empty is not None
    assert info_empty["scripts_present"] is False


def test_read_package_json_bin_present_for_string(tmp_path: Path) -> None:
    """Phase 50 D-03: bin as non-empty string → bin_present=True."""
    manifest = tmp_path / "package.json"
    manifest.write_text(
        json.dumps({"name": "myapp", "version": "1.0.0", "bin": "cli.js"})
    )
    info = packages._read_package_json(manifest)
    assert info is not None
    assert info["bin_present"] is True
    assert info["name"] == "myapp"
    assert info["language"] == "javascript"


def test_read_package_json_bin_present_for_dict(tmp_path: Path) -> None:
    """Phase 50 D-03: bin as dict with at least one truthy value → bin_present=True."""
    manifest = tmp_path / "package.json"
    manifest.write_text(
        json.dumps(
            {"name": "myapp", "version": "1.0.0", "bin": {"foo": "bin/foo.js"}}
        )
    )
    info = packages._read_package_json(manifest)
    assert info is not None
    assert info["bin_present"] is True


def test_read_package_json_bin_present_false_for_empty_dict(tmp_path: Path) -> None:
    """Phase 50 D-03: bin as empty dict → bin_present=False."""
    manifest = tmp_path / "package.json"
    manifest.write_text(
        json.dumps({"name": "myapp", "version": "1.0.0", "bin": {}})
    )
    info = packages._read_package_json(manifest)
    assert info is not None
    assert info["bin_present"] is False


def test_read_package_json_bin_present_false_when_missing(tmp_path: Path) -> None:
    """Phase 50 D-03: no bin key → bin_present=False."""
    manifest = tmp_path / "package.json"
    manifest.write_text(
        json.dumps({"name": "myapp", "version": "1.0.0"})
    )
    info = packages._read_package_json(manifest)
    assert info is not None
    assert info["bin_present"] is False
    # Legacy keys preserved.
    assert info["name"] == "myapp"
    assert info["version"] == "1.0.0"
    assert info["language"] == "javascript"
    assert info["dependencies"] == []


# ============================================================================
# Phase 50 Plan 02 Task 2: D-06 in-place UPDATE for cross-run kind flips.
# ============================================================================


def test_kind_flip_pkg_to_app(tmp_path: Path, conn: sqlite3.Connection) -> None:
    """D-06: package gaining [project.scripts] on re-run flips to app with id preserved."""
    pkg_dir = tmp_path / "myapp"
    pkg_dir.mkdir(parents=True)
    manifest = pkg_dir / "pyproject.toml"
    # First refresh: no scripts → kind="package".
    manifest.write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    row = conn.execute(
        "SELECT id, kind, uri FROM nodes WHERE name='myapp'"
    ).fetchone()
    assert row is not None, "first refresh did not create the row"
    pkg_id, pkg_kind, pkg_uri_val = row
    assert pkg_kind == "package"
    assert pkg_uri_val.startswith("pkg:")

    # Second refresh after adding [project.scripts] → expect kind flip to "app".
    manifest.write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
        '[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    rows = conn.execute(
        "SELECT id, kind, uri, attrs_json FROM nodes WHERE name='myapp'"
    ).fetchall()
    assert len(rows) == 1, f"expected exactly one row after flip; got {rows!r}"
    app_id, app_kind_db, app_uri_val, attrs_json = rows[0]
    assert app_id == pkg_id, "D-06: row id must be preserved across kind flip"
    assert app_kind_db == "app"
    assert app_uri_val.startswith("app:")
    attrs = json.loads(attrs_json)
    assert attrs["app_kind"] == "cli"
    assert attrs["app_signals"] == ["cli"]


def test_kind_flip_app_to_pkg_reverts(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-06: app losing [project.scripts] on re-run reverts to package with id preserved."""
    pkg_dir = tmp_path / "myapp"
    pkg_dir.mkdir(parents=True)
    manifest = pkg_dir / "pyproject.toml"
    # First refresh with scripts → kind="app".
    manifest.write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
        '[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    row = conn.execute(
        "SELECT id, kind FROM nodes WHERE name='myapp'"
    ).fetchone()
    assert row is not None
    app_id, app_kind_db = row
    assert app_kind_db == "app"

    # Remove [project.scripts] → expect revert to kind="package".
    manifest.write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    rows = conn.execute(
        "SELECT id, kind, uri, attrs_json FROM nodes WHERE name='myapp'"
    ).fetchall()
    assert len(rows) == 1, f"expected exactly one row after revert; got {rows!r}"
    pkg_id, pkg_kind_db, pkg_uri_val, attrs_json = rows[0]
    assert pkg_id == app_id, "D-06: row id must be preserved across kind revert"
    assert pkg_kind_db == "package"
    assert pkg_uri_val.startswith("pkg:")
    attrs = json.loads(attrs_json) if attrs_json else {}
    # D-03: Package rows MUST NOT carry app_kind / app_signals.
    assert "app_kind" not in attrs
    assert "app_signals" not in attrs


def test_kind_flip_preserves_inbound_edge_fk(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-06: inbound edges against the flipped row survive because dst id is preserved."""
    pkg_dir = tmp_path / "myapp"
    pkg_dir.mkdir(parents=True)
    manifest = pkg_dir / "pyproject.toml"
    manifest.write_text('[project]\nname = "myapp"\nversion = "0.1.0"\n')
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    pkg_row = conn.execute(
        "SELECT id FROM nodes WHERE name='myapp' AND kind='package'"
    ).fetchone()
    assert pkg_row is not None
    pkg_id = pkg_row[0]

    # Manually insert an inbound edge against the pkg row from a synthetic
    # domain node (use _upsert_edge to also create the src domain node).
    upsert._upsert_edge(
        conn,
        GraphEdge(
            src=("domain", "billing", None),
            dst=("package", "myapp", "myapp"),
            kind="belongs_to_domain",
            attrs={},
        ),
    )
    inbound_before = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE dst=?", (pkg_id,)
    ).fetchone()[0]
    assert inbound_before >= 1

    # Flip pkg → app.
    manifest.write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
        '[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    app_row = conn.execute(
        "SELECT id FROM nodes WHERE name='myapp' AND kind='app'"
    ).fetchone()
    assert app_row is not None
    assert app_row[0] == pkg_id, "row id must survive the flip"
    inbound_after = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE dst=?", (pkg_id,)
    ).fetchone()[0]
    assert inbound_after == inbound_before, (
        "D-06: inbound edges must survive the kind flip because dst FK is preserved"
    )


def test_no_kind_flip_for_zero_signal_manifest(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-06: zero-signal pure library re-run does not duplicate or flip the row."""
    pkg_dir = tmp_path / "purelib"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "purelib"\nversion = "0.1.0"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    rows_before = conn.execute(
        "SELECT id, kind, uri FROM nodes WHERE name='purelib'"
    ).fetchall()
    assert len(rows_before) == 1
    pkg_id, kind_before, uri_before = rows_before[0]
    assert kind_before == "package"

    # Re-run with identical manifest — no flip should occur.
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    rows_after = conn.execute(
        "SELECT id, kind, uri FROM nodes WHERE name='purelib'"
    ).fetchall()
    assert len(rows_after) == 1, "zero-signal re-run must not duplicate the row"
    assert rows_after[0] == (pkg_id, kind_before, uri_before)


# ============================================================================
# Phase 50 Plan 02 Task 3: JS-signal and multi-signal integration tests.
# ============================================================================


def _refresh_and_fetch(
    tmp_path: Path, conn: sqlite3.Connection, name: str
) -> tuple[str, str, dict]:
    """Run packages.refresh and return (kind, uri, attrs) for the named row."""
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    row = conn.execute(
        "SELECT kind, uri, attrs_json FROM nodes WHERE name=?", (name,)
    ).fetchone()
    assert row is not None, f"no row named {name!r} after refresh"
    return row[0], row[1], json.loads(row[2]) if row[2] else {}


def test_refresh_js_bin_string_classifies_app_cli(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-02: package.json bin as non-empty string → app/cli."""
    pkg_dir = tmp_path / "tool"
    pkg_dir.mkdir()
    (pkg_dir / "package.json").write_text(
        json.dumps({"name": "tool", "version": "1.0.0", "bin": "cli.js"})
    )
    kind, uri, attrs = _refresh_and_fetch(tmp_path, conn, "tool")
    assert kind == "app"
    assert uri.startswith("app:")
    assert attrs["app_kind"] == "cli"
    assert attrs["app_signals"] == ["cli"]


def test_refresh_js_bin_dict_classifies_app_cli(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-02: package.json bin as dict with truthy value → app/cli."""
    pkg_dir = tmp_path / "tool"
    pkg_dir.mkdir()
    (pkg_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "tool",
                "version": "1.0.0",
                "bin": {"foo": "bin/foo.js"},
            }
        )
    )
    kind, uri, attrs = _refresh_and_fetch(tmp_path, conn, "tool")
    assert kind == "app"
    assert uri.startswith("app:")
    assert attrs["app_kind"] == "cli"
    assert attrs["app_signals"] == ["cli"]


def test_refresh_js_next_classifies_app_nextjs(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-02: dependencies.next present → app/nextjs."""
    pkg_dir = tmp_path / "site"
    pkg_dir.mkdir()
    (pkg_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "site",
                "version": "1.0.0",
                "dependencies": {"next": "14", "react": "18"},
            }
        )
    )
    kind, uri, attrs = _refresh_and_fetch(tmp_path, conn, "site")
    assert kind == "app"
    assert uri.startswith("app:")
    assert attrs["app_kind"] == "nextjs"
    assert "nextjs" in attrs["app_signals"]


def test_refresh_js_expo_classifies_app_expo(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-02: dependencies.expo present → app/expo."""
    pkg_dir = tmp_path / "mobile"
    pkg_dir.mkdir()
    (pkg_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "mobile",
                "version": "1.0.0",
                "dependencies": {"expo": "50", "react-native": "0.73"},
            }
        )
    )
    kind, _uri, attrs = _refresh_and_fetch(tmp_path, conn, "mobile")
    assert kind == "app"
    assert attrs["app_kind"] == "expo"
    assert "expo" in attrs["app_signals"]


def test_refresh_js_vite_with_index_html_classifies_app_spa(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-02: vite dep AND index.html on disk → app/spa."""
    pkg_dir = tmp_path / "spa-app"
    pkg_dir.mkdir()
    (pkg_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "spa-app",
                "version": "1.0.0",
                "dependencies": {"vite": "5", "react": "18"},
            }
        )
    )
    (pkg_dir / "index.html").write_text("<!doctype html><html></html>")
    kind, _uri, attrs = _refresh_and_fetch(tmp_path, conn, "spa-app")
    assert kind == "app"
    assert attrs["app_kind"] == "spa"
    assert "spa" in attrs["app_signals"]


def test_refresh_js_vite_without_index_html_stays_package(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-03: vite dep WITHOUT index.html → no spa signal → stays package."""
    pkg_dir = tmp_path / "lib"
    pkg_dir.mkdir()
    (pkg_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "lib",
                "version": "1.0.0",
                "dependencies": {"vite": "5"},
            }
        )
    )
    kind, uri, attrs = _refresh_and_fetch(tmp_path, conn, "lib")
    assert kind == "package"
    assert uri.startswith("pkg:")
    assert "app_kind" not in attrs
    assert "app_signals" not in attrs


def test_refresh_js_multi_signal_nextjs_wins(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-04: multi-signal precedence — bin + next → app_kind=nextjs, sorted signals."""
    pkg_dir = tmp_path / "site"
    pkg_dir.mkdir()
    (pkg_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "site",
                "version": "1.0.0",
                "bin": "cli.js",
                "dependencies": {"next": "14"},
            }
        )
    )
    kind, _uri, attrs = _refresh_and_fetch(tmp_path, conn, "site")
    assert kind == "app"
    assert attrs["app_kind"] == "nextjs"
    assert attrs["app_signals"] == sorted(["cli", "nextjs"])


def test_refresh_python_pure_library_stays_package(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """D-03 / APP-03: pyproject without [project.scripts] → kind=package, no app keys."""
    pkg_dir = tmp_path / "purelib"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "purelib"\nversion = "0.1.0"\n'
    )
    kind, uri, attrs = _refresh_and_fetch(tmp_path, conn, "purelib")
    assert kind == "package"
    assert uri.startswith("pkg:")
    assert "app_kind" not in attrs
    assert "app_signals" not in attrs


def test_refresh_app_node_attrs_json_contains_app_kind_and_signals(
    tmp_path: Path, conn: sqlite3.Connection
) -> None:
    """app rows expose app_kind/app_signals via json_extract; package rows expose NULL."""
    # App: pyproject with scripts.
    app_dir = tmp_path / "myapp"
    app_dir.mkdir()
    (app_dir / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
        '[project.scripts]\nmyapp = "myapp.cli:main"\n'
    )
    # Package: pyproject without scripts.
    pkg_dir = tmp_path / "purelib"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "purelib"\nversion = "0.1.0"\n'
    )

    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)

    app_row = conn.execute(
        "SELECT json_extract(attrs_json, '$.app_kind'), "
        "       json_extract(attrs_json, '$.app_signals') "
        "FROM nodes WHERE name='myapp'"
    ).fetchone()
    assert app_row[0] == "cli"
    assert app_row[1] is not None

    pkg_row = conn.execute(
        "SELECT json_extract(attrs_json, '$.app_kind'), "
        "       json_extract(attrs_json, '$.app_signals') "
        "FROM nodes WHERE name='purelib'"
    ).fetchone()
    assert pkg_row[0] is None
    assert pkg_row[1] is None
