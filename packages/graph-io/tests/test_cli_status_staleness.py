"""cg status: fresh → 0; after new commit → 2; broken/no-init → 3/5."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _git_repo import init_repo, write_and_commit


def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "graph_io.cli.main", "--repo", str(cwd), "--mode", "test", *args],
        capture_output=True, text=True,
    )


def test_status_fresh_after_update(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    assert _cg(["update", "--full"], tmp_path).returncode == 0
    res = _cg(["status"], tmp_path)
    assert res.returncode == 0


def test_status_stale_after_new_commit(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    _cg(["update", "--full"], tmp_path)
    write_and_commit(tmp_path, {"b.py": "y = 2\n"}, "add b")
    res = _cg(["status"], tmp_path)
    assert res.returncode == 2


def test_status_json_shape(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    _cg(["update", "--full"], tmp_path)
    res = _cg(["--fmt", "json", "status"], tmp_path)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "last_indexed_commit" in data
    assert "head" in data
    assert "stale" in data
    assert "schema_version" in data
    assert "node_counts" in data
    assert "edge_counts" in data
    assert "languages_indexed" in data


def test_status_no_db_returns_3(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    res = _cg(["status"], tmp_path)
    assert res.returncode == 3


def test_status_outside_git_returns_5(tmp_path: Path) -> None:
    res = _cg(["status"], tmp_path)
    assert res.returncode == 5
