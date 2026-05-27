"""Phase 45 D-02 surgical change: update_index no longer writes wiki/index.md."""

from __future__ import annotations

from pathlib import Path

from wiki_io.update_index import update_index


def _seed_wiki(tmp_path: Path) -> Path:
    """Create a minimal wiki structure with one curated page per category."""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "foo.md").write_text(
        "---\ncategory: concept\ntitle: Foo\nsummary: A test concept\n---\n\nbody\n",
        encoding="utf-8",
    )
    (wiki / "adrs").mkdir(parents=True)
    (wiki / "adrs" / "001.md").write_text(
        "---\ncategory: adr\ntitle: ADR-001\n---\n\nbody\n",
        encoding="utf-8",
    )
    return wiki


def test_update_index_does_not_write_main_index(tmp_path: Path):
    wiki = _seed_wiki(tmp_path)
    sentinel = "SENTINEL — must not be overwritten by update_index\n"
    (wiki / "index.md").write_text(sentinel, encoding="utf-8")

    update_index(wiki)

    assert (wiki / "index.md").read_text(encoding="utf-8") == sentinel, (
        "update_index(wiki) must NOT write wiki/index.md (Phase 45 D-02)"
    )


def test_update_index_does_not_create_main_index_when_absent(tmp_path: Path):
    wiki = _seed_wiki(tmp_path)
    assert not (wiki / "index.md").exists()

    update_index(wiki)

    assert not (wiki / "index.md").exists(), (
        "update_index must NOT create wiki/index.md (Phase 45 D-02)"
    )


def test_update_index_still_writes_per_folder_subindexes(tmp_path: Path):
    wiki = _seed_wiki(tmp_path)
    update_index(wiki)

    assert (wiki / "concepts" / "index.md").exists()
    assert (wiki / "adrs" / "index.md").exists()
    concepts_index = (wiki / "concepts" / "index.md").read_text(encoding="utf-8")
    assert "Foo" in concepts_index


def test_update_index_leaves_pre_existing_main_index_mtime_unchanged(tmp_path: Path):
    wiki = _seed_wiki(tmp_path)
    (wiki / "index.md").write_text("preexisting\n", encoding="utf-8")
    mtime_before = (wiki / "index.md").stat().st_mtime_ns

    update_index(wiki)

    mtime_after = (wiki / "index.md").stat().st_mtime_ns
    assert mtime_before == mtime_after, "update_index must not touch wiki/index.md mtime"
