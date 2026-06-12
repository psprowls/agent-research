"""Unit tests for wiki_io.backlink_index — scanner-derived `## Referenced in
wiki` regeneration (Slice 4). Pure Python, no Bedrock."""

from __future__ import annotations

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
        f"---\ntitle: {fm.get('title', slug)}\ncategory: source\n{meta}---\n\n# {slug}\n\n## Touches\n{link_block}\n",
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
        wiki,
        "2026-06-spec",
        ["[[entities/pkg_foo|Foo Package]]"],
        title="Auth Spec",
        source_type="spec",
        source_date="2026-06",
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
        wiki,
        "2026-06-multi",
        ["[[entities/pkg_foo]]", "[[entities/pkg_bar]]"],
        title="Multi",
        source_type="spec",
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


def test_build_entity_backlink_map_returns_category_slug_path(tmp_path):
    """[M4 §3.2] The extracted helper exposes the inverse map as a value:
    stem -> [(category, slug, page_path)] for [[entities/<stem>]] links across
    the preserved dirs."""
    from wiki_io.backlink_index import build_entity_backlink_map

    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir()
    (wiki / "sources").mkdir()
    (wiki / "entities" / "pkg_a.md").write_text("---\nuri: x\n---\n", encoding="utf-8")
    (wiki / "concepts" / "async-fanout.md").write_text(
        "---\ntitle: Async fan-out\n---\nSee [[entities/pkg_a]] for detail.\n",
        encoding="utf-8",
    )
    (wiki / "sources" / "spec-1.md").write_text("---\ntitle: Spec 1\n---\nAlso [[entities/pkg_a]].\n", encoding="utf-8")

    mapping = build_entity_backlink_map(wiki)

    assert set(mapping.keys()) == {"pkg_a"}
    entries = sorted(mapping["pkg_a"], key=lambda e: (e[0], e[1]))
    assert entries[0][0] == "concepts" and entries[0][1] == "async-fanout"
    assert entries[1][0] == "sources" and entries[1][1] == "spec-1"
    # Third element is the page Path, not a frontmatter Post.
    assert entries[0][2] == wiki / "concepts" / "async-fanout.md"
    assert all(isinstance(e[2], Path) for e in entries)


def test_regenerate_preserves_other_h2s(tmp_path: Path) -> None:
    """Scanner-owned: only ## Referenced in wiki is rewritten."""
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(
        wiki / "entities",
        "pkg_foo",
        extra_h2="## Custom Notes\nHand-written, keep me.\n\n",
    )
    _source_page(wiki, "2026-06-spec", ["[[entities/pkg_foo]]"], title="Spec")
    regenerate_referenced_in_wiki(wiki)
    text = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    assert "## Custom Notes\nHand-written, keep me." in text
    assert "## Narrative\nSome prose." in text


def test_guidance_page_applies_to_produces_entity_backlink(tmp_path):
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    # Entity page with the scanner-owned heading.
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg_graph-io.md").write_text(
        "---\ntitle: graph-io\n---\n\n## Referenced in wiki\n\n_No wiki pages reference this entity yet._\n",
        encoding="utf-8",
    )
    # Guidance page (nested under a topic) linking that entity.
    (wiki / "guidance" / "react-native").mkdir(parents=True)
    (wiki / "guidance" / "react-native" / "use-virtualizer.md").write_text(
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: x\napplies_when: y\nimpact: high\nupdated: 2026-06-08\ntokens: 0\n---\n\n"
        "## Guidance\nUse a virtualizer.\n\n## Applies to\n- [[entities/pkg_graph-io]]\n",
        encoding="utf-8",
    )

    updated = regenerate_referenced_in_wiki(wiki)

    assert "pkg_graph-io" in updated
    body = (wiki / "entities" / "pkg_graph-io.md").read_text(encoding="utf-8")
    # The bullet must carry the topic-qualified slug so the link resolves.
    assert "[[guidance/react-native/use-virtualizer]]" in body


def test_folded_architecture_concept_page_contributes_backlinks(tmp_path):
    """A concepts/ page with kind: architecture (folded from architecture/)
    contributes backlinks exactly like a plain concept page."""
    from wiki_io.backlink_index import build_entity_backlink_map

    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "project-overview.md").write_text(
        "---\ntitle: Project Overview\ncategory: concept\nkind: architecture\n---\n\n"
        "Built around [[entities/pkg_alpha]].\n",
        encoding="utf-8",
    )
    refs = build_entity_backlink_map(wiki)
    assert ("concepts", "project-overview", wiki / "concepts" / "project-overview.md") in refs["pkg_alpha"]
