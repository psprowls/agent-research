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
