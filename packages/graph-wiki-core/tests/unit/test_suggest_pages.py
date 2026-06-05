from __future__ import annotations

import pytest
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


def test_set_and_read_suggested_pages_round_trip():
    from graph_wiki_core.commands.suggest_pages import (
        read_suggested_pages,
        set_suggested_pages_in_frontmatter,
    )

    page = "---\nsource_kind: source\ntarget_slug: foo\nentity_uri: null\n---\n\nBody text.\n"
    entries = [
        {"kind": "concept", "title": "Sec Ownership", "slug": "sec-ownership",
         "mode": "create_new", "existing_slug": None, "rationale": "why", "status": "proposed"},
    ]
    out = set_suggested_pages_in_frontmatter(page, entries)
    # Other keys + body preserved.
    assert "source_kind: source" in out
    assert "target_slug: foo" in out
    assert out.rstrip().endswith("Body text.")
    # suggested_pages serialized into frontmatter and is the last key.
    assert "suggested_pages:" in out
    fm_block = out.split("---", 2)[1]
    assert fm_block.rstrip().splitlines()[-1].lstrip().startswith("- ") or "suggested_pages:" in fm_block
    # Reading returns the entries back.
    got = read_suggested_pages(out)
    assert got == entries


def test_set_suggested_pages_is_idempotent_and_replaces_block():
    from graph_wiki_core.commands.suggest_pages import set_suggested_pages_in_frontmatter

    page = "---\nsource_kind: source\ntarget_slug: foo\nentity_uri: null\n---\n\nBody.\n"
    entries = [
        {"kind": "adr", "title": "T", "slug": "t", "mode": "create_new",
         "existing_slug": None, "rationale": "r", "status": "proposed"},
    ]
    once = set_suggested_pages_in_frontmatter(page, entries)
    twice = set_suggested_pages_in_frontmatter(once, entries)
    assert once == twice  # byte-stable
    # Replacing with a different set does not duplicate the key.
    other = [
        {"kind": "concept", "title": "U", "slug": "u", "mode": "create_new",
         "existing_slug": None, "rationale": "r2", "status": "approved"},
    ]
    replaced = set_suggested_pages_in_frontmatter(once, other)
    assert replaced.count("suggested_pages:") == 1
    assert "slug: u" in replaced
    assert "slug: t" not in replaced


def test_set_suggested_pages_empty_removes_key():
    from graph_wiki_core.commands.suggest_pages import (
        read_suggested_pages,
        set_suggested_pages_in_frontmatter,
    )

    page = "---\nsource_kind: source\ntarget_slug: foo\n---\nBody.\n"
    entries = [{"kind": "adr", "title": "T", "slug": "t", "mode": "create_new",
                "existing_slug": None, "rationale": "r", "status": "proposed"}]
    with_block = set_suggested_pages_in_frontmatter(page, entries)
    cleared = set_suggested_pages_in_frontmatter(with_block, [])
    assert "suggested_pages:" not in cleared
    assert "source_kind: source" in cleared
    assert read_suggested_pages(cleared) == []


def test_read_suggested_pages_no_frontmatter_returns_empty():
    from graph_wiki_core.commands.suggest_pages import read_suggested_pages

    assert read_suggested_pages("no frontmatter here") == []
    assert read_suggested_pages("---\nsource_kind: source\n---\nBody") == []


def test_render_section_empty_when_no_entries():
    from graph_wiki_core.commands.suggest_pages import render_suggested_pages_section

    assert render_suggested_pages_section([]) == ""


def test_render_section_lists_entries_with_status_and_rationale():
    from graph_wiki_core.commands.suggest_pages import render_suggested_pages_section

    entries = [
        {"kind": "concept", "title": "Sec Ownership", "slug": "sec-ownership",
         "mode": "create_new", "existing_slug": None, "rationale": "a split", "status": "proposed"},
        {"kind": "adr", "title": "MD", "slug": "md", "mode": "update_existing",
         "existing_slug": "0007-md", "rationale": "revisits", "status": "approved"},
    ]
    section = render_suggested_pages_section(entries)
    assert section.startswith("## Suggested pages")
    assert "edit `status`" in section  # the "approve in frontmatter" note
    assert "**concept · create new**" in section
    assert "sec-ownership" in section
    assert "_proposed_" in section
    assert "**adr · update**" in section
    assert "0007-md" in section
    assert "_approved_" in section
    assert "a split" in section


