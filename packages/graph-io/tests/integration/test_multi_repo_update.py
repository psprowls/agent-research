"""Multi-repo workspace update integration tests (Tasks 2 + 3).

# integration-gate-allow
These tests do NOT touch any external network service (no Bedrock, no API) —
they build tmp_path git repos and drive graph-io's update pipeline against a
real sqlite DB. They are <2s and safe to run on every PR, so they carry the
`# integration-gate-allow` marker instead of the canonical
GRAPH_WIKI_RUN_INTEGRATION env gate (see docs/testing.md). They keep the
`pytest.mark.integration` marker so the default `-m "not integration"` run
still skips them; opt in with `-m integration`.
"""

import subprocess
from pathlib import Path

import pytest
from graph_io import store, update
from graph_io.uri import RepoContext, repo_uri

pytestmark = pytest.mark.integration


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _mk_py_repo(root: Path, name: str, pkg_name: str, dep: str | None = None):
    d = root / name
    (d / "src" / pkg_name).mkdir(parents=True)
    deps = f'dependencies = ["{dep}"]\n' if dep else "dependencies = []\n"
    (d / "pyproject.toml").write_text(f'[project]\nname = "{pkg_name}"\nversion = "0.1.0"\n{deps}')
    (d / "src" / pkg_name / "__init__.py").write_text("X = 1\n")
    _git(["init", "-q"], d)
    _git(["add", "-A"], d)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], d)
    return d


def test_two_members_two_repositories_and_scoped_repo_column(tmp_path):
    root = tmp_path / "mono"
    root.mkdir()
    ws = root / "workspace"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("version: 2\nmulti-repo: true\n")
    a = _mk_py_repo(root, "alpha", "alpha")
    b = _mk_py_repo(root, "beta", "beta")

    update.run_workspace([a, b], workspace=ws, full=True)

    conn = store.read_only_connect(update.graph_dir(ws) / "code.db")
    repos = conn.execute("SELECT name FROM nodes WHERE kind='repository' ORDER BY name").fetchall()
    assert [r[0] for r in repos] == ["alpha", "beta"]
    nulls = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='file' AND repo IS NULL").fetchone()[0]
    assert nulls == 0
    a_uri = repo_uri(RepoContext(org="local", repo="alpha"))
    a_files = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='file' AND repo=?", (a_uri,)).fetchone()[0]
    assert a_files >= 1


def test_full_rebuild_of_one_member_keeps_other(tmp_path):
    root = tmp_path / "mono"
    root.mkdir()
    ws = root / "workspace"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("version: 2\nmulti-repo: true\n")
    a = _mk_py_repo(root, "alpha", "alpha")
    b = _mk_py_repo(root, "beta", "beta")
    update.run_workspace([a, b], workspace=ws, full=True)

    update.run_workspace([a], workspace=ws, full=True)
    conn = store.read_only_connect(update.graph_dir(ws) / "code.db")
    beta = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='repository' AND name='beta'").fetchone()[0]
    assert beta == 1


def test_cross_repo_depends_on_package(tmp_path):
    root = tmp_path / "mono"
    root.mkdir()
    ws = root / "workspace"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("version: 2\nmulti-repo: true\n")
    a = _mk_py_repo(root, "alpha", "alpha")
    b = _mk_py_repo(root, "beta", "beta", dep="alpha")
    update.run_workspace([a, b], workspace=ws, full=True)

    conn = store.read_only_connect(update.graph_dir(ws) / "code.db")
    ext = conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='dependency' AND name='alpha'").fetchone()[0]
    assert ext == 0
    rows = conn.execute(
        """
        SELECT s.name, d.name FROM edges e
        JOIN nodes s ON s.id=e.src JOIN nodes d ON d.id=e.dst
        WHERE e.kind='depends_on_package'
        """
    ).fetchall()
    assert ("beta", "alpha") in rows
