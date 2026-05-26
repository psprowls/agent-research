from __future__ import annotations

"""Shared pytest fixtures for graph-wiki-agent tests.

Provides:
- fixture_vault_path: resolves the cross-package round-trip-vault fixture so
  unit and integration tests can read real vault pages without committing
  duplicate data.
- seeded_graph_conn: session-scoped read-only sqlite3.Connection over the
  sample_monorepo fixture in packages/graph-io after `graph_io.update.run`.
  Mirrors packages/graph-io/tests/conftest.py::seeded_db so Phase 37 tests
  exercise build_graph_tools(conn) without standing up the librarian fan-out.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Integration gate: decorate real-Bedrock tests so they are skipped in CI
# unless GRAPH_WIKI_RUN_INTEGRATION=1 is set. Tests may import this from conftest
# or redefine it locally — either is fine.
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


@pytest.fixture
def fixture_vault_path() -> Path:
    """Return the Path to packages/wiki-io/tests/fixtures/round-trip-vault.

    The path is computed relative to this conftest file so it works regardless
    of the cwd from which pytest is invoked. The fixture asserts the path
    exists so a misconfigured repo fails fast with a clear message rather than
    confusing FileNotFoundError in downstream tests.

    Threat mitigation T-03-02: path is anchored to this file's location;
    no user-supplied input is involved.
    """
    vault = (
        Path(__file__).parent.parent.parent.parent
        / "packages"
        / "wiki-io"
        / "tests"
        / "fixtures"
        / "round-trip-vault"
    )
    if not vault.exists():
        pytest.skip(
            f"round-trip-vault fixture not found at {vault}; "
            "check that packages/wiki-io is present in the workspace."
        )
    return vault


def _resolve_sample_monorepo_fixture() -> Path:
    """Resolve packages/graph-io/tests/fixtures/sample_monorepo.

    Tries the editable-install layout first (graph_io.__file__ → walk up to
    the package root then into tests/fixtures/sample_monorepo). Falls back
    to walking upward from cwd searching for the same relative path. Returns
    a Path object that may not exist — callers must check `.exists()`.
    """
    try:
        import graph_io  # noqa: WPS433 — lazy import inside resolver
    except ImportError:
        graph_io = None  # type: ignore[assignment]

    if graph_io is not None:
        candidate = (
            Path(graph_io.__file__).resolve().parent.parent.parent.parent
            / "packages"
            / "graph-io"
            / "tests"
            / "fixtures"
            / "sample_monorepo"
        )
        if candidate.exists():
            return candidate

    cwd = Path.cwd().resolve()
    for parent in (cwd, *cwd.parents):
        candidate = parent / "packages" / "graph-io" / "tests" / "fixtures" / "sample_monorepo"
        if candidate.exists():
            return candidate
    return cwd / "packages" / "graph-io" / "tests" / "fixtures" / "sample_monorepo"


_GRAPH_IO_FIXTURE = _resolve_sample_monorepo_fixture()


@pytest.fixture(scope="session")
def seeded_graph_conn(tmp_path_factory):
    """Session-scoped read-only conn over a sample_monorepo seeded via `graph_io.update.run`.

    Mirrors packages/graph-io/tests/conftest.py::seeded_db. Used by Phase 37's
    graph_tools tests to exercise build_graph_tools(conn) and the 5 tool callables
    against a real graph DB without standing up the librarian fan-out.
    """
    from graph_io import update
    from graph_io.store import read_only_connect
    from workspace_io.config import resolve as resolve_workspace
    from workspace_io.paths import graph_dir

    if not _GRAPH_IO_FIXTURE.exists():
        pytest.skip(f"sample_monorepo fixture not found at {_GRAPH_IO_FIXTURE}")

    repo_root = tmp_path_factory.mktemp("gwa_graph_seed") / "repo"
    shutil.copytree(_GRAPH_IO_FIXTURE, repo_root)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seeded init"], cwd=repo_root, check=True)
    update.run(repo_root, full=True)
    ws = resolve_workspace(repo_root, require_manifest=False).workspace
    conn = read_only_connect(graph_dir(ws) / "code.db")
    try:
        yield conn
    finally:
        conn.close()
