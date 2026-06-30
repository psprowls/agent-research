"""Add tests/ to sys.path so _git_repo helpers are importable without a package prefix."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from graph_io.schema import apply_schema  # noqa: E402

# D7: domains now come from <workspace>/.graph-wiki.yaml (graph.domains), not a
# repo-root domains.yaml. This restores the exact domain set the sample_monorepo
# fixture defined pre-feature (core/web/presentation) into the workspace manifest.
_SAMPLE_DOMAINS_MANIFEST = (
    "version: 2\n"
    "graph:\n"
    "  domains:\n"
    "    core:\n"
    "      packages: [mypkg, pyutil]\n"
    "      description: Core utilities domain\n"
    "    web:\n"
    "      packages: [jspkg, webutil]\n"
    "      parent: presentation\n"
    "    presentation:\n"
    "      packages: []\n"
    "      description: Top-level UI layer\n"
)


@pytest.fixture(scope="session", autouse=True)
def _isolate_from_ambient_workspace():
    """Strip `GRAPH_WIKI_WORKSPACE` for the whole graph-io test session.

    graph-io tests build their own temp workspaces; no test reads the ambient
    env var. If a developer has it pointed at a real workspace, `config.resolve`
    would bind the seeded_db fixture's writes there — clobbering that workspace's
    `.graph-wiki.yaml` and code.db (the D7 manifest write made this destructive).
    Removing it categorically prevents any graph-io test from touching it.
    """
    mp = pytest.MonkeyPatch()
    mp.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    yield
    mp.undo()


@pytest.fixture(scope="session")
def seeded_workspace(tmp_path_factory) -> Path:
    """Workspace dir whose `.graph-wiki/code.db` is built by `update.run(..., full=True)`.

    Session-scoped: builds the sample_monorepo graph once and returns the
    workspace `Path` (not a connection). `seeded_db` opens a read-only conn over
    the same workspace; the handle-API tests pass this path straight to
    `open_reader`/`open_writer`.

    The workspace is pinned to a temp sibling of the seeded repo via the *pure*
    `resolve_workspace` (no env, no manifest check) and passed explicitly to
    `update.run`, so the fixture never resolves against the ambient
    `GRAPH_WIKI_WORKSPACE` (see `_isolate_from_ambient_workspace`).
    """
    # Lazy imports to avoid forcing the import at conftest collection time
    # for tests that do not need the seeded DB.
    from graph_io import update
    from workspace_io.config import resolve_workspace
    from workspace_io.paths import manifest_path

    fixture_src = Path(__file__).parent / "fixtures" / "sample_monorepo"
    repo_root = tmp_path_factory.mktemp("queries_seed") / "repo"
    shutil.copytree(fixture_src, repo_root)

    # `gw graph update` requires the workspace to be a git repository.
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seeded_db init"], cwd=repo_root, check=True)

    # D7: write the workspace manifest carrying graph.domains before update.run
    # (resolve_workspace is pure; update.run does not create the manifest).
    ws = resolve_workspace(repo_root)
    ws.mkdir(parents=True, exist_ok=True)
    manifest_path(ws).write_text(_SAMPLE_DOMAINS_MANIFEST, encoding="utf-8")

    update.run(repo_root, workspace=ws, full=True)
    return ws


@pytest.fixture(scope="session")
def seeded_db(seeded_workspace):
    """Read-only conn over sample_monorepo after `update.run(..., full=True)`.

    Session-scoped per D-14: one update run per test session; all callers
    share the resulting `mode=ro` connection. Safe because every Phase 32
    query helper opens read-only and issues no INSERT/UPDATE/DELETE.
    """
    from workspace_io.paths import graph_dir

    db_path = graph_dir(seeded_workspace) / "code.db"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def empty_db():
    """Empty in-memory DB with the schema applied; function-scoped."""
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    try:
        yield conn
    finally:
        conn.close()
