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
