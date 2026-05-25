"""Full update: tiny multi-file git repo → populated DB."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from workspace_io.config import resolve as resolve_workspace
from workspace_io.paths import graph_dir

from graph_io import update
from _git_repo import init_repo, write_and_commit


def _open_ro(repo: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{graph_dir(resolve_workspace(repo, False).workspace) / 'code.db'}?mode=ro", uri=True)


def test_update_full_populates_db(tmp_path: Path) -> None:
    init_repo(tmp_path)
    head = write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "src/a.py": "def foo():\n    return 1\n",
            "src/b.py": "from .a import foo\n\ndef bar():\n    return foo()\n",
        },
        "init",
    )

    update.run(tmp_path, full=True)

    conn = _open_ro(tmp_path)
    try:
        kinds = {row[0] for row in conn.execute("SELECT DISTINCT kind FROM nodes").fetchall()}
        assert {"file", "function", "package"} <= kinds
        names = {row[0] for row in conn.execute("SELECT name FROM nodes WHERE kind='function'").fetchall()}
        assert {"foo", "bar"} <= names
        last = conn.execute("SELECT value FROM metadata WHERE key='last_indexed_commit'").fetchone()
        assert last == (head,)
    finally:
        conn.close()


def test_update_writes_gitignore(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")

    update.run(tmp_path, full=True)

    gitignore = (graph_dir(resolve_workspace(tmp_path, False).workspace) / ".gitignore").read_text()
    assert "code.db" in gitignore
    assert "code.db-wal" in gitignore
    assert "code.db-shm" in gitignore


def test_update_raises_outside_git(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(update.NotInGitRepoError):
        update.run(tmp_path, full=True)


def test_update_skips_default_skip_dirs(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "src/a.py": "def keep_me():\n    return 1\n",
            "dist/junk.py": "def skip_me():\n    return 2\n",
        },
        "init",
    )

    update.run(tmp_path, full=True)

    conn = _open_ro(tmp_path)
    try:
        names = {row[0] for row in conn.execute(
            "SELECT name FROM nodes WHERE kind='function'"
        ).fetchall()}
        assert "keep_me" in names
        assert "skip_me" not in names

        paths = {row[0] for row in conn.execute(
            "SELECT path FROM nodes WHERE kind='file'"
        ).fetchall()}
        assert "src/a.py" in paths
        assert "dist/junk.py" not in paths
    finally:
        conn.close()


def test_update_honors_cgignore(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            ".cgignore": "generated\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "src/a.py": "def keep_me():\n    return 1\n",
            "generated/auto.py": "def skip_me():\n    return 2\n",
        },
        "init",
    )

    update.run(tmp_path, full=True)

    conn = _open_ro(tmp_path)
    try:
        names = {row[0] for row in conn.execute(
            "SELECT name FROM nodes WHERE kind='function'"
        ).fetchall()}
        assert "keep_me" in names
        assert "skip_me" not in names
    finally:
        conn.close()
