"""Unit tests for entry_points.emit (ENTRY-01..05)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from graph_io import entry_points, packages, store
from graph_io.uri import RepoContext

CTX = RepoContext(org="testorg", repo="testrepo")


# ---------- helpers ----------


def _setup_db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "code.db"
    return store.connect(db_path, create=True)


def _write_pyproject(
    pkg_dir: Path,
    *,
    name: str | None = None,
    scripts: dict[str, str] | None = None,
    entry_points_dict: dict[str, dict[str, str]] | None = None,
) -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    parts = ["[project]", f'name = "{name or pkg_dir.name}"']
    if scripts:
        parts.append("[project.scripts]")
        for k, v in scripts.items():
            parts.append(f'{k} = "{v}"')
    if entry_points_dict:
        for group, entries in entry_points_dict.items():
            parts.append(f'[project.entry-points."{group}"]')
            for k, v in entries.items():
                parts.append(f'{k} = "{v}"')
    (pkg_dir / "pyproject.toml").write_text("\n".join(parts) + "\n")


def _write_python_src(pkg_dir: Path, dotted: str, content: str = "def main(): pass\n") -> None:
    """Build src-layout file tree from a dotted module path.

    e.g. dotted='foo_pkg.cli' -> creates <pkg_dir>/src/foo_pkg/__init__.py
    and <pkg_dir>/src/foo_pkg/cli.py.
    """
    parts = dotted.split(".")
    src_root = pkg_dir / "src" / parts[0]
    src_root.mkdir(parents=True, exist_ok=True)
    (src_root / "__init__.py").write_text("")
    if len(parts) == 1:
        (src_root / "__init__.py").write_text(content)
        return
    inner = src_root
    for p in parts[1:-1]:
        inner = inner / p
        inner.mkdir(parents=True, exist_ok=True)
        (inner / "__init__.py").write_text("")
    (inner / f"{parts[-1]}.py").write_text(content)


def _write_package_json(pkg_dir: Path, data: dict) -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "package.json").write_text(json.dumps(data))


# ---------- Task 1: skeleton ----------


def test_entry_points_module_exposes_emit() -> None:
    """Plan 30-02 Task 1: public emit + private helpers exist and are callable."""
    assert callable(entry_points.emit)
    assert callable(entry_points._emit_pyproject_entries)
    assert callable(entry_points._emit_packagejson_entries)
    assert "import" in entry_points._EXPORT_CONDITION_KEYS


# ---------- Task 2: pyproject ----------


def _impl_target(conn: sqlite3.Connection, ep_name: str) -> str | None:
    row = conn.execute(
        """
        SELECT f.path FROM edges e
        JOIN nodes ep ON e.src = ep.id AND ep.kind='entry_point' AND ep.name=?
        JOIN nodes f  ON e.dst = f.id  AND f.kind='file'
        WHERE e.kind = 'implemented_by'
        """,
        (ep_name,),
    ).fetchone()
    return row[0] if row else None


def _declares_edge_exists(conn: sqlite3.Connection, pkg_name: str, ep_name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM edges e
        JOIN nodes p ON e.src = p.id AND p.kind='package' AND p.name=?
        JOIN nodes ep ON e.dst = ep.id AND ep.kind='entry_point' AND ep.name=?
        WHERE e.kind = 'declares_entry_point'
        """,
        (pkg_name, ep_name),
    ).fetchone()
    return row is not None


def test_pyproject_scripts_emits_entry_point(tmp_path: Path) -> None:
    """ENTRY-01: [project.scripts] foo-cli = 'foo_pkg.cli:main' resolves to a File."""
    pkg_dir = tmp_path / "packages" / "foo_pkg"
    _write_pyproject(pkg_dir, scripts={"foo-cli": "foo_pkg.cli:main"})
    _write_python_src(pkg_dir, "foo_pkg.cli")
    conn = _setup_db(tmp_path)
    packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    entry_points.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())

    row = conn.execute(
        "SELECT name, attrs_json FROM nodes WHERE kind='entry_point' AND name='foo-cli'"
    ).fetchone()
    assert row is not None, "EntryPoint(name='foo-cli') not emitted"
    attrs = json.loads(row[1])
    assert attrs["entry_kind"] == "executable"
    assert attrs["source"] == "pyproject.scripts"
    assert attrs["callable"] == "main"
    assert _declares_edge_exists(conn, "foo_pkg", "foo-cli")
    impl_path = _impl_target(conn, "foo-cli")
    assert impl_path is not None
    assert impl_path.endswith("packages/foo_pkg/src/foo_pkg/cli.py")


