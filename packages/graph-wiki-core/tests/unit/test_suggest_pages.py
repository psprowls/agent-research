from __future__ import annotations

from graph_wiki_core.commands.suggest_pages import (
    SUGGESTION_KINDS,
    parse_extractor_response,
)


def test_parse_extractor_response_valid_mapping() -> None:
    raw = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Section Ownership\n"
        "    slug: section-ownership\n"
        "    mode: create_new\n"
        "    existing_slug:\n"
        "    rationale: A reusable split.\n"
    )
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert len(entries) == 1
    e = entries[0]
    assert e["kind"] == "concept"
    assert e["title"] == "Section Ownership"
    assert e["slug"] == "section-ownership"
    assert e["mode"] == "create_new"
    assert e["existing_slug"] is None
    assert e["rationale"] == "A reusable split."
    # status is NOT set by the parser (merge owns it)
    assert "status" not in e


def test_parse_extractor_response_empty_list_is_parsed_true() -> None:
    entries, parsed = parse_extractor_response("suggestions: []")
    assert entries == []
    assert parsed is True


def test_parse_extractor_response_top_level_list_accepted() -> None:
    raw = "- kind: adr\n  title: T\n  slug: t\n  mode: create_new\n  rationale: r\n"
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert entries[0]["kind"] == "adr"


def test_parse_extractor_response_strips_code_fence() -> None:
    raw = (
        "```yaml\nsuggestions:\n  - kind: concept\n    title: T\n    slug: t\n"
        "    mode: create_new\n    rationale: r\n```"
    )
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert entries[0]["slug"] == "t"


def test_parse_extractor_response_unparseable_returns_false() -> None:
    entries, parsed = parse_extractor_response("this is not yaml: : : [")
    assert entries == []
    assert parsed is False


def test_parse_extractor_response_drops_invalid_kind_and_normalizes() -> None:
    raw = (
        "suggestions:\n"
        "  - kind: package\n"          # invalid kind -> dropped
        "    title: Bad\n"
        "    slug: bad\n"
        "    mode: create_new\n"
        "    rationale: r\n"
        "  - kind: architecture\n"
        "    title: Good\n"
        "    slug: 'Good Slug!'\n"      # slugified
        "    mode: bogus\n"            # invalid mode -> create_new
        "    rationale: r2\n"
    )
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert [e["kind"] for e in entries] == ["architecture"]
    assert entries[0]["slug"] == "good-slug"
    assert entries[0]["mode"] == "create_new"
    assert SUGGESTION_KINDS == frozenset({"concept", "adr", "architecture"})


def test_build_curated_vault_index_lists_existing_pages(tmp_path):
    from graph_wiki_core.commands.suggest_pages import build_curated_vault_index

    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "adrs").mkdir(parents=True)
    (wiki / "architecture").mkdir(parents=True)
    (wiki / "sources").mkdir(parents=True)  # must be ignored

    (wiki / "concepts" / "ownership.md").write_text(
        "---\ntitle: Ownership Model\ncategory: concept\nsummary: who owns what\n---\n# x",
        encoding="utf-8",
    )
    (wiki / "adrs" / "0007-md.md").write_text(
        "---\ntitle: 'ADR-0007: Markdown'\ncategory: adr\nsummary: md stays\n---\n# x",
        encoding="utf-8",
    )
    (wiki / "architecture" / "layers.md").write_text(
        "---\ntitle: Layers\nsummary: bottom to top\n---\n# x",
        encoding="utf-8",
    )
    (wiki / "sources" / "spec.md").write_text("---\ntitle: A Spec\n---\n# x", encoding="utf-8")

    index = build_curated_vault_index(wiki)

    by_slug = {e["slug"]: e for e in index}
    assert set(by_slug) == {"ownership", "0007-md", "layers"}
    assert by_slug["ownership"]["kind"] == "concept"
    assert by_slug["ownership"]["title"] == "Ownership Model"
    assert by_slug["ownership"]["summary"] == "who owns what"
    assert by_slug["0007-md"]["kind"] == "adr"
    assert by_slug["layers"]["kind"] == "architecture"
    # sources/ is not curated -> excluded
    assert "spec" not in by_slug


def test_build_curated_vault_index_missing_dirs_returns_empty(tmp_path):
    from graph_wiki_core.commands.suggest_pages import build_curated_vault_index

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    assert build_curated_vault_index(wiki) == []
