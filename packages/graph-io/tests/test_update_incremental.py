"""Incremental update: only changed files re-parsed; D-status files deleted."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from workspace_io.config import resolve as resolve_workspace
from workspace_io.paths import graph_dir

from graph_io import update
from _git_repo import init_repo, remove_and_commit, write_and_commit


def _ro(repo: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{graph_dir(resolve_workspace(repo, False).workspace) / 'code.db'}?mode=ro", uri=True)


def test_incremental_picks_up_modified_file(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "def foo():\n    return 1\n"}, "init")
    update.run(tmp_path, full=True)

    head2 = write_and_commit(
        tmp_path,
        {"a.py": "def foo():\n    return 1\n\ndef bar():\n    return 2\n"},
        "add bar",
    )
    update.run(tmp_path, full=False)

    conn = _ro(tmp_path)
    try:
        names = {row[0] for row in conn.execute("SELECT name FROM nodes WHERE kind='function'").fetchall()}
        assert names == {"foo", "bar"}
        assert conn.execute("SELECT value FROM metadata WHERE key='last_indexed_commit'").fetchone() == (head2,)
    finally:
        conn.close()


def test_incremental_deletes_removed_file(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {"a.py": "def foo():\n    return 1\n", "b.py": "def bar():\n    return 2\n"},
        "init",
    )
    update.run(tmp_path, full=True)

    remove_and_commit(tmp_path, ["b.py"], "remove b")
    update.run(tmp_path, full=False)

    conn = _ro(tmp_path)
    try:
        names = {row[0] for row in conn.execute("SELECT name FROM nodes WHERE kind='function'").fetchall()}
        assert names == {"foo"}
        files = {row[0] for row in conn.execute("SELECT path FROM nodes WHERE kind='file'").fetchall()}
        assert files == {"a.py"}
    finally:
        conn.close()


def test_incremental_handles_rename(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "def foo():\n    return 1\n"}, "init")
    update.run(tmp_path, full=True)

    subprocess.run(["git", "mv", "a.py", "b.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "rename"], cwd=tmp_path, check=True)
    update.run(tmp_path, full=False)

    conn = _ro(tmp_path)
    try:
        files = {row[0] for row in conn.execute("SELECT path FROM nodes WHERE kind='file'").fetchall()}
        assert files == {"b.py"}
        rows = conn.execute(
            "SELECT path FROM nodes WHERE kind='function' AND name='foo'"
        ).fetchall()
        assert rows == [("b.py",)]
    finally:
        conn.close()
