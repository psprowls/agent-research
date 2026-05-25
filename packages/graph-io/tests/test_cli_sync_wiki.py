"""cg sync-wiki — end-to-end smoke against a tiny repo with a fake wiki layout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from _git_repo import init_repo, write_and_commit


def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "graph_io.cli.main", "--repo", str(cwd), "--mode", "test", *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def repo_with_wiki(tmp_path: Path) -> Path:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "src/a.py": "x = 1\n",
            "lattice/.lattice.yaml": "registered_plugins: []\n",
            "graph-wiki/wiki/packages/demo/demo.md": "# demo\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_sync_wiki_reports_newly_linked(repo_with_wiki: Path) -> None:
    res = _cg(["sync-wiki"], repo_with_wiki)
    assert res.returncode == 0, res.stderr
    assert "newly linked" in res.stdout
    assert "demo" in res.stdout
    assert "wiki/packages/demo/demo.md" in res.stdout


def test_sync_wiki_second_run_is_quiet(repo_with_wiki: Path) -> None:
    first = _cg(["sync-wiki"], repo_with_wiki)
    assert first.returncode == 0
    second = _cg(["sync-wiki"], repo_with_wiki)
    assert second.returncode == 0
    # The "newly linked" section header still prints, but with "(none)".
    newly_linked_section = second.stdout.split("undocumented")[0]
    assert "(none)" in newly_linked_section


def test_sync_wiki_reports_undocumented(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "lonely"\nversion = "0.1.0"\n',
            "src/a.py": "x = 1\n",
            "lattice/.lattice.yaml": "registered_plugins: []\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr

    res = _cg(["sync-wiki"], tmp_path)
    assert res.returncode == 0, res.stderr
    assert "lonely" in res.stdout
    assert "undocumented" in res.stdout


def test_sync_wiki_without_graph_returns_3(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "a.py": "x = 1\n",
            "graph-wiki/.graph-wiki.yaml": "registered_plugins: []\n",
        },
        "init",
    )

    res = _cg(["sync-wiki"], tmp_path)
    assert res.returncode == 3, res.stdout + res.stderr
