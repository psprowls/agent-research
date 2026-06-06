"""Unit tests for the bootstrap command (Plan 05-01; renamed in Phase 18 / CMD-02).

The Typer subcommand was renamed `init` → `bootstrap` in Phase 18 so Claude Code's
native `/init` slash command is reachable again. The underlying Python module
`graph_wiki_core.commands.init` and its `run_init` function intentionally remain
unchanged per Phase 18 D-02 (internal, machine-facing, not user-typed).

Requirements covered: CMD-01, CMD-02.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from workspace_io.manifest import read as read_manifest
from workspace_io.paths import manifest_path

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_init_result(wiki: Path, workspace: Path):
    from graph_wiki_core.commands.init import InitResult

    return InitResult(
        status="ok",
        wiki_path=str(wiki),
        repo_path=str(workspace),
        topic="test-topic",
        tool="claude-code",
        date="2026-05-14",
        installed_files=["CLAUDE.md", "index.md", "log.md"],
        page_templates_copied=3,
        layers={},
        raw_path=str(workspace / "raw"),
        work_path=str(workspace / "work"),
    )


# ---------------------------------------------------------------------------
# init_wiki creates raw/ and work/
# ---------------------------------------------------------------------------


def test_init_wiki_creates_raw_and_work_dirs(tmp_path: Path) -> None:
    """init_wiki() creates raw/ as a workspace sibling and work/ under the wiki dir."""
    from wiki_io.init_vault import init_wiki

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"

    init_wiki(
        wiki_path=wiki,
        repo_path=workspace,
        topic="test",
        tool="claude-code",
        force=True,
        non_interactive=True,
    )

    assert (workspace / "raw").is_dir(), "raw/ directory must be created"
    assert (wiki / "work").is_dir(), "work/ directory must be created under the wiki"


# ---------------------------------------------------------------------------
# run_init returns InitResult with raw_path and work_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_init_returns_init_result_with_raw_work(tmp_path: Path) -> None:
    """run_init() returns an InitResult whose raw_path and work_path point at created dirs."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"

    with patch(
        "graph_wiki_core.commands.init.resolve_wiki_and_repo",
        return_value=(wiki, workspace),
    ):
        from graph_wiki_core.commands.init import run_init

        # repo_path pins Phase-1 workspace bootstrap to tmp_path; without it,
        # run_init falls back to Path.cwd() and scaffolds a real <cwd>/graph-wiki.
        result = await run_init(
            topic="my-topic", tool="claude-code", force=True, workspace_path=None, repo_path=tmp_path
        )

    assert result.status == "ok"
    assert Path(result.raw_path).name == "raw"
    assert Path(result.work_path).name == "work"
    assert Path(result.raw_path).is_dir()
    assert Path(result.work_path).is_dir()


@pytest.mark.asyncio
async def test_run_init_registers_agent_plugin_identity_with_core_version(
    tmp_path: Path,
) -> None:
    """run_init() writes stable graph-wiki-agent identity using core dist version."""
    workspace = tmp_path / "workspace"
    repo = tmp_path / "repo"
    workspace.mkdir()
    repo.mkdir()
    wiki = workspace / "wiki"

    from graph_wiki_core.commands.init import run_init

    with (
        patch("graph_wiki_core.commands.init.importlib.metadata.version", return_value="9.8.7"),
        patch(
            "graph_wiki_core.commands.init.init_wiki",
            return_value={
                "status": "ok",
                "wiki_path": str(wiki),
                "repo_path": str(repo),
                "topic": "test-topic",
                "tool": "claude-code",
                "date": "2026-05-14",
                "installed_files": [],
                "page_templates_copied": 0,
                "layers": {},
                "raw_path": str(workspace / "raw"),
                "work_path": str(workspace / "work"),
            },
        ),
    ):
        await run_init(
            topic="test-topic",
            tool="claude-code",
            force=True,
            workspace_path=workspace,
            repo_path=repo,
        )

    plugins = read_manifest(manifest_path(workspace))["plugins"]
    assert {
        "name": "graph-wiki-agent",
        "installed_version": "9.8.7",
        "applied_version": "9.8.7",
    } in plugins
    assert all(p["name"] != "graph-wiki-core" for p in plugins)
