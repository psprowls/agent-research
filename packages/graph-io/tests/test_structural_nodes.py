"""Structural nodes: Repository, SubPackage, File role flags (STRUCT-01..06)."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from pathlib import Path

import pytest
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import store, structural_nodes, upsert
from graph_io.uri import RepoContext

_CTX = RepoContext(org="test", repo="repo")


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


@pytest.fixture()
def patched_git(monkeypatch):
    """Stub graph_io.update._git to return canned output instead of running git."""
    def fake_git(args, *, cwd):
        joined = " ".join(args)
        if joined == "symbolic-ref --short refs/remotes/origin/HEAD":
            return "origin/main\n"
        if joined == "symbolic-ref --short HEAD":
            return "main\n"
        if joined == "remote get-url origin":
            return "git@github.com:test/repo.git\n"
        return ""

    monkeypatch.setattr(structural_nodes, "_git", fake_git)


def _seed_package(
    conn: sqlite3.Connection,
    name: str = "mypkg",
    path: str = "packages/mypkg",
    language: str = "python",
) -> None:
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[
                GraphNode(
                    kind="package",
                    name=name,
                    path=path,
                    line=None,
                    attrs={"uri": f"pkg:test/repo/{name}", "language": language},
                )
            ],
            edges=[],
        ),
    )


# ============================================================================
# A. Repository emission (D-01..D-03)
# ============================================================================


def test_emit_repository_node_single(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )
    rows = conn.execute("SELECT name, path, uri FROM nodes WHERE kind='repository'").fetchall()
    assert len(rows) == 1
    name, path, uri = rows[0]
    assert name == "repo"
    assert path is None
    assert uri == "repo:test/repo"


def test_emit_repository_path_is_null(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )
    row = conn.execute("SELECT path FROM nodes WHERE kind='repository'").fetchone()
    assert row[0] is None


def test_emit_repository_attrs_include_owner_name_url(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )
    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='repository'"
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs.get("owner") == "test"
    assert attrs.get("name") == "repo"
    assert "url" in attrs
    assert attrs.get("default_branch") == "main"


def test_emit_repository_default_branch_null_on_detached(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch
) -> None:
    from graph_io.update import NotInGitRepoError

    def fake_git(args, *, cwd):
        raise NotInGitRepoError("detached")

    monkeypatch.setattr(structural_nodes, "_git", fake_git)

    structural_nodes.emit(
        conn,
        repo_root=tmp_path,
        ctx=RepoContext(org="local", repo="x"),
        skip_dirs=frozenset(),
    )
    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='repository'"
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs.get("default_branch") is None


def test_emit_repository_local_mode_url_is_filesystem_path(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch
) -> None:
    from graph_io.update import NotInGitRepoError

    def fake_git(args, *, cwd):
        raise NotInGitRepoError("local")

    monkeypatch.setattr(structural_nodes, "_git", fake_git)

    structural_nodes.emit(
        conn,
        repo_root=tmp_path,
        ctx=RepoContext(org="local", repo=tmp_path.name),
        skip_dirs=frozenset(),
    )
    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='repository'"
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs.get("url") == str(tmp_path.absolute())


def test_emit_creates_repo_to_package_edge(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    _seed_package(conn, name="mypkg", path="packages/mypkg")
    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )
    rows = conn.execute(
        "SELECT n1.kind, n2.kind FROM edges e "
        "JOIN nodes n1 ON e.src=n1.id "
        "JOIN nodes n2 ON e.dst=n2.id "
        "WHERE e.kind='physically_contains' "
        "AND n2.kind='package'"
    ).fetchall()
    assert ("repository", "package") in rows


# ============================================================================
# B. Role-flag heuristics (D-09..D-12)
# ============================================================================


def test_is_test_path_directory_traversal() -> None:
    assert structural_nodes._is_test_path("tests/foo.py")
    assert structural_nodes._is_test_path("pkg/__tests__/x.py")
    assert structural_nodes._is_test_path("a/b/test/y.py")


def test_is_test_path_filename_patterns() -> None:
    assert structural_nodes._is_test_path("test_foo.py")
    assert structural_nodes._is_test_path("foo_test.py")
    assert structural_nodes._is_test_path("x.test.ts")
    assert structural_nodes._is_test_path("y.spec.js")
    assert structural_nodes._is_test_path("foo.test.tsx")
    assert structural_nodes._is_test_path("foo.spec.jsx")


def test_is_test_path_negative() -> None:
    assert not structural_nodes._is_test_path("src/foo.py")
    assert not structural_nodes._is_test_path("pkg/main.py")
    assert not structural_nodes._is_test_path("index.js")


def test_is_config_file_exact_names() -> None:
    assert structural_nodes._is_config_file("pyproject.toml")
    assert structural_nodes._is_config_file("package.json")
    assert structural_nodes._is_config_file("Makefile")
    assert structural_nodes._is_config_file("setup.cfg")


def test_is_config_file_globs() -> None:
    assert structural_nodes._is_config_file("vite.config.ts")
    assert structural_nodes._is_config_file("jest.config.js")
    assert structural_nodes._is_config_file("tsconfig.base.json")


def test_is_config_file_negative() -> None:
    assert not structural_nodes._is_config_file("foo.py")
    assert not structural_nodes._is_config_file("README.md")


def test_is_generated_filename_patterns(tmp_path: Path) -> None:
    fake = tmp_path / "foo_pb2.py"
    fake.write_text("DESCRIPTOR=None\n")
    assert structural_nodes._is_generated(fake, "foo_pb2.py")
    fake2 = tmp_path / "data.gen.ts"
    fake2.write_text("export {}\n")
    assert structural_nodes._is_generated(fake2, "data.gen.ts")


def test_is_generated_content_marker_at_generated(tmp_path: Path) -> None:
    f = tmp_path / "foo.py"
    f.write_text("# @generated by xyz\nx = 1\n")
    assert structural_nodes._is_generated(f, "foo.py")


def test_is_generated_content_marker_do_not_edit_case_insensitive(tmp_path: Path) -> None:
    f = tmp_path / "foo.py"
    f.write_text("# Do Not Edit -- machine generated\nx = 1\n")
    assert structural_nodes._is_generated(f, "foo.py")


def test_is_generated_skipped_above_1mb(tmp_path: Path) -> None:
    f = tmp_path / "big.py"
    f.write_text("# @generated by xyz\n" + ("x = 1\n" * 200_000))
    assert f.stat().st_size > 1_000_000
    assert not structural_nodes._is_generated(f, "big.py")


def test_is_generated_negative(tmp_path: Path) -> None:
    f = tmp_path / "foo.py"
    f.write_text("def public(): pass\n")
    assert not structural_nodes._is_generated(f, "foo.py")


def test_is_type_only_d_ts_and_pyi() -> None:
    assert structural_nodes._is_type_only("types.d.ts")
    assert structural_nodes._is_type_only("stubs.pyi")
    assert not structural_nodes._is_type_only("foo.ts")
    assert not structural_nodes._is_type_only("foo.py")


def test_is_executable_exec_bit(tmp_path: Path) -> None:
    f = tmp_path / "no_ext_script"
    f.write_text("hello\n")
    f.chmod(0o755)
    assert structural_nodes._is_executable(f, "no_ext_script")


def test_is_executable_shebang_only(tmp_path: Path) -> None:
    f = tmp_path / "run.sh"
    f.write_text("#!/bin/sh\necho hi\n")
    # explicitly NOT executable bit
    f.chmod(0o644)
    assert structural_nodes._is_executable(f, "run.sh")


def test_is_executable_negative(tmp_path: Path) -> None:
    f = tmp_path / "plain.py"
    f.write_text("x = 1\n")
    f.chmod(0o644)
    assert not structural_nodes._is_executable(f, "plain.py")


# ============================================================================
# C. SubPackage emission (D-04..D-08, D-18)
# ============================================================================


def test_subpackage_python_src_layout(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    # Set up a src-layout package
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    (src_root / "sub").mkdir()
    (src_root / "sub" / "__init__.py").write_text("")
    (src_root / "sub" / "deep").mkdir()
    (src_root / "sub" / "deep" / "__init__.py").write_text("")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    names = sorted(
        row[0]
        for row in conn.execute(
            "SELECT name FROM nodes WHERE kind='subpackage'"
        ).fetchall()
    )
    assert names == ["mypkg", "mypkg.sub", "mypkg.sub.deep"]


def test_subpackage_python_flat_layout(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    flat_root = pkg_dir / "mypkg"
    flat_root.mkdir(parents=True)
    (flat_root / "__init__.py").write_text("")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    names = sorted(
        row[0]
        for row in conn.execute(
            "SELECT name FROM nodes WHERE kind='subpackage'"
        ).fetchall()
    )
    assert names == ["mypkg"]


def test_subpackage_no_init_emits_none(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    pkg_dir.mkdir(parents=True)
    # No __init__.py anywhere — neither src nor flat layout

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    n = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='subpackage'"
    ).fetchone()[0]
    assert n == 0


def test_subpackage_jsts_package_emits_zero(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "jspkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "index.js").write_text("module.exports = {};")

    _seed_package(conn, name="jspkg", path="packages/jspkg", language="javascript")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    n = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='subpackage'"
    ).fetchone()[0]
    assert n == 0


def test_subpackage_dotted_path_includes_importable(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    (src_root / "cli").mkdir()
    (src_root / "cli" / "__init__.py").write_text("")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM nodes WHERE kind='subpackage'"
        ).fetchall()
    }
    assert "mypkg.cli" in names
    # NOT just "cli"
    assert "cli" not in names


def test_subpackage_parent_is_package_for_top_level(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    # The mypkg subpackage's parent should be a package node
    rows = conn.execute(
        "SELECT n_src.kind FROM edges e "
        "JOIN nodes n_src ON e.src = n_src.id "
        "JOIN nodes n_dst ON e.dst = n_dst.id "
        "WHERE e.kind='physically_contains' "
        "AND n_dst.kind='subpackage' AND n_dst.name='mypkg'"
    ).fetchall()
    assert rows == [("package",)]


def test_subpackage_parent_is_enclosing_subpackage_for_nested(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    (src_root / "sub").mkdir()
    (src_root / "sub" / "__init__.py").write_text("")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    rows = conn.execute(
        "SELECT n_src.kind, n_src.name FROM edges e "
        "JOIN nodes n_src ON e.src = n_src.id "
        "JOIN nodes n_dst ON e.dst = n_dst.id "
        "WHERE e.kind='physically_contains' "
        "AND n_dst.kind='subpackage' AND n_dst.name='mypkg.sub'"
    ).fetchall()
    assert rows == [("subpackage", "mypkg")]


# ============================================================================
# D. File emission with SPARSER read (D-13, D-14, D-20)
# ============================================================================


def test_file_python_reads_sparser_has_main(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    (src_root / "main.py").write_text(
        "def main(): pass\n\nif __name__ == '__main__':\n    main()\n"
    )

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")
    # Pre-seed source-parser attrs on the File node (as _process_files would)
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[
                GraphNode(
                    kind="file",
                    name="main.py",
                    path="packages/mypkg/src/mypkg/main.py",
                    line=None,
                    attrs={
                        "_has_main_block": True,
                        "_has_importable_symbols": True,
                        "language": "python",
                    },
                )
            ],
            edges=[],
        ),
    )

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='file' AND path=?",
        ("packages/mypkg/src/mypkg/main.py",),
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs.get("has_main") is True
    assert attrs.get("is_importable") is True


def test_file_python_defaults_when_sparser_attrs_missing(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    (src_root / "no_parse.py").write_text("# never parsed by source-parser\n")
    # No pre-seeded File node — sparser attrs are absent

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='file' AND path=?",
        ("packages/mypkg/src/mypkg/no_parse.py",),
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs.get("has_main") is False
    assert attrs.get("is_importable") is False


def test_file_jsts_default_has_main_false_is_importable_true(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "jspkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "index.js").write_text("module.exports = {};")

    _seed_package(conn, name="jspkg", path="packages/jspkg", language="javascript")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='file' AND path=?",
        ("packages/jspkg/index.js",),
    ).fetchone()
    attrs = json.loads(row[0])
    assert attrs.get("has_main") is False
    assert attrs.get("is_importable") is True


def test_test_file_parented_by_repository_not_package(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    test_dir = pkg_dir / "tests"
    test_dir.mkdir()
    (test_dir / "test_foo.py").write_text("def test_x(): pass\n")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    rows = conn.execute(
        "SELECT n_src.kind FROM edges e "
        "JOIN nodes n_src ON e.src=n_src.id "
        "JOIN nodes n_dst ON e.dst=n_dst.id "
        "WHERE e.kind='physically_contains' "
        "AND n_dst.kind='file' AND n_dst.path=?",
        ("packages/mypkg/tests/test_foo.py",),
    ).fetchall()
    parent_kinds = {r[0] for r in rows}
    assert parent_kinds == {"repository"}


def test_non_test_python_file_parented_by_subpackage(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    (src_root / "foo.py").write_text("def foo(): pass\n")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    rows = conn.execute(
        "SELECT n_src.kind, n_src.name FROM edges e "
        "JOIN nodes n_src ON e.src=n_src.id "
        "JOIN nodes n_dst ON e.dst=n_dst.id "
        "WHERE e.kind='physically_contains' "
        "AND n_dst.kind='file' AND n_dst.path=?",
        ("packages/mypkg/src/mypkg/foo.py",),
    ).fetchall()
    assert rows == [("subpackage", "mypkg")]


# ============================================================================
# E. Generic container exclusion (D-15)
# ============================================================================


def test_generic_container_dirs_never_emitted_as_nodes(
    conn: sqlite3.Connection, tmp_path: Path, patched_git
) -> None:
    pkg_dir = tmp_path / "packages" / "mypkg"
    src_root = pkg_dir / "src" / "mypkg"
    src_root.mkdir(parents=True)
    (src_root / "__init__.py").write_text("")
    (pkg_dir / "tests").mkdir()
    (pkg_dir / "tests" / "test_foo.py").write_text("def test_x(): pass\n")

    _seed_package(conn, name="mypkg", path="packages/mypkg", language="python")

    structural_nodes.emit(
        conn, repo_root=tmp_path, ctx=_CTX, skip_dirs=frozenset()
    )

    rows = conn.execute(
        "SELECT kind, name FROM nodes "
        "WHERE name IN ('packages', 'tests', 'libs', 'apps', 'shared', 'common')"
    ).fetchall()
    assert rows == []
