"""cg query commands — end-to-end smoke against a tiny repo."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from _git_repo import init_repo, write_and_commit


def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "graph_io.cli.main", "--repo", str(cwd), "--mode", "test", *args],
        capture_output=True, text=True,
    )


@pytest.fixture()
def populated_repo(tmp_path: Path) -> Path:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "src/a.py": "__all__ = ['alpha']\n\ndef alpha():\n    return beta()\n\ndef beta():\n    return 1\n",
            # src/b.py imports `alpha` from module `a`; the imports edge dst.path = "a"
            # so `cg imported-by a` returns src/b.py.  --full would prune the stub node,
            # so the fixture uses plain `update` (no --full) to preserve import edges.
            "src/b.py": "from a import alpha\n\ndef gamma():\n    return alpha()\n",
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


def test_imports(populated_repo: Path) -> None:
    res = _cg(["imports", "src/a.py"], populated_repo)
    assert res.returncode == 0


def test_describe_package(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "describe-package", "demo"], populated_repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["name"] == "demo"
    assert data["language"] == "python"


def test_describe_path(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "describe-path", "src/a.py"], populated_repo)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["path"] == "src/a.py"
    assert any(c["name"] == "alpha" for c in data["children"])


def test_query_without_db_returns_3(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"a.py": "x = 1\n"}, "init")
    res = _cg(["find", "--name", "alpha"], tmp_path)
    assert res.returncode == 3


# ── imported-by / exports / exported-by ───────────────────────────────────────
#
# The Python parser stores `imports` edges as  src/b.py → ("file", symbol, module)
# where module is the bare module name (e.g. "a" for `from a import alpha`).
# `cg imported-by` queries by dst.path, so the correct path argument is the
# module name ("a"), not the source file path ("src/a.py").
# `update --full` prunes placeholder nodes that aren't tracked paths, which
# destroys the import stubs; the fixture therefore uses plain `update`.


def test_imported_by(populated_repo: Path) -> None:
    res = _cg(["imported-by", "a"], populated_repo)
    assert res.returncode == 0, res.stderr
    assert "src/b.py" in res.stdout


def test_imported_by_symbol_filter(populated_repo: Path) -> None:
    res = _cg(["imported-by", "a", "--symbol", "alpha"], populated_repo)
    assert res.returncode == 0, res.stderr
    assert "src/b.py" in res.stdout

    res2 = _cg(["imported-by", "a", "--symbol", "no_such_symbol"], populated_repo)
    assert res2.returncode == 0
    assert res2.stdout.strip() == ""


def test_imported_by_json(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "imported-by", "a"], populated_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert any(r["path"] == "src/b.py" for r in data)
    assert all({"path", "symbol", "depth"} <= set(r) for r in data)


def test_exports(populated_repo: Path) -> None:
    res = _cg(["--fmt", "json", "exports", "src/a.py"], populated_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    names = {r["name"] for r in data}
    assert "alpha" in names


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


# ── Phase 36: cg find named-flag UX (CGFIND-01/02/03) ────────────────────────


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


# ── Phase 49 BUILTIN-06 / D-12: cg list-builtins smoke ───────────────────────


@pytest.fixture()
def builtin_repo(tmp_path: Path) -> Path:
    """A git repo with a Python package importing pathlib + os; returns repo root after update."""
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "src/demo/__init__.py": "from pathlib import Path\nimport os\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_cg_list_builtins_smoke(builtin_repo: Path) -> None:
    """list-builtins exits 0; human output includes pathlib and os line-per-line."""
    res = _cg(["list-builtins"], builtin_repo)
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    assert "pathlib" in lines
    assert "os" in lines


def test_cg_list_builtins_json(builtin_repo: Path) -> None:
    """list-builtins --fmt json exits 0; output is a JSON list with kind='builtin' entries."""
    res = _cg(["--fmt", "json", "list-builtins"], builtin_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert len(data) > 0
    assert all(r["kind"] == "builtin" for r in data)
    names = {r["name"] for r in data}
    assert "pathlib" in names


def test_cg_list_builtins_empty(tmp_path: Path) -> None:
    """list-builtins on a freshly initialised empty graph exits 0 (no builtins yet)."""
    init_repo(tmp_path)
    write_and_commit(tmp_path, {"pyproject.toml": '[project]\nname = "empty"\nversion = "0.1.0"\n'}, "init")
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr

    # human mode: warning to stderr, no stdout
    res_human = _cg(["list-builtins"], tmp_path)
    assert res_human.returncode == 0, res_human.stderr
    assert "No builtins in graph." in res_human.stderr
    assert res_human.stdout.strip() == ""

    # json mode: [] to stdout
    res_json = _cg(["--fmt", "json", "list-builtins"], tmp_path)
    assert res_json.returncode == 0, res_json.stderr
    assert json.loads(res_json.stdout) == []
