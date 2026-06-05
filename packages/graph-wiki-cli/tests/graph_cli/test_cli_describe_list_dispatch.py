"""gw graph describe/list dispatcher behavior (router + inference)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ._git_repo import init_repo, write_and_commit


def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "graph_wiki_cli.graph_cli.main", "--repo", str(cwd), "--mode", "test", *args],
        capture_output=True, text=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.1"\n',
            "src/demo/__init__.py": "__all__ = ['delta']\n\ndef delta():\n    return 1\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_describe_package_explicit_kind(repo: Path) -> None:
    res = _cg(["describe", "demo", "--kind", "package"], repo)
    assert res.returncode == 0, res.stderr
    assert "demo" in res.stdout


def test_describe_package_explicit_kind_json(repo: Path) -> None:
    res = _cg(["--fmt", "json", "describe", "demo", "--kind", "package"], repo)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["name"] == "demo"


def test_describe_unknown_kind_is_bad_parameter(repo: Path) -> None:
    res = _cg(["describe", "demo", "--kind", "wombat"], repo)
    assert res.returncode == 2
    assert "kind must be one of" in res.stderr


def test_describe_repo_explicit_kind_no_selector(repo: Path) -> None:
    res = _cg(["describe", "--kind", "repo"], repo)
    assert res.returncode == 0, res.stderr
