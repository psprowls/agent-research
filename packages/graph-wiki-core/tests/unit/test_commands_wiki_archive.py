# packages/graph-wiki-core/tests/unit/test_commands_wiki_archive.py
from __future__ import annotations

import asyncio
from pathlib import Path


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace, wiki). Creates wiki/ structure."""
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    return workspace, wiki


def _write_page(wiki: Path, d: str, stem: str, status: str) -> Path:
    dir_path = wiki / d
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / f"{stem}.md"
    p.write_text(f"---\ntitle: {stem}\nstatus: {status}\n---\n\nbody\n", encoding="utf-8")
    return p


def test_run_wiki_archive_dry_run(tmp_path: Path) -> None:
    from graph_wiki_core.commands.wiki_archive import run_wiki_archive

    workspace, wiki = _make_workspace(tmp_path)
    _write_page(wiki, "adrs", "0002-gone", "superseded")

    result = asyncio.run(run_wiki_archive(workspace_path=workspace, dry_run=True))

    assert result.dry_run is True
    assert len(result.moved) == 1
    assert not (wiki / "adrs" / "_archive").exists()


def test_run_wiki_archive_executes_move_via_rename(tmp_path: Path) -> None:
    # tmp_path is not a git repo → git mv fails → os.rename fallback exercised.
    from graph_wiki_core.commands.wiki_archive import run_wiki_archive

    workspace, wiki = _make_workspace(tmp_path)
    _write_page(wiki, "concepts", "old-thing", "deprecated")
    _write_page(wiki, "concepts", "active-thing", "active")

    result = asyncio.run(run_wiki_archive(workspace_path=workspace, dry_run=False))

    assert result.dry_run is False
    assert len(result.moved) == 1
    assert (wiki / "concepts" / "_archive" / "old-thing.md").exists()
    assert not (wiki / "concepts" / "old-thing.md").exists()
    assert (wiki / "concepts" / "active-thing.md").exists()  # untouched
    # No sidecar/index side effects.
    assert not (wiki / "work-index.json").exists()


def test_run_wiki_archive_targeted(tmp_path: Path) -> None:
    from graph_wiki_core.commands.wiki_archive import run_wiki_archive

    workspace, wiki = _make_workspace(tmp_path)
    _write_page(wiki, "proposals", "approved-one", "approved")
    _write_page(wiki, "proposals", "open-one", "created")

    result = asyncio.run(
        run_wiki_archive(
            workspace_path=workspace,
            slugs=["proposals/approved-one", "proposals/open-one"],
            dry_run=False,
        )
    )

    assert len(result.moved) == 1
    assert any("not terminal" in s["reason"] for s in result.skipped)
    assert (wiki / "proposals" / "_archive" / "approved-one.md").exists()
