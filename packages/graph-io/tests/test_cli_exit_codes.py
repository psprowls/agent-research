"""Pin every documented exit code so script consumers can rely on them."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from _git_repo import init_repo, write_and_commit


def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "graph_io.cli.main", "--repo", str(cwd), "--mode", "test", *args],
        capture_output=True, text=True,
    )


def test_exit_0_success(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    assert _cg(["update", "--full"], tmp_path).returncode == 0


def test_exit_1_generic_describe_unknown_package(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    _cg(["update", "--full"], tmp_path)
    res = _cg(["describe-package", "no-such-package"], tmp_path)
    assert res.returncode == 1
    assert "not found" in res.stderr


def test_exit_2_stale(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    _cg(["update", "--full"], tmp_path)
    write_and_commit(tmp_path, {"b.py": "y = 2\n"}, "second")
    res = _cg(["status"], tmp_path)
    assert res.returncode == 2


def test_exit_3_not_initialized(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    res = _cg(["status"], tmp_path)
    assert res.returncode == 3


def test_exit_5_not_in_git_repo(tmp_path: Path) -> None:
    res = _cg(["update"], tmp_path)
    assert res.returncode == 5


def test_exit_4_schema_mismatch(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    _cg(["update", "--full"], tmp_path)

    db = tmp_path / "graph-wiki" / ".graph" / "code.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO metadata(key, value) VALUES ('schema_version', '999') "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
        )

    for argv in (
        ["status"],
        ["dump"],
        ["find", "x"],
        ["callers", "x"],
        ["callees", "x"],
        ["imports", "a.py"],
        ["imported-by", "a.py"],
        ["exports", "a.py"],
        ["exported-by", "x"],
        ["describe-package", "anything"],
        ["describe-path", "a.py"],
    ):
        res = _cg(argv, tmp_path)
        assert res.returncode == 4, (argv, res.stdout, res.stderr)
        assert "schema" in res.stderr.lower()


def test_exit_6_update_in_progress(tmp_path: Path) -> None:
    import os
    import time

    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    
    # Initialize the DB
    assert _cg(["update", "--full"], tmp_path).returncode == 0

    # Strict-mode CLI invocation below requires a workspace manifest.
    (tmp_path / "graph-wiki" / ".graph-wiki.yaml").write_text(
        "version: 2\n"
        "initialized_at: '2026-05-25'\n"
        "plugins:\n"
        "- name: graph-wiki-agent\n"
        "  installed_version: 0.1.0\n"
        "  applied_version: 0.1.0\n"
    )

    db = tmp_path / "graph-wiki" / ".graph" / "code.db"
    locker = sqlite3.connect(db)
    locker.isolation_level = None  # manual transaction control
    locker.execute("BEGIN EXCLUSIVE")
    try:
        write_and_commit(tmp_path, {"b.py": "y = 2\n"}, "second")
        env = {**os.environ, "LATTICE_GRAPH_LOCK_TIMEOUT_MS": "200"}
        started = time.monotonic()
        res = subprocess.run(
            [sys.executable, "-m", "graph_io.cli.main",
             "--repo", str(tmp_path), "update"],
            capture_output=True, text=True, env=env,
        )
        elapsed_ms = (time.monotonic() - started) * 1000
    finally:
        locker.execute("ROLLBACK")
        locker.close()

    assert res.returncode == 6, (res.stdout, res.stderr)
    assert "in progress" in res.stderr.lower()
    assert elapsed_ms < 5_000, f"update waited {elapsed_ms:.0f}ms — busy_timeout not honored"
