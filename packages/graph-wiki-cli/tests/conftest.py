from __future__ import annotations

"""Package-local pytest fixtures for graph-wiki-cli tests.

Only CLI presentation fixtures live here. In particular, this conftest does not
import MCP fixtures from the agent package; moved CLI tests should exercise the
new ``graph_wiki_cli`` package boundary directly.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


PLAIN_HELP_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


def _resolve_sample_monorepo_fixture() -> Path:
    """Resolve packages/graph-io/tests/fixtures/sample_monorepo."""
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
def seeded_graph_workspace(tmp_path_factory):
    """Session-scoped workspace Path for graph command CliRunner tests."""
    from graph_io import update
    from workspace_io.config import resolve as resolve_workspace

    if not _GRAPH_IO_FIXTURE.exists():
        pytest.skip(f"sample_monorepo fixture not found at {_GRAPH_IO_FIXTURE}")

    repo_root = tmp_path_factory.mktemp("gw_graph_cmd_ws") / "repo"
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
    return ws
