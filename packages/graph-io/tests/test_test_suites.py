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
