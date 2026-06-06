"""Characterization harness: the entities/ tree must not change as containers are removed."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from graph_wiki_core.commands.init import run_init
from graph_wiki_core.commands.scan import run_scan


def _snapshot_entities(wiki: Path) -> dict[str, str]:
    """Map entities/<file> -> text, for byte-stable comparison."""
    ents = wiki / "entities"
    if not ents.exists():
        return {}
    return {str(p.relative_to(ents)): p.read_text(encoding="utf-8") for p in sorted(ents.rglob("*.md"))}


# Deliberately function-scoped (the underlying seeded_graph_workspace is
# session-scoped): each test gets a freshly bootstrapped wiki via
# run_init(force=True) + a clean run_scan write into wiki/, so the snapshot is
# captured against a pristine vault regardless of test ordering or reruns.
@pytest.fixture
def scanned_workspace(seeded_graph_workspace: Path):
    """Bootstrap a wiki on top of the seeded-graph workspace, return (wiki, workspace).

    seeded_graph_workspace is a Path to the workspace root (<repo>/graph-wiki/).
    The repo lives at workspace.parent.  We bootstrap a fresh wiki/ inside the
    workspace so run_scan has a valid vault to write into.
    """
    workspace = seeded_graph_workspace
    repo = workspace.parent

    asyncio.run(
        run_init(
            topic="sample-monorepo",
            tool="claude-code",
            force=True,
            interactive=False,
            workspace_path=workspace,
            repo_path=repo,
        )
    )

    wiki = workspace / "wiki"
    return wiki, workspace


def test_scan_entities_tree_snapshot(scanned_workspace, snapshot):
    wiki, workspace = scanned_workspace
    repo = workspace.parent
    asyncio.run(run_scan(workspace_path=workspace, repo_path=repo, narrate=False))
    entities = _snapshot_entities(wiki)
    assert entities, (
        "entities/ tree is empty after run_scan — snapshot would be useless; "
        "check that the graph was built and write_entities ran"
    )
    assert entities == snapshot
