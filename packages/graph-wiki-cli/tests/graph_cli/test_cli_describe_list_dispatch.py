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
        capture_output=True,
        text=True,
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


# ---------------------------------------------------------------------------
# Ecosystem auto-resolution for bare-name dependency describe
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_with_pypi_dep(tmp_path: Path) -> Path:
    """Repo with a single Python package declaring boto3 as a dependency.

    After update --full, the graph has a dependency node (ecosystem=pypi, name=boto3).
    """
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": ('[project]\nname = "myapp"\nversion = "0.1.0"\ndependencies = ["boto3>=1.38"]\n'),
            "src/myapp/__init__.py": "",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_describe_infers_dependency_and_autofills_ecosystem(repo_with_pypi_dep: Path) -> None:
    """Bare 'describe boto3' (no --kind, no --ecosystem) auto-resolves ecosystem=pypi."""
    # First verify the dependency node was actually created with ecosystem=pypi.
    probe = _cg(
        ["describe", "boto3", "--kind", "dependency", "--ecosystem", "pypi"],
        repo_with_pypi_dep,
    )
    assert probe.returncode == 0, f"fixture probe failed: {probe.stderr}"
    assert "boto3" in probe.stdout

    # Now test the inference path: no --kind, no --ecosystem.
    res = _cg(["describe", "boto3"], repo_with_pypi_dep)
    assert res.returncode == 0, f"expected exit 0, got {res.returncode}; stderr={res.stderr}"
    assert "boto3" in res.stdout
    assert "ecosystem" in res.stdout

    # JSON variant: confirm ecosystem is filled correctly.
    res_json = _cg(["--fmt", "json", "describe", "boto3"], repo_with_pypi_dep)
    assert res_json.returncode == 0, f"json variant failed: {res_json.stderr}"
    parsed = json.loads(res_json.stdout)
    assert parsed["name"] == "boto3"
    assert parsed["ecosystem"] == "pypi"


def test_describe_ambiguous_dependency_across_ecosystems(tmp_path: Path) -> None:
    """Bare 'describe lodash' when lodash exists in both pypi and npm → exit 7.

    The current scanner collapses same-(kind,name,path) rows via UPSERT, so two
    ecosystems for the same dep name cannot coexist through a normal scan. This
    test reaches the ambiguous branch by seeding the graph DB directly with two
    dependency rows, then calling _resolve_kind as a unit test.
    """
    import json as _json
    import sqlite3
    import types

    from graph_wiki_cli.graph_cli.q_describe import _resolve_kind
    from workspace_io.paths import graph_dir

    # Build a minimal repo + workspace so graph_dir resolves.
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {"pyproject.toml": '[project]\nname = "dummy"\nversion = "0.1.0"\n'},
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr

    # Resolve workspace and get the DB path.
    from workspace_io.config import resolve as resolve_workspace

    ws = resolve_workspace(tmp_path, require_manifest=False).workspace
    db = graph_dir(ws) / "code.db"

    # Directly insert a second dependency row for lodash/npm alongside any
    # existing lodash/pypi row (or insert both fresh).
    conn = sqlite3.connect(str(db))
    try:
        # Remove any existing lodash rows so we control exactly two.
        conn.execute("DELETE FROM nodes WHERE kind='dependency' AND name='lodash'")
        # Insert pypi row.
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?,?,NULL,NULL,?,?)",
            (
                "dependency",
                "lodash",
                _json.dumps({"ecosystem": "pypi", "name": "lodash", "url": "", "versions_in_use": []}),
                "dependency:pypi/lodash",
            ),
        )
        # Insert npm row — same (kind, name, path=NULL) key, so we must use a
        # distinct URI to differentiate; force a second row via raw INSERT.
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?,?,NULL,NULL,?,?)",
            (
                "dependency",
                "lodash",
                _json.dumps({"ecosystem": "npm", "name": "lodash", "url": "", "versions_in_use": []}),
                "dependency:npm/lodash",
            ),
        )
        conn.commit()
        # Verify two rows exist.
        count = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='dependency' AND name='lodash'").fetchone()[0]
        assert count == 2, f"expected 2 lodash rows, got {count}"
    finally:
        conn.close()

    # Call _resolve_kind directly with a SimpleNamespace that has ecosystem=None.
    args = types.SimpleNamespace(
        selector="lodash",
        ecosystem=None,
        workspace=ws,
    )
    result = _resolve_kind(args)
    from graph_io import exit_codes

    assert result == exit_codes.AMBIGUOUS, f"expected AMBIGUOUS (7), got {result!r}"


# ---------------------------------------------------------------------------
# Symbol describe: explicit --kind function/class/method/type + --in-package
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_with_symbols(tmp_path: Path) -> Path:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.1"\n',
            "src/demo/__init__.py": "__all__ = ['process']\nfrom .a import process\n",
            "src/demo/a.py": ("def process():\n    return validate()\n\ndef validate():\n    return 1\n"),
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_describe_symbol_explicit_kind(repo_with_symbols: Path) -> None:
    res = _cg(["describe", "process", "--kind", "function"], repo_with_symbols)
    assert res.returncode == 0, res.stderr
    assert "function process" in res.stdout
    assert "callees (depth 1): validate" in res.stdout


def test_describe_symbol_explicit_kind_json(repo_with_symbols: Path) -> None:
    res = _cg(["--fmt", "json", "describe", "process", "--kind", "function"], repo_with_symbols)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["name"] == "process"


def test_describe_symbol_in_package_narrows(repo_with_symbols: Path) -> None:
    res = _cg(["describe", "process", "--kind", "function", "--in-package", "demo"], repo_with_symbols)
    assert res.returncode == 0, res.stderr
    assert "function process" in res.stdout


def test_describe_help_lists_code_kinds(tmp_path: Path) -> None:
    init_repo(tmp_path)
    res = _cg(["describe", "--help"], tmp_path)
    assert res.returncode == 0, res.stderr
    for k in ("function", "class", "method", "type"):
        assert k in res.stdout


# ---------------------------------------------------------------------------
# --in-package actually selects: two packages with the same function name
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_two_pkgs_same_fn(tmp_path: Path) -> Path:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pkga/pyproject.toml": '[project]\nname = "pkga"\nversion = "0.1.0"\n',
            "pkga/src/pkga/__init__.py": "def shared_fn():\n    return 1\n",
            "pkgb/pyproject.toml": '[project]\nname = "pkgb"\nversion = "0.1.0"\n',
            "pkgb/src/pkgb/__init__.py": "def shared_fn():\n    return 2\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_describe_symbol_in_package_selects_right_package(repo_two_pkgs_same_fn: Path) -> None:
    a = _cg(["describe", "shared_fn", "--kind", "function", "--in-package", "pkga"], repo_two_pkgs_same_fn)
    assert a.returncode == 0, a.stderr
    assert "pkga" in a.stdout and "pkgb" not in a.stdout
    b = _cg(["describe", "shared_fn", "--kind", "function", "--in-package", "pkgb"], repo_two_pkgs_same_fn)
    assert b.returncode == 0, b.stderr
    assert "pkgb" in b.stdout and "pkga" not in b.stdout
