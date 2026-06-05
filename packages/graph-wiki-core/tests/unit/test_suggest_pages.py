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


def _prop(kind, slug, title="T", mode="create_new", existing=None, rationale="r"):
    return {
        "kind": kind,
        "title": title,
        "slug": slug,
        "mode": mode,
        "existing_slug": existing,
        "rationale": rationale,
    }


def test_merge_appends_new_as_proposed():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    out = merge_suggested_pages([], [_prop("concept", "a"), _prop("adr", "b")])
    assert [(e["kind"], e["slug"], e["status"]) for e in out] == [
        ("concept", "a", "proposed"),
        ("adr", "b", "proposed"),
    ]


def test_merge_preserves_human_decided_untouched():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    existing = [
        {"kind": "concept", "title": "Kept", "slug": "a", "mode": "create_new",
         "existing_slug": None, "rationale": "old", "status": "approved"},
    ]
    # A new proposal for the SAME key must not re-add or mutate the approved entry.
    out = merge_suggested_pages(existing, [_prop("concept", "a", title="New", rationale="new")])
    assert len(out) == 1
    assert out[0]["status"] == "approved"
    assert out[0]["title"] == "Kept"
    assert out[0]["rationale"] == "old"


def test_merge_refreshes_matching_proposed_in_place():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    existing = [
        {"kind": "concept", "title": "Old", "slug": "a", "mode": "create_new",
         "existing_slug": None, "rationale": "old", "status": "proposed"},
    ]
    out = merge_suggested_pages(existing, [_prop("concept", "a", title="Fresh", rationale="fresh")])
    assert len(out) == 1
    assert out[0]["title"] == "Fresh"
    assert out[0]["rationale"] == "fresh"
    assert out[0]["status"] == "proposed"


def test_merge_preserves_orphaned_proposed():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    existing = [
        {"kind": "concept", "title": "Orphan", "slug": "a", "mode": "create_new",
         "existing_slug": None, "rationale": "r", "status": "proposed"},
    ]
    out = merge_suggested_pages(existing, [_prop("adr", "b")])  # no proposal for 'a'
    keys = [(e["kind"], e["slug"]) for e in out]
    assert ("concept", "a") in keys  # orphan kept
    assert ("adr", "b") in keys


def test_merge_is_idempotent_on_identical_proposals():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    proposals = [_prop("concept", "a"), _prop("adr", "b")]
    once = merge_suggested_pages([], proposals)
    twice = merge_suggested_pages(once, proposals)
    assert once == twice


def test_merge_dedups_duplicate_proposals_by_key():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    out = merge_suggested_pages([], [_prop("concept", "a", title="first"), _prop("concept", "a", title="second")])
    assert len(out) == 1
    assert out[0]["title"] == "first"
