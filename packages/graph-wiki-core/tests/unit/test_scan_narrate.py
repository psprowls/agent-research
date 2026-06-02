from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter
import pytest

from graph_io import exit_codes
from graph_wiki_core.commands import scan as scan_module


def _seed_minimal_graph(db_path: Path) -> None:
    """One package node pkg-a (no domain), uri pkg:org/repo/pkg-a."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', "
            "'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n\nNo pinned containers.\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    return workspace


def test_narrate_false_skips_fanout_and_keeps_placeholder(tmp_workspace, monkeypatch):
    """run_scan(narrate=False): zero SubagentPool.run_all calls; the entity page
    keeps the template `## Narrative` placeholder and `— TODO` file-map rows."""
    workspace = tmp_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    _seed_minimal_graph(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", "")
    )

    run_all_calls: list = []

    async def _spy_run_all(self, *, items, task, role, model_id, max_concurrency):
        run_all_calls.append(role)
        from subagent_runtime.pool import FanOutResult
        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _spy_run_all)
    monkeypatch.setattr(scan_module, "make_llm", lambda role, *, model_override=None: MagicMock())

    # Minimal deterministic file map so the package page gets a File map section.
    pkg_a_block = (
        "## File map - pkg-a\n"
        "TODO — overview of this package's tree.\n\n"
        "### pkg-a/\n"
        "TODO — describe what this directory contains.\n\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
    )
    fake_ws = [{
        "name": "pkg-a", "path": "packages/pkg-a",
        "wiki_relative_path": "packages/pkg-a/overview.md",
        "type": "library", "language": "python",
        "changed_files": None, "file_map": pkg_a_block,
    }]
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: fake_ws)
    monkeypatch.setattr(
        scan_module, "_load_existing_pages",
        lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}),
    )
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module, "compute_diff",
        lambda ws, ex: {"new": ["pkg-a"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    result = asyncio.run(
        scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False, narrate=False)
    )

    assert run_all_calls == [], f"narrate=False must not run any fan-out; got {run_all_calls}"
    assert "pkg:org/repo/pkg-a" in result.entities_created
    assert result.entities_narrated == []

    page = next(
        p for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "pkg:org/repo/pkg-a"
    )
    text = page.read_text(encoding="utf-8")
    # Structural parity: Narrative placeholder intact, file-map rows still — TODO.
    assert "_(scanner will populate on next scan)_" in text
    assert "| `pyproject.toml` | file | — TODO |" in text
