"""Idle re-run is a no-op: counts unchanged, last_indexed_commit stable."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from workspace_io.config import resolve as resolve_workspace
from workspace_io.paths import graph_dir

from graph_io import update
from _git_repo import init_repo, write_and_commit


def _ro(repo: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{graph_dir(resolve_workspace(repo, False).workspace) / 'code.db'}?mode=ro", uri=True)


def test_idle_rerun_is_noop(tmp_path: Path) -> None:
    init_repo(tmp_path)
    head = write_and_commit(tmp_path, {"a.py": "def foo():\n    return 1\n"}, "init")
    update.run(tmp_path, full=True)

    conn = _ro(tmp_path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    finally:
        conn.close()

    update.run(tmp_path, full=False)

    conn = _ro(tmp_path)
    try:
        after = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        assert after == before
        assert conn.execute("SELECT value FROM metadata WHERE key='last_indexed_commit'").fetchone() == (head,)
    finally:
        conn.close()
