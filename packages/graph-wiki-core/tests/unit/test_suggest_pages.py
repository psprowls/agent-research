from __future__ import annotations

import pytest
from graph_wiki_core.commands.suggest_pages import (
    SUGGESTION_KINDS,
    parse_extractor_response,
)


@pytest.fixture(autouse=True)
def _stub_reasoner():
    from unittest.mock import patch

    from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult

    with patch(
        "graph_wiki_core.commands.suggest_pages.run_proposal_reasoner",
        return_value=ProposalReasonerResult(status="ok", analysis="test reasoner analysis"),
    ):
        yield


async def _run_suggest_phase_for_test(wiki, page):
    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    return await run_suggest_phase(
        wiki=wiki,
        page_path=page,
        source_path=page,
        source_text=page.read_text(encoding="utf-8"),
        entity_uri=None,
        entity_stem=None,
        graph_tools=[],
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
        "  - kind: package\n"  # invalid kind -> dropped
        "    title: Bad\n"
        "    slug: bad\n"
        "    mode: create_new\n"
        "    rationale: r\n"
        "  - kind: architecture\n"
        "    title: Good\n"
        "    slug: 'Good Slug!'\n"  # slugified
        "    mode: bogus\n"  # invalid mode -> create_new
        "    rationale: r2\n"
    )
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert [e["kind"] for e in entries] == ["architecture"]
    assert entries[0]["slug"] == "good-slug"
    assert entries[0]["mode"] == "create_new"
    assert SUGGESTION_KINDS == frozenset({"concept", "adr", "architecture"})


def test_parse_extractor_response_defaults_infinite_rank() -> None:
    raw = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Infinite Rank\n"
        "    slug: infinite-rank\n"
        "    mode: create_new\n"
        "    rank: .inf\n"
        "    rationale: r\n"
    )

    entries, parsed = parse_extractor_response(raw)

    assert parsed is True
    assert entries[0]["rank"] == 999


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


@pytest.mark.asyncio
async def test_run_suggest_phase_writes_ledger_notes_not_page(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from wiki_io.proposals import list_proposals, proposal_path

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text(
        "---\nsource_type: doc\ntarget_slug: doc\nentity_uri: null\n---\n\nThe doc body.\n",
        encoding="utf-8",
    )
    original = page.read_text(encoding="utf-8")

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
        reports, status = await _run_suggest_phase_for_test(wiki, page)

    assert status["reasoner"] == "ok"
    assert status["extractor"] == "ok"
    assert status["proposals"] == 1
    # Report shape includes Task 5 reasoner metadata; slug == target_slug.
    assert reports == [
        {
            "kind": "concept",
            "title": "A Concept",
            "slug": "a-concept",
            "mode": "create_new",
            "rank": 999,
            "confidence": "medium",
            "status": "proposed",
        }
    ]
    # The proposal lives in the ledger, keyed by filename, with an ingest origin.
    note = proposal_path(wiki, "concept", "a-concept")
    assert note.exists()
    rec = list_proposals(wiki)[0]
    assert rec["origins"] == [{"ref": "sources/doc", "source": "ingest", "rationale": "justified"}]
    # The Source page is NOT touched — no suggested_pages, no section.
    assert page.read_text(encoding="utf-8") == original
    assert "suggested_pages" not in original
    assert "## Suggested pages" not in original


@pytest.mark.asyncio
async def test_run_suggest_phase_update_existing_targets_existing_slug(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from wiki_io.proposals import proposal_path

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "adrs").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text("---\ntarget_slug: doc\n---\n\nBody.\n", encoding="utf-8")

    llm_yaml = (
        "suggestions:\n"
        "  - kind: adr\n"
        "    title: Markdown stays canonical\n"
        "    slug: md-idea\n"
        "    mode: update_existing\n"
        "    existing_slug: 0007-md\n"
        "    rationale: revisits the decision\n"
    )
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=llm_yaml))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        reports, status = await _run_suggest_phase_for_test(wiki, page)

    # The note is keyed by the EXISTING slug (the update target), not the proposal slug.
    assert status["extractor"] == "ok"
    assert proposal_path(wiki, "adr", "0007-md").exists()
    assert reports[0]["slug"] == "0007-md"
    assert reports[0]["mode"] == "update_existing"


@pytest.mark.asyncio
async def test_run_suggest_phase_llm_error_writes_zero_notes(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text("---\ntarget_slug: doc\n---\n\nBody.\n", encoding="utf-8")

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(side_effect=RuntimeError("bedrock boom"))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        reports, status = await _run_suggest_phase_for_test(wiki, page)

    assert reports == []
    assert status["reasoner"] == "ok"
    assert status["extractor"] == "failed"
    assert status["error"] == "extractor failed"
    # No notes written; the dir may not even exist.
    assert not list((wiki / "proposals").glob("*.md")) if (wiki / "proposals").is_dir() else True


@pytest.mark.asyncio
async def test_run_suggest_phase_parse_miss_writes_zero_notes(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text("---\ntarget_slug: doc\n---\n\nBody.\n", encoding="utf-8")

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content="not valid yaml: : ["))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        reports, status = await _run_suggest_phase_for_test(wiki, page)

    assert reports == []
    assert status["reasoner"] == "ok"
    assert status["extractor"] == "failed"
    assert status["error"] == "extractor output did not parse"
