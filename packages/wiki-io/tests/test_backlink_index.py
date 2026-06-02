from __future__ import annotations

"""Unit tests for wiki_io.backlink_index — scanner-derived `## Referenced in
wiki` regeneration (Slice 4). Pure Python, no Bedrock."""

from pathlib import Path


def _entity_page(entities: Path, stem: str, extra_h2: str = "") -> Path:
    entities.mkdir(parents=True, exist_ok=True)
    p = entities / f"{stem}.md"
    body = (
        "---\n"
        f"uri: pkg:o/r/{stem}\n"
        "kind: package\n"
        "---\n\n"
        f"# {stem}\n\n"
        "## Narrative\n"
        "Some prose.\n\n"
        "## Referenced in wiki\n"
        "_(scanner will populate on next scan)_\n\n"
        f"{extra_h2}"
        "## Purpose\n"
        "Human-authored text that must survive.\n"
    )
    p.write_text(body, encoding="utf-8")
    return p


def _source_page(wiki: Path, slug: str, links: list[str], **fm) -> Path:
    d = wiki / "sources"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}.md"
    meta = "".join(f"{k}: {v}\n" for k, v in fm.items())
    link_block = "\n".join(f"- {lnk}" for lnk in links)
    p.write_text(
        f"---\ntitle: {fm.get('title', slug)}\ncategory: source\n{meta}---\n\n"
        f"# {slug}\n\n## Touches\n{link_block}\n",
        encoding="utf-8",
    )
    return p


def test_inject_referenced_in_wiki_replaces_only_that_region(tmp_path: Path) -> None:
    from wiki_io.backlink_index import inject_referenced_in_wiki

    page = _entity_page(tmp_path / "entities", "pkg_foo")
    inject_referenced_in_wiki(page, "- [[sources/2026-06-spec]] — Spec")
    text = page.read_text(encoding="utf-8")
    assert "- [[sources/2026-06-spec]] — Spec" in text
    # Other regions preserved verbatim.
    assert "## Narrative\nSome prose." in text
    assert "Human-authored text that must survive." in text


def test_regenerate_builds_sorted_backlinks(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_foo")
    # `|alias` must be stripped so the link resolves to stem `pkg_foo`.
    _source_page(
        wiki, "2026-06-spec", ["[[entities/pkg_foo|Foo Package]]"],
        title="Auth Spec", source_type="spec", source_date="2026-06",
    )
    updated = regenerate_referenced_in_wiki(wiki)
    assert "pkg_foo" in updated
    text = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    assert "[[sources/2026-06-spec]]" in text
    assert "Auth Spec" in text
    assert "spec" in text


def test_regenerate_multi_entity_source_backlinks_from_all(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_foo")
    _entity_page(wiki / "entities", "pkg_bar")
    _source_page(
        wiki, "2026-06-multi",
        ["[[entities/pkg_foo]]", "[[entities/pkg_bar]]"],
        title="Multi", source_type="spec",
    )
    regenerate_referenced_in_wiki(wiki)
    foo = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    bar = (wiki / "entities" / "pkg_bar.md").read_text(encoding="utf-8")
    assert "[[sources/2026-06-multi]]" in foo
    assert "[[sources/2026-06-multi]]" in bar


def test_regenerate_is_idempotent(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_foo")
    _source_page(wiki, "2026-06-spec", ["[[entities/pkg_foo]]"], title="Spec")
    regenerate_referenced_in_wiki(wiki)
    first = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    regenerate_referenced_in_wiki(wiki)
    second = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    assert first == second


def test_regenerate_empty_when_no_references(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_lonely")
    regenerate_referenced_in_wiki(wiki)
    text = (wiki / "entities" / "pkg_lonely.md").read_text(encoding="utf-8")
    # Placeholder replaced by the deterministic "no references" line.
    assert "_No wiki pages reference this entity yet._" in text
    assert "Human-authored text that must survive." in text


def test_regenerate_preserves_other_h2s(tmp_path: Path) -> None:
    """Scanner-owned: only ## Referenced in wiki is rewritten."""
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(
        wiki / "entities", "pkg_foo",
        extra_h2="## Custom Notes\nHand-written, keep me.\n\n",
    )
    _source_page(wiki, "2026-06-spec", ["[[entities/pkg_foo]]"], title="Spec")
    regenerate_referenced_in_wiki(wiki)
    text = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    assert "## Custom Notes\nHand-written, keep me." in text
    assert "## Narrative\nSome prose." in text
