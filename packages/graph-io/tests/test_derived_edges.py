"""Unit + end-to-end tests for graph_io.derived_edges (Phase 31 DERIVED-01..04)."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from workspace_io.config import resolve as resolve_workspace
from workspace_io.paths import graph_dir

from graph_io import (
    derived_edges,
    domains,
    packages,
    store,
    structural_nodes,
    update,
)
from graph_io.uri import RepoContext

from _git_repo import init_repo, write_and_commit

CTX = RepoContext(org="testorg", repo="testrepo")

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_monorepo"


# ---------- helpers ----------


def _setup(tmp_path: Path) -> sqlite3.Connection:
    conn = store.connect(tmp_path / "code.db", create=True)
    return conn


def _write_pkg_py(root: Path, name: str, files: dict[str, str]) -> None:
    pkg_dir = root / "packages" / name
    importable = name.replace("-", "_")
    src_dir = pkg_dir / "src" / importable
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "__init__.py").write_text("")
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.0.0"\n'
        f'requires-python = ">=3.11"\n'
        f'[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    )
    for rel, content in files.items():
        (pkg_dir / rel).parent.mkdir(parents=True, exist_ok=True)
        (pkg_dir / rel).write_text(content)


def _emit_phase_29(conn: sqlite3.Connection, root: Path) -> None:
    with store.transaction(conn):
        packages.refresh(conn, repo_root=root, ctx=CTX)
        structural_nodes.emit(
            conn, repo_root=root, ctx=CTX, skip_dirs=frozenset(),
        )


def _two_domain_setup(tmp_path: Path) -> sqlite3.Connection:
    _write_pkg_py(tmp_path, "pkg-a", {
        "src/pkg_a/foo.py": "from pkg_b import bar\n",
    })
    _write_pkg_py(tmp_path, "pkg-b", {
        "src/pkg_b/__init__.py": "",
        "src/pkg_b/bar.py": "x = 1\n",
    })
    (tmp_path / "domains.yaml").write_text(
        "D:\n  packages: [pkg-a]\n"
        "E:\n  packages: [pkg-b]\n"
    )
    conn = _setup(tmp_path)
    _emit_phase_29(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    derived_edges.compute(conn, repo_root=tmp_path, ctx=CTX)
    return conn


# ---------- (a) references emitted ----------


def test_references_emitted(tmp_path: Path) -> None:
    conn = _two_domain_setup(tmp_path)
    row = conn.execute(
        "SELECT e.attrs_json FROM edges e "
        "JOIN nodes src ON e.src=src.id "
        "JOIN nodes dst ON e.dst=dst.id "
        "WHERE e.kind='references' AND src.name='D' AND dst.name='pkg-b'"
    ).fetchone()
    assert row is not None
    attrs = json.loads(row[0]) if row[0] else {}
    assert attrs.get("usage_count") == 1


# ---------- (b) depends_on emitted ----------


def test_depends_on_emitted(tmp_path: Path) -> None:
    conn = _two_domain_setup(tmp_path)
    row = conn.execute(
        "SELECT e.attrs_json FROM edges e "
        "JOIN nodes src ON e.src=src.id "
        "JOIN nodes dst ON e.dst=dst.id "
        "WHERE e.kind='depends_on' AND src.name='D' AND dst.name='E'"
    ).fetchone()
    assert row is not None
    attrs = json.loads(row[0]) if row[0] else {}
    assert attrs.get("usage_count") == 1


# ---------- no self-loops ----------


def test_no_self_loops_in_depends_on(tmp_path: Path) -> None:
    # pkg-a in domain D imports pkg-a-helper (also in D)
    _write_pkg_py(tmp_path, "pkg-a", {
        "src/pkg_a/foo.py": "from pkg_a_helper import x\n",
    })
    _write_pkg_py(tmp_path, "pkg-a-helper", {
        "src/pkg_a_helper/__init__.py": "x = 1\n",
    })
    (tmp_path / "domains.yaml").write_text(
        "D:\n  packages: [pkg-a, pkg-a-helper]\n"
    )
    conn = _setup(tmp_path)
    _emit_phase_29(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    derived_edges.compute(conn, repo_root=tmp_path, ctx=CTX)
    # D -> D depends_on must NOT exist (D-09)
    count = conn.execute(
        "SELECT COUNT(*) FROM edges e JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='depends_on' AND s.name='D' AND d.name='D'"
    ).fetchone()[0]
    assert count == 0
    # Intra-domain references also must NOT exist (D-08)
    count = conn.execute(
        "SELECT COUNT(*) FROM edges e JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='references' AND s.name='D' AND d.name='pkg-a-helper'"
    ).fetchone()[0]
    assert count == 0


# ---------- (c) idempotency ----------


def test_idempotency(tmp_path: Path) -> None:
    conn = _two_domain_setup(tmp_path)
    edges_first = sorted(conn.execute(
        "SELECT src, dst, kind FROM edges WHERE kind IN ('references', 'depends_on')"
    ).fetchall())
    derived_edges.compute(conn, repo_root=tmp_path, ctx=CTX)
    edges_second = sorted(conn.execute(
        "SELECT src, dst, kind FROM edges WHERE kind IN ('references', 'depends_on')"
    ).fetchall())
    assert edges_first == edges_second


# ---------- (d) no transitive storage ----------


def test_no_transitive_storage(tmp_path: Path) -> None:
    # parent contains child; child has pkg-a importing pkg-x in OUTSIDE
    _write_pkg_py(tmp_path, "pkg-a", {
        "src/pkg_a/foo.py": "from pkg_x import y\n",
    })
    _write_pkg_py(tmp_path, "pkg-x", {
        "src/pkg_x/__init__.py": "y = 1\n",
    })
    (tmp_path / "domains.yaml").write_text(
        "parent:\n  packages: []\n"
        "child:\n  packages: [pkg-a]\n  parent: parent\n"
        "outside:\n  packages: [pkg-x]\n"
    )
    conn = _setup(tmp_path)
    _emit_phase_29(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    derived_edges.compute(conn, repo_root=tmp_path, ctx=CTX)
    # references edge exists from child -> pkg-x
    row = conn.execute(
        "SELECT 1 FROM edges e JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='references' AND s.name='child' AND d.name='pkg-x'"
    ).fetchone()
    assert row is not None
    # references edge MUST NOT exist from parent -> pkg-x (no transitive bubble-up at compute time, DERIVED-04)
    row = conn.execute(
        "SELECT 1 FROM edges e JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='references' AND s.name='parent' AND d.name='pkg-x'"
    ).fetchone()
    assert row is None


# ---------- TestSuite -> Domain helpers ----------


def _seed_testsuite(
    conn: sqlite3.Connection,
    suite_name: str,
    suite_path: str | None,
    pkg_keys: list[tuple[str, str | None]],
) -> None:
    """Insert a TestSuite node + tests edges directly (bypassing Phase 30
    for testing isolation)."""
    conn.execute(
        "INSERT OR IGNORE INTO nodes(kind, name, path) VALUES (?, ?, ?)",
        ("test_suite", suite_name, suite_path),
    )
    for pkg_name, pkg_path in pkg_keys:
        suite_id = conn.execute(
            "SELECT id FROM nodes WHERE kind='test_suite' AND name=?",
            (suite_name,),
        ).fetchone()[0]
        if pkg_path is None:
            pkg_id = conn.execute(
                "SELECT id FROM nodes WHERE kind='package' AND name=? AND path IS NULL",
                (pkg_name,),
            ).fetchone()[0]
        else:
            pkg_id = conn.execute(
                "SELECT id FROM nodes WHERE kind='package' AND name=? AND path=?",
                (pkg_name, pkg_path),
            ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO edges(src, dst, kind, attrs_json) "
            "VALUES (?, ?, 'tests', NULL)",
            (suite_id, pkg_id),
        )


# ---------- (e) TestSuite -> Domain emitted when all in one Domain ----------


def test_testsuite_domain_emitted(tmp_path: Path) -> None:
    _write_pkg_py(tmp_path, "pkg-a", {})
    _write_pkg_py(tmp_path, "pkg-b", {})
    (tmp_path / "domains.yaml").write_text(
        "D:\n  packages: [pkg-a, pkg-b]\n"
    )
    conn = _setup(tmp_path)
    _emit_phase_29(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    _seed_testsuite(conn, "integration", "tests/integration",
                    [("pkg-a", "packages/pkg-a"),
                     ("pkg-b", "packages/pkg-b")])
    derived_edges.compute(conn, repo_root=tmp_path, ctx=CTX)
    row = conn.execute(
        "SELECT 1 FROM edges e JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='tests' AND s.name='integration' AND d.kind='domain' AND d.name='D'"
    ).fetchone()
    assert row is not None


# ---------- (f) TestSuite -> Domain NOT emitted for multi-domain span ----------


def test_testsuite_no_domain_on_multi_domain_span(tmp_path: Path) -> None:
    _write_pkg_py(tmp_path, "pkg-a", {})
    _write_pkg_py(tmp_path, "pkg-b", {})
    (tmp_path / "domains.yaml").write_text(
        "D:\n  packages: [pkg-a]\n"
        "E:\n  packages: [pkg-b]\n"
    )
    conn = _setup(tmp_path)
    _emit_phase_29(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    _seed_testsuite(conn, "integration", "tests/integration",
                    [("pkg-a", "packages/pkg-a"),
                     ("pkg-b", "packages/pkg-b")])
    derived_edges.compute(conn, repo_root=tmp_path, ctx=CTX)
    row = conn.execute(
        "SELECT 1 FROM edges e JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='tests' AND s.name='integration' AND d.kind='domain'"
    ).fetchone()
    assert row is None


# ---------- (g) TestSuite -> Domain NOT emitted for single-package suite ----------


def test_testsuite_no_domain_for_single_package_suite(tmp_path: Path) -> None:
    _write_pkg_py(tmp_path, "pkg-a", {})
    (tmp_path / "domains.yaml").write_text(
        "D:\n  packages: [pkg-a]\n"
    )
    conn = _setup(tmp_path)
    _emit_phase_29(conn, tmp_path)
    domains.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())
    _seed_testsuite(conn, "unit", "tests/unit",
                    [("pkg-a", "packages/pkg-a")])
    derived_edges.compute(conn, repo_root=tmp_path, ctx=CTX)
    row = conn.execute(
        "SELECT 1 FROM edges e JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='tests' AND s.name='unit' AND d.kind='domain'"
    ).fetchone()
    assert row is None


# ---------- (h) end-to-end update.run on sample_monorepo fixture ----------


def test_update_run_end_to_end(tmp_path: Path) -> None:
    # Copy sample_monorepo into a git repo, run update.run twice.
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_ROOT, repo)
    init_repo(repo)
    # write_and_commit handles git add + commit; here all fixture files
    # already exist, so add them all in one commit:
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    update.run(repo, full=True)

    ws = resolve_workspace(repo, require_manifest=False).workspace
    db_path = graph_dir(ws) / "code.db"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        # 3 Domain nodes
        count = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE kind='domain'"
        ).fetchone()[0]
        assert count == 3
        # belongs_to_domain edges
        count = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE kind='belongs_to_domain'"
        ).fetchone()[0]
        assert count >= 2   # mypkg -> core, jspkg -> web
        # domain_contains_domain edge presentation -> web
        row = conn.execute(
            "SELECT 1 FROM edges e JOIN nodes s ON e.src=s.id "
            "JOIN nodes d ON e.dst=d.id "
            "WHERE e.kind='domain_contains_domain' AND s.name='presentation' AND d.name='web'"
        ).fetchone()
        assert row is not None
        edges_first = sorted(conn.execute(
            "SELECT src, dst, kind FROM edges"
        ).fetchall())
    finally:
        conn.close()
    # SC#3: second update.run produces unchanged edges
    update.run(repo, full=False)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        edges_second = sorted(conn.execute(
            "SELECT src, dst, kind FROM edges"
        ).fetchall())
    finally:
        conn.close()
    assert edges_first == edges_second