def test_pyproject_entry_points_console_scripts(tmp_path: Path) -> None:
    """ENTRY-01: [project.entry-points.console_scripts] is executable."""
    pkg_dir = tmp_path / "packages" / "bar_pkg"
    _write_pyproject(
        pkg_dir,
        entry_points_dict={"console_scripts": {"bar": "bar_pkg.cli:run"}},
    )
    _write_python_src(pkg_dir, "bar_pkg.cli")
    conn = _setup_db(tmp_path)
    packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    entry_points.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())

    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='entry_point' AND name='bar'"
    ).fetchone()
    assert row is not None
    attrs = json.loads(row[0])
    assert attrs["entry_kind"] == "executable"
    assert attrs["source"] == "pyproject.entry-points.console_scripts"
    assert attrs["callable"] == "run"
    assert _impl_target(conn, "bar") is not None


def test_pyproject_entry_points_library_group(tmp_path: Path) -> None:
    """ENTRY-01: Non-console_scripts entry-points groups produce library kind."""
    pkg_dir = tmp_path / "packages" / "myapp"
    _write_pyproject(
        pkg_dir,
        entry_points_dict={"myapp.plugins": {"jsonfmt": "myapp.formatters:json_fmt"}},
    )
    _write_python_src(pkg_dir, "myapp.formatters")
    conn = _setup_db(tmp_path)
    packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    entry_points.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())

    row = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='entry_point' AND name='jsonfmt'"
    ).fetchone()
    assert row is not None
    attrs = json.loads(row[0])
    assert attrs["entry_kind"] == "library"
    assert attrs["source"] == "pyproject.entry-points.myapp.plugins"
    assert attrs["callable"] == "json_fmt"


def test_implemented_by_null_on_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """D-06: declared entry whose target file is missing -> no implemented_by edge +
    stderr warning. cg update still succeeds."""
    pkg_dir = tmp_path / "packages" / "ghost"
    _write_pyproject(pkg_dir, scripts={"ghost-cli": "ghost.cli:main"})
    # NOTE: do not write the source — leave the target missing.
    (pkg_dir / "src" / "ghost").mkdir(parents=True)
    (pkg_dir / "src" / "ghost" / "__init__.py").write_text("")
    conn = _setup_db(tmp_path)
    packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    entry_points.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())

    row = conn.execute(
        "SELECT 1 FROM nodes WHERE kind='entry_point' AND name='ghost-cli'"
    ).fetchone()
    assert row is not None, "EntryPoint must still be emitted on miss"
    assert _impl_target(conn, "ghost-cli") is None
    captured = capsys.readouterr()
    assert "ghost-cli" in captured.err
    assert "cannot resolve implemented_by" in captured.err


def test_malformed_pyproject_does_not_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Defensive: malformed pyproject.toml inside a Package directory is skipped."""
    pkg_dir = tmp_path / "packages" / "okpkg"
    # Write a VALID manifest so packages.refresh sees this Package row first.
    _write_pyproject(pkg_dir, name="okpkg", scripts={"ok": "okpkg.cli:main"})
    _write_python_src(pkg_dir, "okpkg.cli")
    conn = _setup_db(tmp_path)
    packages.refresh(conn, repo_root=tmp_path, ctx=CTX)
    # Now corrupt the manifest before entry_points.emit reads it. We rewrite
    # in-place so the Package row remains but tomllib will fail.
    (pkg_dir / "pyproject.toml").write_text("not [valid toml [at all")
    entry_points.emit(conn, repo_root=tmp_path, ctx=CTX, skip_dirs=frozenset())

    # No EntryPoint emitted from the corrupted manifest.
    cnt = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='entry_point'"
    ).fetchone()[0]
    assert cnt == 0
    captured = capsys.readouterr()
    assert "failed to parse" in captured.err
    assert "pyproject.toml" in captured.err
