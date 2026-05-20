"""Unit tests for eval_harness.isolation.EvalWorktree.

All tests are async (asyncio_mode=auto in pyproject.toml).
"""

from __future__ import annotations

from pathlib import Path

from eval_harness.isolation import EvalWorktree


async def test_evalworktree_creates_copy(fixture_vault_path: Path) -> None:
    """EvalWorktree creates a tmpdir workspace; wt.path/wiki/index.md exists."""
    async with EvalWorktree(fixture_vault_path) as wt:
        assert wt.path is not None
        assert wt.path.exists()
        assert (wt.path / "wiki" / "index.md").exists()


async def test_evalworktree_includes_graph_wiki(fixture_vault_path: Path) -> None:
    """EvalWorktree copy includes wiki/.graph-wiki/bm25 so indexes travel with the wiki."""
    async with EvalWorktree(fixture_vault_path) as wt:
        assert (wt.path / "wiki" / ".graph-wiki" / "bm25").exists()


async def test_evalworktree_cleans_up(fixture_vault_path: Path) -> None:
    """Tmpdir is removed after the context manager exits."""
    captured_tmp: Path | None = None
    async with EvalWorktree(fixture_vault_path) as wt:
        # Capture the internal _tmp before exit
        captured_tmp = Path(wt._tmp)  # noqa: SLF001
        assert captured_tmp.exists()

    # After __aexit__, the tmpdir must be gone
    assert captured_tmp is not None
    assert not captured_tmp.exists()


async def test_evalworktree_isolation(fixture_vault_path: Path) -> None:
    """Two EvalWorktrees opened sequentially have distinct paths."""
    async with EvalWorktree(fixture_vault_path) as wt1:
        path1 = wt1.path

    async with EvalWorktree(fixture_vault_path) as wt2:
        path2 = wt2.path

    assert path1 != path2
