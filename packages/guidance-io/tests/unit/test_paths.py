from __future__ import annotations

from pathlib import Path

from guidance_io.paths import (
    guidance_dir,
    guidance_index_path,
    list_pages,
    page_path,
    slugify,
    tags_yaml_path,
)


def test_guidance_dir_is_under_wiki() -> None:
    ws = Path("/tmp/ws")
    assert guidance_dir(ws) == ws / "wiki" / "guidance"


def test_page_path_composes_topic_and_slug() -> None:
    ws = Path("/tmp/ws")
    assert page_path(ws, "react-native", "use-a-virtualizer") == (
        ws / "wiki" / "guidance" / "react-native" / "use-a-virtualizer.md"
    )


def test_slugify_lowercases_and_dashes() -> None:
    assert slugify("Use a List Virtualizer for Any List") == "use-a-list-virtualizer-for-any-list"


def test_slugify_strips_punctuation_and_edges() -> None:
    assert slugify("  FlashList / LegendList!  ") == "flashlist-legendlist"


def test_slugify_empty_returns_untitled() -> None:
    assert slugify("!!!") == "untitled"


def test_list_pages_returns_sorted_md(tmp_path: Path) -> None:
    topic_dir = tmp_path / "wiki" / "guidance" / "react-native"
    topic_dir.mkdir(parents=True)
    (topic_dir / "b-page.md").write_text("---\n---\n", encoding="utf-8")
    (topic_dir / "a-page.md").write_text("---\n---\n", encoding="utf-8")
    (topic_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    pages = list_pages(tmp_path, "react-native")
    assert [p.name for p in pages] == ["a-page.md", "b-page.md"]


def test_list_pages_absent_topic_returns_empty(tmp_path: Path) -> None:
    assert list_pages(tmp_path, "nonexistent") == []


def test_list_pages_excludes_index_md(tmp_path: Path) -> None:
    topic_dir = tmp_path / "wiki" / "guidance" / "react-native"
    topic_dir.mkdir(parents=True)
    (topic_dir / "a-page.md").write_text("---\n---\n", encoding="utf-8")
    (topic_dir / "index.md").write_text("---\n---\n", encoding="utf-8")
    pages = list_pages(tmp_path, "react-native")
    assert [p.name for p in pages] == ["a-page.md"]


def test_tags_yaml_path() -> None:
    ws = Path("/tmp/ws")
    assert tags_yaml_path(ws) == ws / "wiki" / "guidance" / "tags.yaml"


def test_guidance_index_path() -> None:
    ws = Path("/tmp/ws")
    assert guidance_index_path(ws) == ws / ".graph-wiki" / "guidance-index.json"
