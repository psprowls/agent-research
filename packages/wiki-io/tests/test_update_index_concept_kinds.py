"""Concepts sub-index groups by effective kind; architecture category is gone."""

from __future__ import annotations

from pathlib import Path

from wiki_io.update_index import update_index


def _page(path: Path, title: str, kind: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kind_line = f"kind: {kind}\n" if kind else ""
    path.write_text(
        f"---\ntitle: {title}\ncategory: concept\n{kind_line}summary: s\n---\n\nBody.\n",
        encoding="utf-8",
    )


def test_concepts_subindex_groups_by_kind(tmp_path):
    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "overview.md", "Overview", "architecture")
    _page(wiki / "concepts" / "retry.md", "Retry", "pattern")
    _page(wiki / "concepts" / "auth.md", "Auth")
    _page(wiki / "concepts" / "weird.md", "Weird", "bogus")  # unknown -> Concepts
    update_index(wiki)
    text = (wiki / "concepts" / "index.md").read_text(encoding="utf-8")
    a, p, c = text.index("### Architecture"), text.index("### Patterns"), text.index("### Concepts")
    assert a < p < c
    assert text.index("[[concepts/weird|Weird]]") > c  # unknown kind folds into Concepts
    assert text.index("[[concepts/overview|Overview]]") > a


def test_concepts_subindex_all_default_renders_flat(tmp_path):
    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "auth.md", "Auth")
    _page(wiki / "concepts" / "cache.md", "Cache")
    update_index(wiki)
    text = (wiki / "concepts" / "index.md").read_text(encoding="utf-8")
    assert "### " not in text  # no kind sub-headings when every page is default


def test_no_architecture_index_written(tmp_path):
    wiki = tmp_path / "wiki"
    _page(wiki / "concepts" / "auth.md", "Auth")
    update_index(wiki)
    assert not (wiki / "architecture").exists()
