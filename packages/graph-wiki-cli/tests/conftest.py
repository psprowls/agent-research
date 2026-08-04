"""Package-local pytest fixtures for graph-wiki-cli tests.

Only CLI presentation fixtures live here. In particular, this conftest does not
import MCP fixtures from the agent package; moved CLI tests should exercise the
new ``graph_wiki_cli`` package boundary directly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PLAIN_HELP_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


@pytest.fixture(scope="session", autouse=True)
def _isolate_from_ambient_workspace():
    """Strip `GRAPH_WIKI_WORKSPACE` for the whole graph-wiki-cli test session.

    `graph_cli/`'s subprocess-based tests invoke the `gw` CLI via bare
    `subprocess.run(...)` with no `env=` override, so the child inherits this
    process's environment; `graph_cli/conftest.py`'s `seeded_db` fixture also
    calls `graph_io.update.run` without an explicit `workspace=`. Either path
    resolves through `workspace_io.config.resolve()`, which binds to the
    ambient env var over the tests' own tmp repo whenever it's set (e.g. a
    real workspace pinned in this repo's `.claude/settings.local.json`).
    Clearing it here — in os.environ, so subprocess children see it too —
    closes that gap regardless of invocation directory (package-local conftest
    fixtures apply even when pytest's rootdir resolves to this package rather
    than the workspace root).
    """
    mp = pytest.MonkeyPatch()
    mp.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    yield
    mp.undo()


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
    from workspace_io.paths import manifest_path

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
    ws = resolve_workspace(repo_root, require_manifest=False).workspace
    ws.mkdir(parents=True, exist_ok=True)
    manifest_path(ws).write_text("version: 2\n", encoding="utf-8")
    update.run(repo_root, full=True)
    return ws
