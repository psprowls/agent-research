"""gw graph query commands — end-to-end smoke against a tiny repo."""

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
def populated_repo(tmp_path: Path) -> Path:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.1"\n',
            "src/a.py": "__all__ = ['alpha']\n\ndef alpha():\n    return beta()\n\ndef beta():\n    return 1\n",
            # src/demo/__init__.py makes `demo` a first-party importable package.
            "src/demo/__init__.py": "__all__ = ['delta']\n\ndef delta():\n    return 1\n",
            # src/b.py imports `delta` from the first-party module `demo`;
            # resolve_file_imports (quick-260530-nsr) repoints the imports edge
            # onto the real file node src/demo/__init__.py, so
            # `gw graph imported-by src/demo/__init__.py` returns src/b.py.
            "src/b.py": "from demo import delta\n\ndef gamma():\n    return delta()\n",
        },
        "init",
    )
    res = _cg(["update"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_find(populated_repo: Path) -> None:
    res = _cg(["find", "--name", "alpha", "--kind", "function"], populated_repo)
    assert res.returncode == 0
    assert "alpha" in res.stdout


def test_find_json(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "find", "--name", "alpha"], populated_repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert any(r["name"] == "alpha" for r in data)


def test_callers(populated_repo: Path) -> None:
    res = _cg(["callers", "beta"], populated_repo)
    assert res.returncode == 0
    assert "alpha" in res.stdout


def test_callees(populated_repo: Path) -> None:
    res = _cg(["callees", "alpha"], populated_repo)
    assert res.returncode == 0
    assert "beta" in res.stdout


def test_imports_exports_commands_removed(populated_repo: Path) -> None:
    for argv in (["imports", "src/a.py"], ["exports", "src/a.py"]):
        res = _cg(argv, populated_repo)
        assert res.returncode != 0
        assert "no such command" in res.stderr.lower()


def test_describe_path_shows_imports_and_exports(populated_repo: Path) -> None:
    res = _cg(["describe", "src/a.py", "--kind", "path"], populated_repo)
    assert res.returncode == 0, res.stderr
    # src/a.py has no imports, so the spine omits that (empty) relationship.
    assert "exports:" in res.stdout
    assert "alpha" in res.stdout  # exported symbol from src/a.py


def test_describe_package(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "describe", "demo", "--kind", "package"], populated_repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["name"] == "demo"
    assert data["attributes"]["language"] == "python"


def test_describe_path(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "describe", "src/a.py", "--kind", "path"], populated_repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["path"] == "src/a.py"
    # Spine renders children as label strings, not dicts.
    assert any("alpha" in c for c in data["relationships"]["children"])


def test_query_without_db_returns_3(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    res = _cg(["find", "--name", "alpha"], tmp_path)
    assert res.returncode == 3


# ── imported-by / exports / exported-by ───────────────────────────────────────
#
# The Python parser stores `imports` edges as  src/b.py → ("file", symbol, module)
# where module is the bare specifier (e.g. "demo" for `from demo import delta`).
# resolve_file_imports (quick-260530-nsr) repoints first-party specifier stubs
# onto the real file node, so `gw graph imported-by` is queried by the resolved
# repo-relative path (src/demo/__init__.py), not the raw specifier.


_IMPORTED_FILE = "src/demo/__init__.py"


def test_imported_by(populated_repo: Path) -> None:
    res = _cg(["imported-by", _IMPORTED_FILE], populated_repo)
    assert res.returncode == 0, res.stderr
    assert "src/b.py" in res.stdout


def test_imported_by_symbol_filter(populated_repo: Path) -> None:
    # Post-resolution (quick-260530-nsr) the imports edge points at the real
    # file node; the imported symbol is preserved in the edge attrs (attrs.symbol)
    # rather than the dst node name. The `--symbol` filter (which matches the dst
    # node name) therefore only excludes — a clearly-foreign symbol returns empty.
    res = _cg(["imported-by", _IMPORTED_FILE, "--symbol", "no_such_symbol"], populated_repo)
    assert res.returncode == 0
    assert res.stdout.strip() == ""


def test_imported_by_json(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "imported-by", _IMPORTED_FILE], populated_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert any(r["path"] == "src/b.py" for r in data)
    assert all({"path", "symbol", "depth"} <= set(r) for r in data)


def test_exported_by(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "exported-by", "alpha"], populated_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert any(r["path"] == "src/a.py" for r in data)


def test_imported_by_without_db_returns_3(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    res = _cg(["imported-by", "a.py"], tmp_path)
    assert res.returncode == 3


# ── Phase 36: gw graph find named-flag UX (CGFIND-01/02/03) ────────────────────────


def test_find_with_named_flags(populated_repo: Path) -> None:
    res = _cg(["find", "--name", "alpha", "--kind", "function"], populated_repo)
    assert res.returncode == 0, res.stderr
    assert "alpha" in res.stdout


def test_find_no_filters_errors(populated_repo: Path) -> None:
    res = _cg(["find"], populated_repo)
    assert res.returncode == 2, (res.returncode, res.stderr)
    err = res.stderr.lower()
    assert "--name" in err and "--kind" in err and "--in-package" in err


def test_find_invalid_kind_errors(populated_repo: Path) -> None:
    res = _cg(["find", "--name", "alpha", "--kind", "bogus"], populated_repo)
    assert res.returncode == 2, (res.returncode, res.stderr)
    err = res.stderr.lower()
    assert "invalid choice" in err or "choose from" in err


def test_find_in_package(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "find", "--in-package", "demo"], populated_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    names = {r["name"] for r in data}
    assert "alpha" in names


def test_find_in_package_case_insensitive(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "find", "--in-package", "DEMO"], populated_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    names = {r["name"] for r in data}
    assert "alpha" in names


def test_find_in_package_unknown_exits_1(populated_repo: Path) -> None:
    res = _cg(["find", "--in-package", "nonexistent-pkg-xyz"], populated_repo)
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)


# ── Phase 49 BUILTIN-06 / D-12: gw graph list --kind builtins smoke ────────────────


@pytest.fixture()
def builtin_repo(tmp_path: Path) -> Path:
    """A git repo with a Python package importing pathlib + os; returns repo root after update."""
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.1"\n',
            "src/demo/__init__.py": "from pathlib import Path\nimport os\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_cg_list_builtins_smoke(builtin_repo: Path) -> None:
    """list --kind builtins exits 0; human output includes pathlib and os line-per-line."""
    res = _cg(["list", "--kind", "builtins"], builtin_repo)
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    assert "pathlib" in lines
    assert "os" in lines


def test_cg_list_builtins_json(builtin_repo: Path) -> None:
    """list --kind builtins --fmt json exits 0; output is a JSON list with kind='builtin' entries."""
    res = _cg(["--fmt", "json", "list", "--kind", "builtins"], builtin_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert len(data) > 0
    assert all(r["kind"] == "builtin" for r in data)
    names = {r["name"] for r in data}
    assert "pathlib" in names


def test_cg_list_builtins_empty(tmp_path: Path) -> None:
    """list --kind builtins on a freshly initialised empty graph exits 0 (no builtins yet)."""
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"pyproject.toml": '[project]\nname = "empty"\nversion = "0.1.1"\n'}, "init")
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr

    # human mode: warning to stderr, no stdout
    res_human = _cg(["list", "--kind", "builtins"], tmp_path)
    assert res_human.returncode == 0, res_human.stderr
    assert "No builtins in graph." in res_human.stderr
    assert res_human.stdout.strip() == ""

    # json mode: [] to stdout
    res_json = _cg(["--fmt", "json", "list", "--kind", "builtins"], tmp_path)
    assert res_json.returncode == 0, res_json.stderr
    assert json.loads(res_json.stdout) == []


# ── Phase 50 APP-05 / D-09: gw graph list --kind apps smoke ────────────────────────


@pytest.fixture()
def app_repo(tmp_path: Path) -> Path:
    """A git repo with a Python CLI app (pyproject has [project.scripts])."""
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": (
                '[project]\nname = "my-cli"\nversion = "0.1.1"\n[project.scripts]\nmy-cli = "my_cli.cli:main"\n'
            ),
            "src/my_cli/__init__.py": "",
            "src/my_cli/cli.py": "def main():\n    return 0\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_cg_list_apps_smoke(app_repo: Path) -> None:
    """list --kind apps exits 0; human output includes the app name line-per-line."""
    res = _cg(["list", "--kind", "apps"], app_repo)
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    assert "my-cli" in lines


def test_cg_list_apps_json(app_repo: Path) -> None:
    """list --kind apps --fmt json exits 0; output is a JSON list with kind='app' entries."""
    res = _cg(["--fmt", "json", "list", "--kind", "apps"], app_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all(r["kind"] == "app" for r in data)
    names = {r["name"] for r in data}
    assert "my-cli" in names


def test_cg_list_apps_empty(tmp_path: Path) -> None:
    """list --kind apps on a graph with no apps emits the empty-result message."""
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {"pyproject.toml": '[project]\nname = "purelib"\nversion = "0.1.1"\n'},
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr

    # human mode: warning to stderr, no stdout
    res_human = _cg(["list", "--kind", "apps"], tmp_path)
    assert res_human.returncode == 0, res_human.stderr
    assert "No apps in graph." in res_human.stderr
    assert res_human.stdout.strip() == ""

    # json mode: [] to stdout
    res_json = _cg(["--fmt", "json", "list", "--kind", "apps"], tmp_path)
    assert res_json.returncode == 0, res_json.stderr
    assert json.loads(res_json.stdout) == []


# ── gw graph list --kind dispatcher ───────────────────────────────────────────


def test_list_packages_via_kind(populated_repo: Path) -> None:
    res = _cg(["list", "--kind", "packages"], populated_repo)
    assert res.returncode == 0, res.stderr
    assert "demo" in res.stdout


def test_list_unknown_kind_is_bad_parameter(populated_repo: Path) -> None:
    res = _cg(["list", "--kind", "wombats"], populated_repo)
    assert res.returncode == 2
    assert "kind must be one of" in res.stderr


# ── --include-tests flag: gw graph callers / callees ──────────────────────────


@pytest.fixture()
def repo_with_test_caller(tmp_path: Path) -> Path:
    """prod target xtarget with a caller defined in a tests/ file (is_test=True)."""
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.1"\n',
            "src/x.py": "def xtarget():\n    return 1\n",
            "tests/test_x.py": "from x import xtarget\n\ndef caller_in_test():\n    return xtarget()\n",
        },
        "init",
    )
    res = _cg(["update"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_callers_excludes_tests_by_default(repo_with_test_caller: Path) -> None:
    res = _cg(["--fmt", "json", "callers", "xtarget"], repo_with_test_caller)
    assert res.returncode == 0, res.stderr
    rows = json.loads(res.stdout)
    assert not any(r["name"] == "caller_in_test" for r in rows)


def test_callers_include_tests_flag_shows_test_caller(repo_with_test_caller: Path) -> None:
    res = _cg(["--fmt", "json", "callers", "xtarget", "--include-tests"], repo_with_test_caller)
    assert res.returncode == 0, res.stderr
    rows = json.loads(res.stdout)
    assert any(r["name"] == "caller_in_test" for r in rows)


def test_callees_include_tests_flag_changes_rows(repo_with_test_caller: Path) -> None:
    default = _cg(["--fmt", "json", "callees", "caller_in_test"], repo_with_test_caller)
    included = _cg(["--fmt", "json", "callees", "caller_in_test", "--include-tests"], repo_with_test_caller)
    assert default.returncode == 0 and included.returncode == 0
    assert len(json.loads(included.stdout)) >= len(json.loads(default.stdout))
    assert any(r["name"] == "xtarget" for r in json.loads(included.stdout))
