"""Unit tests for test_suites.emit (TEST-01..07) + Plan 30-04 integration."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
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


# ---------- Task 3: tests edges ----------


def _tests_edge_targets(conn: sqlite3.Connection, suite_path: str) -> set[tuple[str, str | None]]:
    rows = conn.execute(
        """
        SELECT n.kind, n.name FROM edges e
        JOIN nodes s ON e.src = s.id
        JOIN nodes n ON e.dst = n.id
        WHERE e.kind='tests' AND s.kind='test_suite' AND s.path=?
        """,
        (suite_path,),
    ).fetchall()
    return {(r[0], r[1]) for r in rows}


def test_tests_edge_python_imports(tmp_path: Path) -> None:
    """D-09/D-10: Python test file 'from foo import bar' -> TestSuite -> Package(foo)."""
    foo_dir = tmp_path / "packages" / "foo"
    _write_pyproject(foo_dir, name="foo")
    _write_python_pkg(foo_dir, "foo")
    bar_dir = tmp_path / "packages" / "bar"
    _write_pyproject(bar_dir, name="bar")
    _write_python_pkg(bar_dir, "bar")

    (tmp_path / "tests" / "integration").mkdir(parents=True)
    (tmp_path / "tests" / "integration" / "test_x.py").write_text(
        "from foo import baz\nimport bar\n"
    )

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    targets = _tests_edge_targets(conn, "tests/integration")
    assert ("package", "foo") in targets
    assert ("package", "bar") in targets


def test_tests_edge_js_bare_imports(tmp_path: Path) -> None:
    """D-11: JS test 'import x from \"jspkg\"' -> TestSuite -> Package(jspkg)."""
    pkg_dir = tmp_path / "packages" / "jspkg"
    _write_package_json(pkg_dir, {"name": "jspkg"})
    other_dir = tmp_path / "packages" / "other"
    _write_package_json(other_dir, {"name": "other"})

    (pkg_dir / "__tests__").mkdir()
    (pkg_dir / "__tests__" / "index.test.js").write_text(
        'import { x } from "other";\n'
    )

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    targets = _tests_edge_targets(conn, "packages/jspkg/__tests__")
    assert ("package", "other") in targets


def test_tests_edge_js_relative_imports(tmp_path: Path) -> None:
    """D-11: JS test 'import x from \"../src/foo\"' -> TestSuite -> Package via _owning_package."""
    pkg_dir = tmp_path / "packages" / "jspkg"
    _write_package_json(pkg_dir, {"name": "jspkg"})
    (pkg_dir / "src").mkdir()
    (pkg_dir / "src" / "foo.js").write_text("export const x = 1;\n")

    (pkg_dir / "__tests__").mkdir()
    (pkg_dir / "__tests__" / "rel.test.js").write_text(
        'import { x } from "../src/foo";\n'
    )

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    targets = _tests_edge_targets(conn, "packages/jspkg/__tests__")
    assert ("package", "jspkg") in targets


def test_tests_edge_repository_threshold(tmp_path: Path) -> None:
    """D-12: a suite importing >=5 first-party packages gets an extra
    TestSuite -> Repository edge."""
    for n in ("p1", "p2", "p3", "p4", "p5"):
        pkg_dir = tmp_path / "packages" / n
        _write_pyproject(pkg_dir, name=n)
        _write_python_pkg(pkg_dir, n)

    (tmp_path / "tests" / "wide").mkdir(parents=True)
    (tmp_path / "tests" / "wide" / "test_x.py").write_text(
        "import p1\nimport p2\nimport p3\nimport p4\nimport p5\n"
    )

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    targets = _tests_edge_targets(conn, "tests/wide")
    pkg_targets = {t for t in targets if t[0] == "package"}
    assert len(pkg_targets) >= 5
    # Repository edge present
    assert any(t[0] == "repository" for t in targets), (
        f"expected Repository edge with >=5 pkg imports; targets={targets}"
    )


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


# ---------- Task 4: kind classification, config, malformed, idempotency ----------


def _suite_kind(conn: sqlite3.Connection, path: str) -> str:
    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='test_suite' AND path=?",
        (path,),
    ).fetchone()
    if row is None:
        return ""
    return json.loads(row[0])["suite_kind"]


def test_suite_kind_classification(tmp_path: Path) -> None:
    """D-17: dir-name precedence (integration/e2e/contract) then filename fallback."""
    _seed_root_pkg(tmp_path)
    cases = {
        "tests/integration": "test_a.py",
        "tests/e2e": "test_b.py",
        "tests/contract": "test_c.py",
        "tests/spec_files": "thing_spec.py",
        "tests/unit": "test_d.py",
        "tests/misc": "empty.txt",
    }
    for sub, fname in cases.items():
        (tmp_path / sub).mkdir(parents=True)
        (tmp_path / sub / fname).write_text("")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    assert _suite_kind(conn, "tests/integration") == "integration"
    assert _suite_kind(conn, "tests/e2e") == "e2e"
    assert _suite_kind(conn, "tests/contract") == "contract"
    assert _suite_kind(conn, "tests/spec_files") == "contract"
    assert _suite_kind(conn, "tests/unit") == "unit"
    assert _suite_kind(conn, "tests/misc") == "unknown"


def test_framework_config_testpaths_adds_root(tmp_path: Path) -> None:
    """D-18: pyproject [tool.pytest.ini_options] testpaths adds extra roots."""
    pkg_dir = tmp_path / "packages" / "foo"
    body = (
        '[tool.pytest.ini_options]\n'
        'testpaths = ["spec"]\n'
    )
    _write_pyproject(pkg_dir, name="foo", body=body)
    _write_python_pkg(pkg_dir, "foo")
    (pkg_dir / "spec").mkdir()
    (pkg_dir / "spec" / "test_x.py").write_text("")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)

    rows = _suite_rows(conn)
    assert any(p == "packages/foo/spec" for _, p in rows), (
        f"testpaths spec/ not discovered as suite root; rows={rows}"
    )


def test_malformed_pyproject_does_not_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """D-18: malformed config -> stderr warning + fall back to filesystem-only."""
    pkg_dir = tmp_path / "packages" / "foo"
    _write_pyproject(pkg_dir, name="foo")
    _write_python_pkg(pkg_dir, "foo")
    (pkg_dir / "tests").mkdir()
    (pkg_dir / "tests" / "test_x.py").write_text("")

    conn = _setup(tmp_path)
    # Run a clean pass first so packages.refresh writes the row.
    with store.transaction(conn):
        packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
        structural_nodes.emit(
            conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset()
        )
    # Now corrupt pyproject before test_suites.emit reads it for testpaths.
    (pkg_dir / "pyproject.toml").write_text("[tool.pytest.ini_options\nbad")
    with store.transaction(conn):
        test_suites.emit(
            conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset()
        )

    # Suite still discovered via conventional FS walk.
    rows = _suite_rows(conn)
    assert any(p == "packages/foo/tests" for _, p in rows)
    captured = capsys.readouterr()
    assert "malformed" in captured.err


def test_idempotency_two_runs_identical_edges(tmp_path: Path) -> None:
    """Re-running emit produces a byte-identical physically_contains + tests
    edge set."""
    pkg_dir = tmp_path / "packages" / "foo"
    _write_pyproject(pkg_dir, name="foo")
    _write_python_pkg(pkg_dir, "foo")
    (pkg_dir / "tests").mkdir()
    (pkg_dir / "tests" / "test_x.py").write_text("import foo\n")

    conn = _setup(tmp_path)
    _run_emit_pipeline(conn, tmp_path)
    snap1 = conn.execute(
        "SELECT src, dst, kind FROM edges WHERE kind IN ('physically_contains','tests') "
        "ORDER BY src, dst, kind"
    ).fetchall()

    # Second run inside a new transaction (emit() is independently invocable).
    with store.transaction(conn):
        test_suites.emit(
            conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset()
        )
    snap2 = conn.execute(
        "SELECT src, dst, kind FROM edges WHERE kind IN ('physically_contains','tests') "
        "ORDER BY src, dst, kind"
    ).fetchall()

    assert snap1 == snap2, (
        f"emit() not idempotent — first run {len(snap1)} edges, second {len(snap2)}"
    )


# ============================================================================
# Plan 30-04: integration + enforcement
# ============================================================================


def test_strict_tree_invariant_class_and_helper_exist() -> None:
    """Task 1: StrictTreeInvariantError + _enforce_strict_tree_invariant are
    importable from graph_io.update; the exception carries offending_child_ids
    and the D-20 hint message format."""
    from graph_io.update import StrictTreeInvariantError, _enforce_strict_tree_invariant

    assert callable(_enforce_strict_tree_invariant)
    e = StrictTreeInvariantError(offending_child_ids=[1, 2, 3])
    assert e.offending_child_ids == [1, 2, 3]
    msg = str(e)
    assert "tree invariant violated" in msg
    assert "3 node(s)" in msg
    assert "duplicate parent edge" in msg or "delete the prior edge" in msg


def test_update_run_calls_emitters_in_correct_order() -> None:
    """Task 2: update.run sources contains entry_points.emit + test_suites.emit +
    the invariant call in the required order (D-21)."""
    import inspect

    from graph_io import update

    src = inspect.getsource(update.run)
    assert "entry_points.emit" in src
    assert "test_suites.emit" in src
    assert "_enforce_strict_tree_invariant" in src

    i_struct = src.index("structural_nodes.emit")
    i_entry = src.index("entry_points.emit")
    i_test = src.index("test_suites.emit")
    i_resolve = src.index("resolve.sweep")
    i_inv = src.index("_enforce_strict_tree_invariant")
    assert i_struct < i_entry < i_test < i_resolve < i_inv, (
        f"wrong order in update.run: struct={i_struct} entry={i_entry} "
        f"test={i_test} resolve={i_resolve} inv={i_inv}"
    )
