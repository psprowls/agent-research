from __future__ import annotations

from pathlib import Path

from graph_wiki_core.commands.guidance_archive import run_guidance_archive
from guidance_io.paths import list_all_pages


def _write_page(wiki: Path, topic: str, slug: str) -> Path:
    p = wiki / "guidance" / topic / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\ntitle: {slug}\ncategory: guidance\nsummary: s\ntopic: {topic}\nimpact: low\n---\n\nbody\n",
        encoding="utf-8",
    )
    return p


def test_dry_run_plans_without_moving(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    _write_page(wiki, "python", "old")

    result = run_guidance_archive(workspace_path=workspace, slugs=["python/old"], dry_run=True)

    assert result.dry_run is True
    assert len(result.moved) == 1
    assert (wiki / "guidance" / "python" / "old.md").exists()
    assert not (wiki / "guidance" / "python" / "_archive").exists()


def test_executes_move_and_regenerates_index(tmp_path: Path) -> None:
    # tmp_path is not a git repo → git mv fails → os.rename fallback exercised.
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    _write_page(wiki, "python", "old")
    _write_page(wiki, "python", "keeper")  # topic survives

    result = run_guidance_archive(workspace_path=workspace, slugs=["python/old"], dry_run=False)

    assert result.dry_run is False
    assert len(result.moved) == 1
    assert (wiki / "guidance" / "python" / "_archive" / "old.md").exists()
    assert not (wiki / "guidance" / "python" / "old.md").exists()
    # Per-topic index regenerated, archived page absent, keeper present.
    topic_index = (wiki / "guidance" / "python" / "index.md").read_text(encoding="utf-8")
    assert "guidance/python/old" not in topic_index
    assert "keeper" in topic_index
    # Root index regenerated and still lists the surviving topic.
    root_index = (wiki / "guidance" / "index.md").read_text(encoding="utf-8")
    assert "python" in root_index.lower()


def test_recall_excludes_archived_page(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    _write_page(wiki, "python", "old")
    _write_page(wiki, "python", "keeper")

    run_guidance_archive(workspace_path=workspace, slugs=["python/old"], dry_run=False)

    remaining = {p.name for p in list_all_pages(workspace)}
    assert "old.md" not in remaining
    assert "keeper.md" in remaining


def test_emptied_topic_index_removed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    _write_page(wiki, "python", "only")
    # Pre-seed a stale topic index that would otherwise survive.
    (wiki / "guidance" / "python" / "index.md").write_text("stale -> [[guidance/python/only]]", encoding="utf-8")

    run_guidance_archive(workspace_path=workspace, slugs=["python/only"], dry_run=False)

    assert (wiki / "guidance" / "python" / "_archive" / "only.md").exists()
    # The now-empty topic's index.md is gone (not left dangling).
    assert not (wiki / "guidance" / "python" / "index.md").exists()


def test_skips_surfaced(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    _write_page(wiki, "python", "real")

    result = run_guidance_archive(
        workspace_path=workspace, slugs=["unqualified", "python/missing", "python/real"], dry_run=False
    )

    assert len(result.moved) == 1
    reasons = " ".join(s["reason"] for s in result.skipped)
    assert "unqualified" in reasons
    assert "not found" in reasons