def test_set_section_appends_when_absent():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    body = "---\nsource_kind: source\n---\n\nIntro paragraph.\n"
    section = render_suggested_pages_section(
        [{"kind": "concept", "title": "T", "slug": "t", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    out = set_suggested_pages_section_in_body(body, section)
    assert "Intro paragraph." in out
    assert out.count("## Suggested pages") == 1
    assert out.rstrip().endswith("_proposed_") or "_proposed_" in out


def test_set_section_replaces_existing_and_is_idempotent():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    section1 = render_suggested_pages_section(
        [{"kind": "concept", "title": "One", "slug": "one", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    base = "Intro.\n"
    once = set_suggested_pages_section_in_body(base, section1)
    twice = set_suggested_pages_section_in_body(once, section1)
    assert once == twice
    assert once.count("## Suggested pages") == 1

    section2 = render_suggested_pages_section(
        [{"kind": "adr", "title": "Two", "slug": "two", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    replaced = set_suggested_pages_section_in_body(once, section2)
    assert replaced.count("## Suggested pages") == 1
    assert "Two" in replaced
    assert "One" not in replaced


def test_set_section_removes_when_empty_section():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    section1 = render_suggested_pages_section(
        [{"kind": "concept", "title": "One", "slug": "one", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    body = set_suggested_pages_section_in_body("Intro.\n", section1)
    cleared = set_suggested_pages_section_in_body(body, "")
    assert "## Suggested pages" not in cleared
    assert "Intro." in cleared


def test_set_section_preserves_trailing_h2():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    body = "Intro.\n\n## Suggested pages\n\nold content\n\n## Touches\n\n[[entities/pkg_x]]\n"
    section = render_suggested_pages_section(
        [{"kind": "concept", "title": "T", "slug": "t", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    out = set_suggested_pages_section_in_body(body, section)
    assert "## Touches" in out          # following H2 survives
    assert "[[entities/pkg_x]]" in out
    assert "old content" not in out     # old section body replaced
    assert out.count("## Suggested pages") == 1


@pytest.mark.asyncio
async def test_run_suggest_phase_writes_proposals_to_page(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import read_suggested_pages, run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text(
        "---\nsource_kind: source\ntarget_slug: doc\nentity_uri: null\n---\n\nThe doc body.\n",
        encoding="utf-8",
    )

    llm_yaml = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: A Concept\n"
        "    slug: a-concept\n"
        "    mode: create_new\n"
        "    rationale: justified\n"
    )
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=llm_yaml))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        entries, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert parsed is True
    assert [(e["kind"], e["slug"], e["status"]) for e in entries] == [("concept", "a-concept", "proposed")]
    # Persisted to the page frontmatter + body mirror.
    written = page.read_text(encoding="utf-8")
    assert read_suggested_pages(written) == entries
    assert "## Suggested pages" in written
    assert "a-concept" in written


@pytest.mark.asyncio
async def test_run_suggest_phase_llm_error_is_best_effort(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    original = "---\nsource_kind: source\ntarget_slug: doc\n---\n\nBody.\n"
    page.write_text(original, encoding="utf-8")

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(side_effect=RuntimeError("bedrock boom"))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        entries, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert entries == []
    assert parsed is False
    # Page is intact (no suggested_pages added).
    assert "suggested_pages:" not in page.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_run_suggest_phase_preserves_prior_human_decision(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    # Page already carries an approved suggestion (human edited status).
    page.write_text(
        "---\n"
        "source_kind: source\n"
        "target_slug: doc\n"
        "suggested_pages:\n"
        "- kind: concept\n"
        "  title: Kept\n"
        "  slug: kept\n"
        "  mode: create_new\n"
        "  existing_slug: null\n"
        "  rationale: r\n"
        "  status: approved\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )

    # Re-ingest proposes the SAME key again.
    llm_yaml = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: New Title\n"
        "    slug: kept\n"
        "    mode: create_new\n"
        "    rationale: new\n"
    )
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=llm_yaml))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        entries, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert parsed is True
    kept = [e for e in entries if e["slug"] == "kept"]
    assert len(kept) == 1
    assert kept[0]["status"] == "approved"   # decision preserved
    assert kept[0]["title"] == "Kept"        # not overwritten by the new proposal
