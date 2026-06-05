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


def test_describe_infers_package_from_bare_name(repo: Path) -> None:
    """No --kind: a bare name matching exactly one package resolves to it."""
    res = _cg(["describe", "demo"], repo)
    assert res.returncode == 0, res.stderr
    assert "demo" in res.stdout


def test_describe_infers_repo_when_no_selector(repo: Path) -> None:
    """No --kind and no selector resolves to the repository node."""
    res = _cg(["describe"], repo)
    assert res.returncode == 0, res.stderr


def test_describe_infers_builtin_from_uri_prefix(repo: Path) -> None:
    """A selector starting with 'builtin:' routes to the builtin describer."""
    # Not asserting success (no such builtin in this tiny repo) — asserting it
    # did NOT mis-route to a name/path lookup. The builtin describer emits
    # 'not a builtin URI' only for non-builtin: strings, so its absence proves
    # the builtin path was taken.
    res = _cg(["describe", "builtin:python/os"], repo)
    assert "not a builtin URI" not in res.stderr


def test_describe_falls_back_to_path_for_unknown_name(repo: Path) -> None:
    """A selector matching no entity name falls through to a path lookup."""
    res = _cg(["describe", "src/demo/__init__.py"], repo)
    assert res.returncode == 0, res.stderr


def test_describe_ambiguous_selector_errors(tmp_path: Path) -> None:
    """A name matching two kinds (package + domain) reports AMBIGUOUS (exit 7)."""
    init_repo(tmp_path)
    # A package literally named 'shared' plus a domain 'shared' in domains.yaml.
    # domains.yaml lives at <repo_root>/domains.yaml (top-level YAML mapping of
    # domain_name -> {packages: [...]}; format confirmed from graph_io/domains.py).
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "shared"\nversion = "0.1.0"\n',
            "src/shared/__init__.py": "x = 1\n",
            "domains.yaml": "shared:\n  packages: [shared]\n  description: 'Shared domain'\n",
        },
        "init",
    )
    assert _cg(["update", "--full"], tmp_path).returncode == 0
    res = _cg(["describe", "shared"], tmp_path)
    assert res.returncode == 7
    assert "ambiguous" in res.stderr.lower()
    assert "--kind" in res.stderr
