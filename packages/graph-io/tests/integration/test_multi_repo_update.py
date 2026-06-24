"""Multi-repo workspace update integration tests (Tasks 2 + 3).

# integration-gate-allow
These tests do NOT touch any external network service (no Bedrock, no API) —
they build tmp_path git repos and drive graph-io's update pipeline against a
real sqlite DB. They are <2s and safe to run on every PR, so they carry the
`# integration-gate-allow` marker instead of the canonical
GRAPH_WIKI_RUN_INTEGRATION env gate (see docs/notes/testing.md). They keep the
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


def test_colliding_relpaths_and_pkg_name_stay_distinct(tmp_path):
    """Two sibling repos sharing a package name AND relative file paths
    (`pyproject.toml`, `src/shared/__init__.py`) must NOT merge into one node.

    This is the regression guard for the connection-scoped `upsert` identity:
    without it the shared `(kind, name, path)` keys collide into single rows,
    giving e.g. `package:shared` two `physically_contains` parents and raising
    `StrictTreeInvariantError`. With per-member repo scoping each repo gets its
    own distinct nodes.
    """
    root = tmp_path / "mono"
    root.mkdir()
    ws = root / "workspace"
    ws.mkdir()
    (ws / ".graph-wiki.yaml").write_text("version: 2\nmulti-repo: true\n")
    # Same package name "shared" + identical relative paths in both repos; only
    # the repo dir name (-> repo URI) differs.
    a = _mk_py_repo(root, "alpha", "shared")
    b = _mk_py_repo(root, "beta", "shared")

    # Must not raise StrictTreeInvariantError.
    update.run_workspace([a, b], workspace=ws, full=True)

    conn = store.read_only_connect(update.graph_dir(ws) / "code.db")
    a_uri = repo_uri(RepoContext(org="local", repo="alpha"))
    b_uri = repo_uri(RepoContext(org="local", repo="beta"))

    # The shared package name is two DISTINCT rows, one per repo.
    pkg_repos = conn.execute("SELECT repo FROM nodes WHERE kind='package' AND name='shared' ORDER BY repo").fetchall()
    assert [r[0] for r in pkg_repos] == [a_uri, b_uri]

    # The colliding relative file path materializes once per repo.
    init_rel = "src/shared/__init__.py"
    init_repos = conn.execute(
        "SELECT repo FROM nodes WHERE kind='file' AND path=? ORDER BY repo",
        (init_rel,),
    ).fetchall()
    assert [r[0] for r in init_repos] == [a_uri, b_uri]

    # No file node leaked unstamped, and no physically_contains child has >1 parent
    # (the invariant the scoping protects — re-checked here explicitly).
    multi_parent = conn.execute(
        "SELECT dst, COUNT(*) FROM edges WHERE kind='physically_contains' GROUP BY dst HAVING COUNT(*) > 1"
    ).fetchall()
    assert multi_parent == []


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
