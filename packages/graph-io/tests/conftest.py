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


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory):
    """Read-only conn over sample_monorepo after `update.run(..., full=True)`.

    Session-scoped per D-14: one update run per test session; all callers
    share the resulting `mode=ro` connection. Safe because every Phase 32
    query helper opens read-only and issues no INSERT/UPDATE/DELETE.
    """
    # Lazy imports to avoid forcing the import at conftest collection time
    # for tests that do not need the seeded DB.
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace
    from workspace_io.paths import graph_dir

    fixture_src = Path(__file__).parent / "fixtures" / "sample_monorepo"
    repo_root = tmp_path_factory.mktemp("queries_seed") / "repo"
    shutil.copytree(fixture_src, repo_root)

    # `cg update` requires the workspace to be a git repository.
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=repo_root, check=True
    )
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seeded_db init"], cwd=repo_root, check=True
    )

    update.run(repo_root, full=True)

    ws = resolve_workspace(repo_root, require_manifest=False).workspace
    db_path = graph_dir(ws) / "code.db"
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
