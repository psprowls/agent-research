"""Smoke test for the seeded_graph_workspace session fixture (Phase 59 Wave 3).

Exercises the fixture body so a broken fixture fails here rather than
confusingly surfacing inside the snapshot tests.
"""

from __future__ import annotations

from pathlib import Path

from workspace_io.paths import graph_dir


def test_seeded_graph_workspace_yields_path(seeded_graph_workspace: Path) -> None:
    """Fixture returns a Path that exists on disk."""
    assert isinstance(seeded_graph_workspace, Path)
    assert seeded_graph_workspace.exists(), (
        f"seeded_graph_workspace path does not exist: {seeded_graph_workspace}"
    )


def test_seeded_graph_workspace_code_db_is_file(seeded_graph_workspace: Path) -> None:
    """graph_dir(ws)/code.db is present — the DB was actually built."""
    db = graph_dir(seeded_graph_workspace) / "code.db"
    assert db.is_file(), (
        f"code.db not found at {db}; update.run may have failed during fixture setup"
    )
