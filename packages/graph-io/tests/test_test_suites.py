"""Unit tests for test_suites.emit (TEST-01..07)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from graph_io import packages, store, structural_nodes, test_suites
from graph_io.uri import RepoContext

CTX = RepoContext(org="testorg", repo="testrepo")


# ---------- helpers ----------


def _setup(tmp_path: Path) -> sqlite3.Connection:
    return store.connect(tmp_path / "code.db", create=True)


def _run_emit_pipeline(conn: sqlite3.Connection, repo_root: Path) -> None:
    """Run packages.refresh + structural_nodes.emit + test_suites.emit
    inside a single transaction (mirrors update.run order)."""
    with store.transaction(conn):
        packages.refresh(conn, repo_root=repo_root, ctx=CTX)
        structural_nodes.emit(conn, repo_root=repo_root, ctx=CTX, skip_dirs=frozenset())
        test_suites.emit(conn, repo_root=repo_root, ctx=CTX, skip_dirs=frozenset())


def _write_pyproject(pkg_dir: Path, *, name: str | None = None, body: str = "") -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    n = name or pkg_dir.name
    (pkg_dir / "pyproject.toml").write_text(f'[project]\nname = "{n}"\n{body}\n')


def _write_python_pkg(pkg_dir: Path, importable: str) -> None:
    """Build a minimal src-layout Python package with an empty __init__.py."""
    src = pkg_dir / "src" / importable
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("")


def _write_package_json(pkg_dir: Path, data: dict) -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "package.json").write_text(json.dumps(data))


def _suite_rows(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    return [
        (r[0], r[1])
        for r in conn.execute(
            "SELECT name, path FROM nodes WHERE kind='test_suite' ORDER BY path"
        ).fetchall()
    ]


# ---------- Task 1 skeleton ----------


def test_test_suites_module_exposes_emit() -> None:
    """Plan 30-03 Task 1: public emit + private helpers exist + thresholds set."""
    assert callable(test_suites.emit)
    assert callable(test_suites._discover_test_roots)
    assert callable(test_suites._classify_suite_kind)
    assert test_suites._REPOSITORY_EDGE_THRESHOLD == 5


# ---------- Task 2: suite emission + re-parenting ----------


def _seed_root_pkg(tmp_path: Path) -> Path:
    """A root pyproject + a tests-only package so structural_nodes emits a
    Repository node even when no real Package files exist."""
    root_pkg = tmp_path / "rootpkg"
    _write_pyproject(root_pkg, name="rootpkg")
    _write_python_pkg(root_pkg, "rootpkg")
    return root_pkg


def test_repo_root_subdirs_become_suites(tmp_path: Path) -> None:
    """TEST-02: repo-root tests/<subdir>/ -> one TestSuite per subdir."""
    _seed_root_pkg(tmp_path)
    (tmp_path / "tests" / "integration").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "integration" / "test_foo.py").write_text("")
    (tmp_path / "tests" / "unit" / "test_bar.py").write_text("")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    rows = _suite_rows(conn)
    paths = {r[1] for r in rows}
    assert paths == {"tests/integration", "tests/unit"}


def test_repo_root_flat_tests_creates_single_suite(tmp_path: Path) -> None:
    """TEST-02: flat repo-root tests/ (no subdirs) -> a single suite named tests."""
    _seed_root_pkg(tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_only.py").write_text("")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    rows = _suite_rows(conn)
    assert rows == [("tests", "tests")]


def test_package_local_tests_dir_is_package_contained(tmp_path: Path) -> None:
    """TEST-03: <pkg>/tests/ creates a TestSuite contained by the Package."""
    pkg_dir = tmp_path / "packages" / "foo"
    _write_pyproject(pkg_dir, name="foo")
    _write_python_pkg(pkg_dir, "foo")
    (pkg_dir / "tests").mkdir()
    (pkg_dir / "tests" / "test_bar.py").write_text("")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    rows = _suite_rows(conn)
    assert ("tests", "packages/foo/tests") in rows
    # Parent edge: Package(foo) -> TestSuite
    parent = conn.execute(
        """
        SELECT p.kind, p.name FROM edges e
        JOIN nodes p ON e.src = p.id
        JOIN nodes s ON e.dst = s.id
        WHERE s.kind='test_suite' AND s.path='packages/foo/tests'
              AND e.kind='physically_contains'
        """
    ).fetchone()
    assert parent is not None
    assert parent == ("package", "foo")


def test_jsts_underscores_tests_dir_same_as_c(tmp_path: Path) -> None:
    """TEST-03: <pkg>/__tests__/ for a JS Package creates a Package-contained suite."""
    pkg_dir = tmp_path / "packages" / "jspkg"
    _write_package_json(pkg_dir, {"name": "jspkg"})
    (pkg_dir / "__tests__").mkdir()
    (pkg_dir / "__tests__" / "index.test.js").write_text("")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    rows = _suite_rows(conn)
    assert ("__tests__", "packages/jspkg/__tests__") in rows


def test_test_file_re_parented_from_repository_to_suite(tmp_path: Path) -> None:
    """TEST-04: the only physically_contains parent of a test file is its
    TestSuite, not the Repository (Phase 29 placement is replaced)."""
    pkg_dir = tmp_path / "packages" / "foo"
    _write_pyproject(pkg_dir, name="foo")
    _write_python_pkg(pkg_dir, "foo")
    (pkg_dir / "tests").mkdir()
    test_path = "packages/foo/tests/test_bar.py"
    (tmp_path / test_path).write_text("")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    parents = conn.execute(
        """
        SELECT p.kind FROM edges e
        JOIN nodes p ON e.src = p.id
        JOIN nodes f ON e.dst = f.id
        WHERE f.kind='file' AND f.path=? AND e.kind='physically_contains'
        """,
        (test_path,),
    ).fetchall()
    parent_kinds = {r[0] for r in parents}
    assert parent_kinds == {"test_suite"}, (
        f"expected only TestSuite parent, got {parent_kinds}"
    )
