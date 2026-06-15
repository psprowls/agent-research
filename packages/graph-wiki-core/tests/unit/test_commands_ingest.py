"""Unit tests for graph_wiki_core.commands.ingest (Plan 05-05).

Requirements: CMD-03
Tests all public behaviors of run_ingest_source and run_ingest_work_item.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# M3 autouse: defang the extractor LLM for the whole module so existing tests
# never trigger a live Bedrock call from the suggest phase.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_extractor_llm():
    """Defang the M3 suggest phase for the whole module.

    The suggest phase calls make_llm("extractor") in the suggest_pages
    namespace, which the per-test ingest.make_llm patches do NOT cover. Stub it
    to return `suggestions: []` (parsed True, zero proposals) so existing tests
    never hit Bedrock. Tests that assert on suggestions nest their own
    `patch("graph_wiki_core.commands.suggest_pages.make_llm", ...)` inside this
    one, which wins for their duration.
    """
    from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult

    fake = MagicMock()
    fake.ainvoke = AsyncMock(return_value=MagicMock(content="suggestions: []"))
    with (
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake),
        patch(
            "graph_wiki_core.commands.suggest_pages.run_proposal_reasoner",
            return_value=ProposalReasonerResult(status="ok", analysis="test reasoner analysis"),
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Phase 40 graph-seeding helper for ingest tests
# ---------------------------------------------------------------------------


def _seed_graph_db_for_ingest_tests(
    workspace: Path,
    packages: list[tuple[str, str, str | None]],
    extra_nodes: list[tuple[str, str, str | None, str | None]] | None = None,
) -> Path:
    """Create <workspace>/.graph-wiki/code.db with package nodes + (optional) file nodes.

    Each `packages` entry is (name, uri, rel_file_path | None). When rel_file_path
    is supplied, a 'file' node is inserted and a 'contains' edge wires
    package -> file. The URI is written to the dedicated `nodes.uri` column
    (Phase 39 finding: production stores URI in the column, NOT in attrs_json).

    `extra_nodes` lets tests add non-package entity nodes (e.g. class) for the
    name-fallback path. Each entry is (kind, name, path | None, uri | None).

    Returns the DB path.
    """
    from graph_io.store import connect
    from workspace_io.paths import graph_dir

    db = graph_dir(workspace) / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db, create=True)
    try:
        next_id = 1
        for name, uri, rel_path in packages:
            pkg_id = next_id
            next_id += 1
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                "VALUES (?, 'package', ?, NULL, NULL, NULL, ?)",
                (pkg_id, name, uri),
            )
            if rel_path is not None:
                file_id = next_id
                next_id += 1
                conn.execute(
                    "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                    "VALUES (?, 'file', ?, ?, NULL, NULL, NULL)",
                    (file_id, Path(rel_path).name, rel_path),
                )
                conn.execute(
                    "INSERT INTO edges (src, dst, kind, attrs_json) VALUES (?, ?, 'contains', NULL)",
                    (pkg_id, file_id),
                )
        for entry in extra_nodes or []:
            kind, name, path, uri = entry
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) VALUES (?, ?, ?, ?, NULL, NULL, ?)",
                (next_id, kind, name, path, uri),
            )
            next_id += 1
    finally:
        conn.close()
    return db


# ---------------------------------------------------------------------------
# test_run_ingest_source_extracts_and_routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_extracts_and_routes(tmp_path: Path) -> None:
    """Fake ingestor omits source_type so it falls to the doc path-guess; page written under sources/foo.md (M3)."""
    from graph_wiki_core.commands.ingest import IngestResult, run_ingest_source

    # Create a fake source file
    source_file = tmp_path / "my-source.md"
    source_file.write_text("# My Source\n\nSome content here.", encoding="utf-8")

    # Build a fake wiki structure
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    fake_llm_response = "---\ntarget_slug: foo\ntitle: My Source\nsummary: A test concept\n---\n\nBody text here."

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index") as mock_update_index,
        patch("graph_wiki_core.commands.ingest.append_log") as mock_append_log,
    ):
        mock_resolve.return_value = (wiki, tmp_path)

        # Set up fake LLM
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    # M3: every ingested doc lands under sources/.
    expected_page = wiki / "sources" / "foo.md"
    assert expected_page.exists(), f"Expected page at {expected_page}"
    written_body = expected_page.read_text(encoding="utf-8")
    assert "source_type: doc" in written_body
    assert "target_slug: foo" in written_body
    assert "entity_uri: null" in written_body
    assert "Body text here." in written_body

    # update_index and append_log must be called
    mock_update_index.assert_called_once_with(wiki)
    mock_append_log.assert_called_once()

    # IngestResult shape check
    assert isinstance(result, IngestResult)
    assert result.status == "ok"
    assert result.slug == "foo"
    assert result.page_type == "source"
    assert result.source_type == "doc"
    assert result.frontmatter_parsed is True
    assert "sources/foo.md" in result.page_path


# ---------------------------------------------------------------------------
# test_ingest_result_guidance_pages_written_field (Task 4)
# ---------------------------------------------------------------------------


def test_ingest_result_has_guidance_pages_written_field():
    import dataclasses
    import json

    from graph_wiki_core.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="sources/x.md",
        slug="x",
        title="X",
        page_type="source",
        source_path="/tmp/x.md",
        cross_refs_updated=1,
        guidance_pages_written=["wiki/guidance/t/a.md"],
    )
    parsed = json.loads(json.dumps(dataclasses.asdict(result)))
    assert parsed["guidance_pages_written"] == ["wiki/guidance/t/a.md"]


def test_ingest_result_guidance_pages_written_defaults_empty():
    from graph_wiki_core.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="sources/x.md",
        slug="x",
        title="X",
        page_type="source",
        source_path="/tmp/x.md",
        cross_refs_updated=1,
    )
    assert result.guidance_pages_written == []


# ---------------------------------------------------------------------------
# test_run_ingest_source_default_slug_from_title
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_default_slug_from_title(tmp_path: Path) -> None:
    """When LLM frontmatter omits target_slug, falls back to slugified title."""
    from graph_wiki_core.commands.ingest import IngestResult, run_ingest_source

    source_file = tmp_path / "my-source.md"
    source_file.write_text("# My Cool Source\n\nContent.", encoding="utf-8")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    # LLM response: no target_slug, but page_type=concept
    fake_llm_response = "---\npage_type: concept\ntitle: My Cool Source\ncategory: concept\nsummary: Cool\n---\n\nBody."

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    # Slug falls back to slugified title ("my-cool-source")
    assert result.slug == "my-cool-source"
    assert isinstance(result, IngestResult)


# ---------------------------------------------------------------------------
# test_run_ingest_work_item_validates_required_fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_work_item_validates_required_fields(tmp_path: Path) -> None:
    """Pass YAML missing 'affects' — ValueError raised with 'affects' in message."""
    from graph_wiki_core.commands.ingest import run_ingest_work_item

    # Missing 'affects' field
    frontmatter_text = (
        "title: Fix Auth Bug\ncategory: work\nkind: bug\nstatus: open\nsummary: Fix the auth bug\nopened: 2026-05-14\n"
    )

    wiki = tmp_path / "wiki"
    wiki.mkdir()

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
    ):
        mock_resolve.return_value = (wiki, tmp_path)

        with pytest.raises(ValueError) as exc_info:
            await run_ingest_work_item(frontmatter_text, "Some body.", workspace_path=wiki)

    assert "affects" in str(exc_info.value)


# ---------------------------------------------------------------------------
# test_run_ingest_work_item_writes_to_workspace_work_dir
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_work_item_writes_page_sidecar_index_and_log(tmp_path: Path) -> None:
    """Valid YAML: page lands at wiki/work/<opened>-<slug>.md; sidecar regen runs;
    update_index + append_log invoked because index.md + log.md are present."""
    from graph_wiki_core.commands.ingest import IngestResult, run_ingest_work_item

    frontmatter_text = (
        "title: Fix Auth Bug\n"
        "category: work\n"
        "kind: bug\n"
        "status: open\n"
        "summary: Fix the auth bug\n"
        "opened: 2026-05-14\n"
        "affects:\n"
        "  - auth-service\n"
    )

    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "index.md").write_text("", encoding="utf-8")
    (wiki / "log.md").write_text("", encoding="utf-8")

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.work.resolve_wiki_and_repo") as mock_resolve_work,
        patch("graph_wiki_core.commands.work.update_index") as mock_ui,
        patch("graph_wiki_core.commands.work.append_log") as mock_al,
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        mock_resolve_work.return_value = (wiki, tmp_path)
        result = await run_ingest_work_item(frontmatter_text, "Some body.", workspace_path=workspace)

    assert isinstance(result, IngestResult)
    assert result.page_type == "work"
    assert result.status == "ok"
    assert result.slug == "fix-auth-bug"
    assert "2026-05-14-fix-auth-bug" in result.page_path
    assert (wiki / "work" / "2026-05-14-fix-auth-bug.md").exists()
    # Unified side-effects: sidecar regenerated, index + log invoked.
    assert (wiki / "work-index.json").exists()
    mock_ui.assert_called_once_with(wiki)
    mock_al.assert_called_once()


# ---------------------------------------------------------------------------
# test_run_ingest_work_item_invokes_file_work_item_with_force
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_work_item_force_overwrites_existing_page(tmp_path: Path) -> None:
    """force=True overwrites an existing work page; force=False raises FileExistsError."""
    from graph_wiki_core.commands.ingest import run_ingest_work_item

    frontmatter_text = (
        "title: Some Item\n"
        "category: work\n"
        "kind: task\n"
        "status: open\n"
        "summary: A task\n"
        "opened: 2026-05-14\n"
        "affects:\n"
        "  - backend\n"
    )

    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.work.resolve_wiki_and_repo") as mock_resolve_work,
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        mock_resolve_work.return_value = (wiki, tmp_path)

        await run_ingest_work_item(frontmatter_text, "Body one.", workspace_path=workspace)
        # Without force, a second file of the same slug/date raises.
        with pytest.raises(FileExistsError):
            await run_ingest_work_item(frontmatter_text, "Body two.", workspace_path=workspace)
        # With force, it overwrites.
        result = await run_ingest_work_item(frontmatter_text, "Body two.", force=True, workspace_path=workspace)

    assert result.status == "ok"
    page = wiki / "work" / "2026-05-14-some-item.md"
    assert "Body two." in page.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# test_ingest_result_round_trips_to_json
# ---------------------------------------------------------------------------


def test_ingest_result_round_trips_to_json() -> None:
    """IngestResult serializes to JSON without error; new fields have honest defaults."""
    from graph_wiki_core.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="sources/foo.md",
        slug="foo",
        title="Foo",
        page_type="source",
        source_path="/some/path/foo.md",
        cross_refs_updated=1,
    )

    # Defaults for the M3 fields
    assert result.source_type is None
    assert result.stripped_wikilinks == []
    assert result.frontmatter_parsed is True

    # Should not raise; new fields serialize cleanly
    serialized = json.dumps(dataclasses.asdict(result))
    parsed = json.loads(serialized)

    assert parsed["status"] == "ok"
    assert parsed["slug"] == "foo"
    assert parsed["page_type"] == "source"
    assert parsed["cross_refs_updated"] == 1
    assert parsed["source_type"] is None
    assert parsed["stripped_wikilinks"] == []
    assert parsed["frontmatter_parsed"] is True


# ---------------------------------------------------------------------------
# _parse_ingestor_response — fence-stripping defense (Plan 06-12 / UAT G1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected_fm,expected_body",
    [
        # Bare --- (must still work — regression guard)
        (
            "---\npage_type: source\ntarget_slug: foo\n---\nBody text.",
            {"page_type": "source", "target_slug": "foo"},
            "Body text.",
        ),
        # ```yaml fenced (UAT G1)
        (
            "```yaml\n---\npage_type: source\ntarget_slug: foo\n---\n```\n\nBody text.",
            {"page_type": "source", "target_slug": "foo"},
            "Body text.",
        ),
        # ``` (no language tag) fenced
        (
            "```\n---\npage_type: source\ntarget_slug: foo\n---\n```\nBody text.",
            {"page_type": "source", "target_slug": "foo"},
            "Body text.",
        ),
    ],
)
def test_parse_ingestor_response_handles_fenced_and_unfenced(raw: str, expected_fm: dict, expected_body: str) -> None:
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    fm, body = _parse_ingestor_response(raw)
    for k, v in expected_fm.items():
        assert fm.get(k) == v, f"key {k}: expected {v}, got {fm.get(k)}"
    assert body.strip() == expected_body.strip()


def test_parse_ingestor_response_no_frontmatter_returns_empty() -> None:
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    fm, body = _parse_ingestor_response("just some text, no frontmatter")
    assert fm == {}
    assert body == "just some text, no frontmatter"


def test_parse_ingestor_response_fence_without_dashes_returns_empty() -> None:
    """Fence present but no --- inside: treat as no-frontmatter, do not
    silently strip the fence and succeed on a non-YAML body."""
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    raw = "```yaml\nkey: value\nno_dashes: here\n```"
    fm, body = _parse_ingestor_response(raw)
    assert fm == {}, f"expected empty dict, got {fm}"


@pytest.mark.asyncio
async def test_run_suggest_phase_uses_reasoner_analysis(tmp_path: Path) -> None:
    from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult
    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    wiki = tmp_path / "wiki"
    page = wiki / "sources" / "spec.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\ntitle: Spec\ncategory: source\n---\n\nSummary.", encoding="utf-8")

    extractor = MagicMock()
    extractor.ainvoke = AsyncMock(
        return_value=MagicMock(
            content=(
                "suggestions:\n"
                "  - kind: concept\n"
                "    title: Better Ingest\n"
                "    slug: better-ingest\n"
                "    mode: create_new\n"
                "    existing_slug:\n"
                "    rank: 1\n"
                "    confidence: high\n"
                "    rationale: The reasoner found a durable ingest pattern.\n"
                "    evidence:\n"
                "      - Full document evidence.\n"
                "    existing_pages_considered: []\n"
                "    reasoning_summary: Create a focused concept.\n"
                "    potential_conflicts: []\n"
                "    implementation_notes:\n"
                "      - Link to the source page.\n"
            )
        )
    )

    with (
        patch(
            "graph_wiki_core.commands.suggest_pages.run_proposal_reasoner",
            return_value=ProposalReasonerResult(status="ok", analysis="rich reasoner analysis"),
        ) as reasoner,
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor),
    ):
        reports, status = await run_suggest_phase(
            wiki=wiki,
            page_path=page,
            source_path=tmp_path / "raw.md",
            source_text="full raw document",
            entity_uri=None,
            entity_stem=None,
            graph_tools=[],
        )

    reasoner.assert_called_once()
    assert status["reasoner"] == "ok"
    assert status["extractor"] == "ok"
    assert reports[0]["slug"] == "better-ingest"


# ---------------------------------------------------------------------------
# page_type=source routing + target_slug-filename equality (Plan 06-13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_routes_source_to_sources_dir(tmp_path: Path) -> None:
    """Fake ingestor returns page_type=source; page lands under sources/foo.md."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    source_file = tmp_path / "an-article.md"
    source_file.write_text("# An Article\n\nBody.", encoding="utf-8")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    fake_llm_response = (
        "---\n"
        "title: An Article\n"
        "category: source\n"
        "page_type: source\n"
        "target_slug: an-article\n"
        "summary: A test source\n"
        "---\n"
        "\n"
        "Body text here."
    )

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    expected_page = wiki / "sources" / "an-article.md"
    assert expected_page.exists(), f"expected page at {expected_page}, got result={result}"
    assert (wiki / "concepts").exists() is False or not any((wiki / "concepts").iterdir()), (
        "concepts/ should be empty for page_type=source"
    )
    assert result.page_type == "source"
    assert "sources/an-article.md" in result.page_path
    assert result.slug == "an-article"


@pytest.mark.asyncio
async def test_run_ingest_source_target_slug_matches_filename(tmp_path: Path) -> None:
    """LLM emits a slug that slugify() transforms; frontmatter target_slug
    in the written file must equal the on-disk filename slug."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    source_file = tmp_path / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    # LLM emits a slug with characters that slugify() would normalize.
    # We use a slug that survives slugify() unchanged for determinism,
    # then assert the rewrite step copies it into the body verbatim.
    # (The real-world G3 case was a slug that DIVERGED from the title-
    # derived slug; the test below covers the rewrite path explicitly.)
    fake_llm_response = (
        "---\n"
        "title: Some Page\n"
        "category: concept\n"
        "page_type: concept\n"
        "target_slug: weird_slug_with_underscores\n"  # slugify -> weird-slug-with-underscores
        "summary: x\n"
        "---\n"
        "Body."
    )

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    # Determine the actual on-disk path; assert filename slug == body target_slug
    written_path = wiki / "sources" / f"{result.slug}.md"
    assert written_path.exists(), f"expected page at {written_path}"
    written_body = written_path.read_text(encoding="utf-8")
    assert f"target_slug: {result.slug}" in written_body, (
        f"target_slug in body must equal filename stem '{result.slug}'; body excerpt:\n{written_body[:300]}"
    )
    # And the original LLM slug (pre-slugify) should NOT survive verbatim
    assert "target_slug: weird_slug_with_underscores" not in written_body


# ---------------------------------------------------------------------------
# _resolve_wikilinks unit tests (Plan 06-14)
# ---------------------------------------------------------------------------


def test_resolve_wikilinks_strips_unresolved(tmp_path: Path) -> None:
    from graph_wiki_core.commands.ingest import _resolve_wikilinks

    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "real-page.md").write_text("# Real", encoding="utf-8")

    text = "See [[real-page]] and [[fake-person]] for context."
    out, stripped = _resolve_wikilinks(text, wiki)
    assert "[[real-page]]" in out
    assert "[[fake-person]]" not in out
    assert "fake-person" in out  # label preserved
    assert stripped == ["fake-person"]


def test_resolve_wikilinks_resolves_subdir_qualified(tmp_path: Path) -> None:
    from graph_wiki_core.commands.ingest import _resolve_wikilinks

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "sources" / "otel-story.md").write_text("# OTel", encoding="utf-8")

    # The UAT G4 case form: [[sources/otel-story]]
    text = "Per [[sources/otel-story]] the trace is propagated…"
    out, stripped = _resolve_wikilinks(text, wiki)
    assert "[[sources/otel-story]]" in out
    assert stripped == []


def test_resolve_wikilinks_preserves_fenced_code(tmp_path: Path) -> None:
    from graph_wiki_core.commands.ingest import _resolve_wikilinks

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    text = (
        "Outside [[fake-page]] is stripped.\n"
        "\n"
        "```\n"
        "Inside [[fake-page]] is preserved.\n"
        "```\n"
        "After [[also-fake]] is stripped.\n"
    )
    out, stripped = _resolve_wikilinks(text, wiki)
    # The fenced occurrence is verbatim
    assert "Inside [[fake-page]] is preserved." in out
    # The unfenced occurrences are stripped
    assert "[[fake-page]]" not in out.replace("Inside [[fake-page]] is preserved.", "")
    assert "[[also-fake]]" not in out
    # Only the two unfenced unresolved targets are reported
    assert sorted(stripped) == ["also-fake", "fake-page"]


@pytest.mark.asyncio
async def test_run_ingest_source_strips_unresolved_wikilinks(tmp_path: Path) -> None:
    """End-to-end: ingestor emits a hallucinated wikilink; written file
    on disk has it stripped; append_log detail records the count."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    source_file = tmp_path / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "real-thing.md").write_text("# Real", encoding="utf-8")
    (wiki / "log.md").write_text("", encoding="utf-8")

    fake_llm_response = (
        "---\n"
        "title: My Page\n"
        "category: concept\n"
        "page_type: concept\n"
        "target_slug: my-page\n"
        "summary: x\n"
        "---\n"
        "Refers to [[real-thing]] and to [[Hallucinated Person]]."
    )

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log") as mock_append_log,
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    written = (wiki / "sources" / "my-page.md").read_text(encoding="utf-8")
    assert "[[real-thing]]" in written
    assert "[[Hallucinated Person]]" not in written
    assert "Hallucinated Person" in written  # label preserved
    # append_log was called with a detail recording the strip count
    call_args = mock_append_log.call_args
    detail = call_args.kwargs.get("detail") or (call_args.args[3] if len(call_args.args) >= 4 else "")
    assert "stripped 1" in detail or "stripped 1 unresolved" in detail
    assert result.page_type == "source"
    assert result.stripped_wikilinks == ["Hallucinated Person"]


# ===========================================================================
# Phase 40: graph-io integration tests (INGESTOR-01, INGESTOR-02)
# ===========================================================================

_FM_TEMPLATE = (
    "---\ntitle: {title}\ncategory: {category}\npage_type: {page_type}\ntarget_slug: {slug}\nsummary: x\n---\nBody."
)


def _build_workspace_with_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a workspace dir, a sibling wiki dir, and a repo root.

    Returns (workspace, wiki, repo). workspace == repo for these tests so
    that source files placed under workspace/<rel_path> are relative to the
    repo root as the graph stores them.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    return workspace, wiki, workspace


# ---------------------------------------------------------------------------
# Test: NOT_INITIALIZED — typed exception raised, LLM never invoked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_not_initialized_raises_typed_exception(
    tmp_path: Path,
) -> None:
    """Missing .graph-wiki/code.db → IngestorGraphNotInitializedError; LLM not invoked."""
    from graph_wiki_core.commands.ingest import (
        IngestorGraphNotInitializedError,
        run_ingest_source,
    )

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")

    # Do NOT create workspace/.graph-wiki/code.db — that is the test scenario.

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        # Record any LLM construction attempt — none should happen.
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content="never"))
        mock_make_llm.return_value = fake_llm

        with pytest.raises(IngestorGraphNotInitializedError) as exc_info:
            await run_ingest_source(source_file, workspace)

    msg = str(exc_info.value)
    assert "graph-io not initialized for this workspace" in msg
    assert "Run 'gw graph build'" in msg
    assert "graph-wiki-core graph build" not in msg
    assert mock_make_llm.call_count == 0, (
        f"LLM must NOT be invoked on NOT_INITIALIZED path; was called {mock_make_llm.call_count}x"
    )
    assert fake_llm.ainvoke.call_count == 0


# ---------------------------------------------------------------------------
# Slice 4: path match routes to sources/, links entity, never packages/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_path_match_links_entity_never_packages(
    tmp_path: Path,
) -> None:
    """Slice 4: a path-matched package routes to sources/ (never packages/),
    sets entity_uri, and embeds a [[entities/pkg_<name>]] wikilink whose target
    equals short_filename for the URI. The slug is NOT forced from the URI."""
    from graph_wiki_core.commands.ingest import run_ingest_source
    from wiki_io.entity_writer import short_filename

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    rel_path = "packages/graph-io/src/graph_io/store.py"
    source_file = workspace / rel_path
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# store\n\nBody.", encoding="utf-8")

    canonical_uri = "pkg:agent-research/agent-research/graph-io"
    _seed_graph_db_for_ingest_tests(workspace, packages=[("graph-io", canonical_uri, rel_path)])

    # LLM picks page_type=source with a clean slug; entity match must NOT
    # override it (decoupled).
    fake_llm_response = _FM_TEMPLATE.format(
        title="Store",
        category="source",
        page_type="source",
        slug="2026-06-store",
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    # Never the legacy packages/ folder.
    assert not (wiki / "packages").exists()
    stem = short_filename(canonical_uri, frozenset())  # "pkg_graph-io"
    expected_page = wiki / "sources" / "2026-06-store.md"
    assert expected_page.exists(), f"expected page at {expected_page}"
    body = expected_page.read_text(encoding="utf-8")
    assert f"entity_uri: {canonical_uri}" in body
    assert f"[[entities/{stem}]]" in body
    assert result.page_type == "source"
    assert result.slug == "2026-06-store"  # LLM slug preserved, not URI tail
    assert result.entity_uri == canonical_uri


# ---------------------------------------------------------------------------
# Test: name match sets URI without entity link (cls: has no entity page)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_name_match_sets_uri_without_entity_link(
    tmp_path: Path,
) -> None:
    """Slice 4: a name-matched class (cls: URI, no entity page) sets entity_uri
    but writes NO [[entities/...]] link and does NOT force the slug."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "random" / "src.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# SubagentPool\n\nBody.", encoding="utf-8")

    canonical_uri = "cls:subagent_runtime.pool.SubagentPool"
    _seed_graph_db_for_ingest_tests(
        workspace,
        packages=[],
        extra_nodes=[("class", "SubagentPool", None, canonical_uri)],
    )

    fake_llm_response = _FM_TEMPLATE.format(
        title="SubagentPool",
        category="concept",
        page_type="concept",
        slug="some-other-thing",
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert result.entity_uri == canonical_uri
    assert result.slug == "some-other-thing"  # LLM slug preserved (no forcing)
    written = (wiki / "sources" / "some-other-thing.md").read_text(encoding="utf-8")
    assert f"entity_uri: {canonical_uri}" in written
    assert "[[entities/" not in written  # cls: has no entity page → no link


# ---------------------------------------------------------------------------
# Test: no match writes entity_uri: null
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_no_match_writes_null_entity_uri(
    tmp_path: Path,
) -> None:
    """Empty graph DB → entity_uri is None and body has 'entity_uri: null'."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")

    # Empty graph — schema exists, no entity rows.
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    fake_llm_response = _FM_TEMPLATE.format(
        title="My Thing",
        category="concept",
        page_type="concept",
        slug="my-thing",
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert result.entity_uri is None
    written = (wiki / "sources" / "my-thing.md").read_text(encoding="utf-8")
    assert "entity_uri: null" in written


# ---------------------------------------------------------------------------
# Test: multi-match → stderr warning + treat as no match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_multi_match_warns_and_falls_back(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Multiple entity-kind nodes named 'Helper' → stderr warn + entity_uri null."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "src.md"
    source_file.write_text("# Helper\n\nBody.", encoding="utf-8")

    _seed_graph_db_for_ingest_tests(
        workspace,
        packages=[],
        extra_nodes=[
            ("class", "Helper", "packages/a/src/a/helper.py", "cls:agent-research/a/Helper"),
            ("class", "Helper", "packages/b/src/b/helper.py", "cls:agent-research/b/Helper"),
        ],
    )

    fake_llm_response = _FM_TEMPLATE.format(
        title="Helper",
        category="concept",
        page_type="concept",
        slug="helper",
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    captured = capsys.readouterr()
    assert "matches multiple graph nodes" in captured.err
    written = (wiki / "sources" / "helper.md").read_text(encoding="utf-8")
    assert "entity_uri: null" in written
    assert result.entity_uri is None


# ---------------------------------------------------------------------------
# Test: conn closed even when LLM raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_closes_conn_on_exception(tmp_path: Path) -> None:
    """conn.close() is called in finally even if ainvoke raises."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    recorded_conn = MagicMock(spec=sqlite3.Connection)
    recorded_conn.execute.return_value.fetchone.return_value = None
    recorded_conn.execute.return_value.fetchall.return_value = []

    class _Boom(RuntimeError):
        pass

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.read_only_connect") as mock_connect,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
        patch("graph_wiki_core.commands.ingest.queries") as mock_queries,
    ):
        mock_resolve.return_value = (wiki, repo)
        mock_connect.return_value = recorded_conn
        mock_queries.find.return_value = []
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(side_effect=_Boom("llm fail"))
        mock_make_llm.return_value = fake_llm

        with pytest.raises(_Boom):
            await run_ingest_source(source_file, workspace)

    recorded_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test: _set_entity_uri_in_body — body rewriter (unit-level)
# ---------------------------------------------------------------------------


def test_set_entity_uri_in_body_inserts_after_target_slug() -> None:
    from graph_wiki_core.commands.ingest import _set_entity_uri_in_body

    text = "---\ntarget_slug: foo\ntitle: Foo\n---\n\nBody"
    out = _set_entity_uri_in_body(text, "pkg:x/y/foo")
    assert "target_slug: foo\nentity_uri: pkg:x/y/foo\n" in out

    # None → null literal
    out_null = _set_entity_uri_in_body(text, None)
    assert "entity_uri: null" in out_null

    # Idempotence: calling twice yields exactly one entity_uri: line
    twice = _set_entity_uri_in_body(out, "pkg:x/y/foo")
    assert twice.count("entity_uri:") == 1

    # No target_slug: in frontmatter → entity_uri inserted at top
    no_slug = "---\ntitle: Foo\n---\n\nBody"
    out2 = _set_entity_uri_in_body(no_slug, "pkg:x/y/foo")
    # First frontmatter line after the opening --- should be entity_uri
    lines = out2.splitlines()
    assert lines[0] == "---"
    assert lines[1] == "entity_uri: pkg:x/y/foo"


# ---------------------------------------------------------------------------
# Test: _ensure_entity_touch_link — entity forward-link injector (unit-level)
# ---------------------------------------------------------------------------


def test_ensure_entity_touch_link_inserts_under_existing_heading() -> None:
    from graph_wiki_core.commands.ingest import _ensure_entity_touch_link

    text = "---\ntitle: Foo\n---\n\nBody text.\n\n## Touches\n- [[entities/pkg_other]]\n"
    out = _ensure_entity_touch_link(text, "pkg_graph-io")
    # New bullet inserted immediately under the heading.
    assert "## Touches\n- [[entities/pkg_graph-io]]\n" in out
    # Pre-existing bullet under the heading is preserved.
    assert "- [[entities/pkg_other]]" in out


def test_ensure_entity_touch_link_appends_section_when_absent() -> None:
    from graph_wiki_core.commands.ingest import _ensure_entity_touch_link

    text = "---\ntitle: Foo\n---\n\nBody text.\n"
    out = _ensure_entity_touch_link(text, "pkg_graph-io")
    # Original content preserved.
    assert out.startswith(text)
    # A Touches section is appended with the link bullet.
    assert "## Touches\n- [[entities/pkg_graph-io]]\n" in out


def test_ensure_entity_touch_link_idempotent() -> None:
    from graph_wiki_core.commands.ingest import _ensure_entity_touch_link

    text = "---\ntitle: Foo\n---\n\nRefers to [[entities/pkg_graph-io]] inline.\n"
    out = _ensure_entity_touch_link(text, "pkg_graph-io")
    # Link already present anywhere → text returned unchanged.
    assert out == text


def test_parse_ingestor_response_uses_safe_load_for_valid_yaml() -> None:
    """Clean YAML is parsed (typed) via yaml.safe_load."""
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    raw = "---\nsource_type: source\ntarget_slug: foo\ntags:\n  - a\n  - b\n---\nBody."
    fm, body = _parse_ingestor_response(raw)
    assert fm["source_type"] == "source"
    assert fm["target_slug"] == "foo"
    assert fm["tags"] == ["a", "b"]  # safe_load yields a real list
    assert body.strip() == "Body."

    # A typed scalar only safe_load (not the hand-rolled parser) produces:
    raw_bool = "---\nsource_type: source\ntarget_slug: foo\nactive: true\n---\nBody."
    fm_bool, _ = _parse_ingestor_response(raw_bool)
    assert fm_bool["active"] is True


def test_parse_ingestor_response_falls_back_to_handrolled_on_yaml_error() -> None:
    """An unquoted colon in a value makes safe_load raise; the hand-rolled
    parser recovers the value verbatim."""
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    # `summary: foo: bar baz` -> safe_load raises ScannerError (a YAMLError);
    # hand-rolled partition-on-first-colon recovers val="foo: bar baz".
    raw = "---\nsource_type: source\ntarget_slug: foo\nsummary: foo: bar baz\n---\nBody."
    fm, body = _parse_ingestor_response(raw)
    assert fm["source_type"] == "source"
    assert fm["target_slug"] == "foo"
    assert fm["summary"] == "foo: bar baz"
    assert body.strip() == "Body."


def test_parse_ingestor_response_empty_block_returns_empty_dict() -> None:
    """A frontmatter block with no parseable keys returns ({}, body)."""
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    raw = "---\n# only a comment\n---\nBody."
    fm, body = _parse_ingestor_response(raw)
    assert fm == {}
    assert body.strip() == "Body."


def test_set_source_type_in_body_inserts_and_is_idempotent() -> None:
    from graph_wiki_core.commands.ingest import _set_source_type_in_body

    text = "---\ntarget_slug: foo\n---\nBody."
    out = _set_source_type_in_body(text, "note")
    lines = out.splitlines()
    assert lines[0] == "---"
    assert lines[1] == "source_type: note"
    # Idempotence: calling twice yields exactly one source_type: line.
    twice = _set_source_type_in_body(out, "spec")
    assert twice.count("source_type:") == 1
    assert "source_type: spec" in twice
    # No-frontmatter: returns text unchanged.
    assert _set_source_type_in_body("no frontmatter here", "note") == "no frontmatter here"


def test_set_source_path_in_body_replaces_in_place_and_is_idempotent() -> None:
    from graph_wiki_core.commands.ingest import _set_source_path_in_body

    text = "---\ntitle: X\nsource_path: raw/specs/x.md\nsource_type: spec\n---\n\nBody\n"
    out = _set_source_path_in_body(text, "raw/_archive/specs/x.md")
    assert "source_path: raw/_archive/specs/x.md" in out
    assert "raw/specs/x.md" not in out
    assert out.index("title:") < out.index("source_path:") < out.index("source_type:")
    assert _set_source_path_in_body(out, "raw/_archive/specs/x.md") == out


def test_set_source_path_in_body_inserts_when_absent() -> None:
    from graph_wiki_core.commands.ingest import _set_source_path_in_body

    text = "---\ntitle: X\n---\n\nBody\n"
    out = _set_source_path_in_body(text, "raw/_archive/specs/x.md")
    assert "source_path: raw/_archive/specs/x.md" in out


def test_set_source_path_in_body_no_frontmatter_passthrough() -> None:
    from graph_wiki_core.commands.ingest import _set_source_path_in_body

    assert _set_source_path_in_body("no frontmatter", "raw/_archive/x.md") == "no frontmatter"


# ---------------------------------------------------------------------------
# M3: always-Source routing even when the LLM claims adr/concept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_always_routes_to_sources_even_if_llm_says_adr(
    tmp_path: Path,
) -> None:
    """An LLM response claiming page_type: adr still lands under sources/."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "src.md"
    source_file.write_text("# A Decision\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # LLM claims adr (page_type ignored — every ingest lands under sources/).
    fake_llm_response = "---\ntitle: A Decision\npage_type: adr\ntarget_slug: a-decision\nsummary: x\n---\nBody."

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert (wiki / "sources" / "a-decision.md").exists()
    assert not (wiki / "adrs").exists() or not any((wiki / "adrs").iterdir())
    assert result.page_type == "source"
    assert result.source_type == "doc"
    assert result.frontmatter_parsed is True
    assert "sources/a-decision.md" in result.page_path


@pytest.mark.asyncio
async def test_run_ingest_source_no_frontmatter_synthesizes_path_guess(
    tmp_path: Path,
) -> None:
    """LLM emits a body with NO frontmatter -> synthesized block lands with
    source_type: doc (the path-guess), target_slug + entity_uri present, frontmatter_parsed False."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "raw-notes.md"
    source_file.write_text("# Raw Notes\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # No --- block at all.
    fake_llm_response = "Just some prose the model emitted, no frontmatter whatsoever."

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    # Slug falls back to slugify(title) == "raw-notes".
    written = (wiki / "sources" / "raw-notes.md").read_text(encoding="utf-8")
    assert "source_type: doc" in written
    assert "target_slug: raw-notes" in written  # synthesis ran BEFORE the body helpers
    assert "entity_uri: null" in written
    assert "Just some prose" in written
    assert result.page_type == "source"
    assert result.source_type == "doc"
    assert result.frontmatter_parsed is False
    assert "sources/raw-notes.md" in result.page_path


# ---------------------------------------------------------------------------
# Source-type determination (source-type-consolidation design 2026-06-05)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_raw_folder_type_is_authoritative(tmp_path: Path) -> None:
    """A source under raw/specs/ is stamped source_type: spec; a contrary LLM
    value is ignored (raw/<type>/ folders are authoritative)."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "raw" / "specs" / "auth.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("# Auth Spec\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # The LLM tries to call it an article — must be ignored.
    fake_llm_response = "---\nsource_type: article\ntarget_slug: auth\ntitle: Auth\nsummary: x\n---\nBody."

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm
        result = await run_ingest_source(source_file, workspace)

    written = (wiki / "sources" / "auth.md").read_text(encoding="utf-8")
    assert "source_type: spec" in written
    assert "source_type: article" not in written
    assert result.source_type == "spec"


@pytest.mark.asyncio
async def test_run_ingest_source_llm_overrides_non_raw_type(tmp_path: Path) -> None:
    """For an in-repo doc (path-guess 'doc'), the LLM may override the type with
    a more specific enum value."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "notes.md"  # in-repo, NOT under raw/
    source_file.write_text("# Notes\n\nA meeting transcript.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    fake_llm_response = "---\nsource_type: transcript\ntarget_slug: notes\ntitle: Notes\nsummary: x\n---\nBody."

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm
        result = await run_ingest_source(source_file, workspace)

    written = (wiki / "sources" / "notes.md").read_text(encoding="utf-8")
    assert "source_type: transcript" in written
    assert result.source_type == "transcript"


@pytest.mark.asyncio
async def test_run_ingest_source_falls_back_to_path_guess_on_bad_llm_type(tmp_path: Path) -> None:
    """An out-of-enum or absent LLM source_type falls back to the path-guess:
    'doc' for an in-repo file, 'note' for a loose file under neither workspace
    nor repo."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # (a) in-repo file, LLM returns out-of-enum garbage -> doc
    in_repo = workspace / "doc.md"
    in_repo.write_text("# Doc\n\nBody.", encoding="utf-8")
    resp_garbage = "---\nsource_type: nonsense\ntarget_slug: doc\ntitle: Doc\nsummary: x\n---\nBody."
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=resp_garbage))
        mock_make_llm.return_value = fake_llm
        result_doc = await run_ingest_source(in_repo, workspace)
    assert result_doc.source_type == "doc"
    assert "source_type: doc" in (wiki / "sources" / "doc.md").read_text(encoding="utf-8")

    # (b) loose file outside workspace+repo, LLM omits source_type -> note
    loose = tmp_path / "outside" / "loose.md"
    loose.parent.mkdir(parents=True)
    loose.write_text("# Loose\n\nBody.", encoding="utf-8")
    resp_empty = "---\ntarget_slug: loose\ntitle: Loose\nsummary: x\n---\nBody."
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=resp_empty))
        mock_make_llm.return_value = fake_llm
        result_note = await run_ingest_source(loose, workspace)
    assert result_note.source_type == "note"
    assert "source_type: note" in (wiki / "sources" / "loose.md").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_run_ingest_source_surfaces_stripped_wikilinks_in_result(
    tmp_path: Path,
) -> None:
    """Hallucinated [[links]] are reported in IngestResult.stripped_wikilinks."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "real-thing.md").write_text("# Real", encoding="utf-8")
    source_file = workspace / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    fake_llm_response = (
        "---\n"
        "title: My Page\n"
        "target_slug: my-page\n"
        "summary: x\n"
        "---\n"
        "Refers to [[real-thing]] and to [[Hallucinated Person]]."
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert result.stripped_wikilinks == ["Hallucinated Person"]
    assert result.frontmatter_parsed is True
    assert result.source_type == "doc"


# ---------------------------------------------------------------------------
# M3 suggestion step: inline suggest phase wired into run_ingest_source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_writes_ledger_notes(tmp_path: Path) -> None:
    """A clean ingest records proposals in proposals/ + in IngestResult; the
    Source page carries no suggested_pages and no ## Suggested pages section."""
    from graph_wiki_core.commands.ingest import run_ingest_source
    from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult
    from wiki_io.proposals import proposal_path

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nA cross-cutting idea.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = "---\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."
    extractor_response = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Cross Cutting Idea\n"
        "    slug: cross-cutting-idea\n"
        "    mode: create_new\n"
        "    rationale: The source defines it.\n"
    )

    ingestor_llm = MagicMock()
    ingestor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm = MagicMock()
    extractor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch(
            "graph_wiki_core.commands.suggest_pages.run_proposal_reasoner",
            return_value=ProposalReasonerResult(status="ok", analysis="reasoned candidates"),
        ),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        result = await run_ingest_source(source_file, workspace)

    # Report shape includes the Task 5 rank/confidence proposal contract.
    assert result.suggestions_parsed is True
    assert [(s["kind"], s["slug"], s["status"]) for s in result.suggested_pages] == [
        ("concept", "cross-cutting-idea", "proposed")
    ]
    assert set(result.suggested_pages[0]) == {"kind", "title", "slug", "mode", "rank", "confidence", "status"}
    assert result.suggested_pages[0]["rank"] == 999
    assert result.suggested_pages[0]["confidence"] == "medium"
    # Storage moved to the ledger.
    assert proposal_path(wiki, "concept", "cross-cutting-idea").exists()
    # The Source page is clean.
    written = (wiki / "sources" / "spec.md").read_text(encoding="utf-8")
    assert "suggested_pages" not in written
    assert "## Suggested pages" not in written
    assert "proposal_status:" in written
    assert "  reasoner: ok" in written
    assert "  extractor: ok" in written
    assert result.proposal_reasoner_status == "ok"
    assert result.proposal_extractor_status == "ok"


@pytest.mark.asyncio
async def test_run_ingest_source_suggest_degraded_is_nonfatal(tmp_path: Path) -> None:
    """Extractor parse miss -> suggestions_parsed False, ingest still ok, zero notes."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = "---\ntarget_slug: spec\ntitle: Spec\n---\nBody."
    extractor_response = "this is not valid yaml: : ["

    ingestor_llm = MagicMock()
    ingestor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm = MagicMock()
    extractor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        result = await run_ingest_source(source_file, workspace)

    assert result.status == "ok"
    assert result.suggestions_parsed is False
    assert result.suggested_pages == []
    assert not any((wiki / "proposals").glob("*.md"))


@pytest.mark.asyncio
async def test_run_ingest_source_records_reasoner_failure(tmp_path: Path) -> None:
    from graph_wiki_core.commands.ingest import run_ingest_source
    from graph_wiki_core.commands.proposal_reasoner import ProposalReasonerResult

    source_file = tmp_path / "spec.md"
    source_file.write_text("# Spec\n\nContent.", encoding="utf-8")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(wiki, packages=[])

    ingestor = MagicMock()
    ingestor.ainvoke = AsyncMock(
        return_value=MagicMock(content="---\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody.")
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
        patch("graph_wiki_core.commands.ingest.render_project_context", return_value=""),
        patch(
            "graph_wiki_core.commands.suggest_pages.run_proposal_reasoner",
            return_value=ProposalReasonerResult(status="failed", analysis="", error="reasoner failed"),
        ),
    ):
        result = await run_ingest_source(source_file, wiki)

    written = (wiki / result.page_path).read_text(encoding="utf-8")
    assert "  reasoner: failed" in written
    assert "  extractor: skipped" in written
    assert '  error: "reasoner failed"' in written
    assert result.proposal_reasoner_status == "failed"
    assert result.proposal_extractor_status == "skipped"


# ---------------------------------------------------------------------------
# M3: re-ingest preserves human suggestion decisions (spec §3.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_reingest_preserves_human_decision(tmp_path: Path) -> None:
    """A human's approved decision in the ledger survives re-ingest (spec §3.2).

    The note's status is human-decided, so upsert leaves it untouched on the
    second ingest — no prior-state capture in ingest.py is required.
    """
    from graph_wiki_core.commands.ingest import run_ingest_source
    from wiki_io.proposals import proposal_path, read_proposal, set_proposal_status

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nA cross-cutting idea.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = "---\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."
    extractor_response = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Cross Cutting Idea\n"
        "    slug: cross-cutting-idea\n"
        "    mode: create_new\n"
        "    rationale: The source defines it.\n"
    )

    def _llms():
        i = MagicMock()
        i.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
        e = MagicMock()
        e.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))
        return i, e

    ingestor_llm, extractor_llm = _llms()
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        first = await run_ingest_source(source_file, workspace)

    assert [(s["slug"], s["status"]) for s in first.suggested_pages] == [("cross-cutting-idea", "proposed")]

    # Human approves via the ledger API.
    set_proposal_status(wiki, "concept", "cross-cutting-idea", "approved")

    ingestor_llm2, extractor_llm2 = _llms()
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm2),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm2),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        second = await run_ingest_source(source_file, workspace)

    kept = [s for s in second.suggested_pages if s["slug"] == "cross-cutting-idea"]
    assert len(kept) == 1
    assert kept[0]["status"] == "approved"  # decision preserved by the ledger
    on_disk = read_proposal(proposal_path(wiki, "concept", "cross-cutting-idea"))
    assert on_disk["status"] == "approved"


@pytest.mark.asyncio
async def test_run_ingest_source_degraded_reingest_preserves_ledger_decision(tmp_path: Path) -> None:
    """A degraded re-ingest (extractor parse-miss) leaves a human-decided ledger
    note untouched — the suggest phase writes nothing, so the decision survives
    on disk even though this run reports zero suggestions."""
    from graph_wiki_core.commands.ingest import run_ingest_source
    from wiki_io.proposals import proposal_path, read_proposal, set_proposal_status

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nA cross-cutting idea.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = "---\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."
    extractor_response = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Cross Cutting Idea\n"
        "    slug: cross-cutting-idea\n"
        "    mode: create_new\n"
        "    rationale: The source defines it.\n"
    )

    ingestor_llm = MagicMock()
    ingestor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm = MagicMock()
    extractor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        await run_ingest_source(source_file, workspace)

    # Human approves via the ledger.
    set_proposal_status(wiki, "concept", "cross-cutting-idea", "approved")

    # Re-ingest the SAME source, but the extractor now returns unparseable YAML.
    ingestor_llm2 = MagicMock()
    ingestor_llm2.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm2 = MagicMock()
    extractor_llm2.ainvoke = AsyncMock(return_value=MagicMock(content="this is not valid yaml: : ["))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm2),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm2),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        second = await run_ingest_source(source_file, workspace)

    # (a) degraded: this run parsed nothing and reports nothing.
    assert second.suggestions_parsed is False
    # IngestResult reports only THIS run's upserts; a degraded run writes nothing,
    # so [] is correct even though the approved note persists on disk.
    assert second.suggested_pages == []
    # (b) the human decision survives on disk — the ledger note is untouched.
    assert read_proposal(proposal_path(wiki, "concept", "cross-cutting-idea"))["status"] == "approved"


def test_synthesize_frontmatter_block_prepends_all_fields() -> None:
    from graph_wiki_core.commands.ingest import (
        _rewrite_target_slug_in_body,
        _set_entity_uri_in_body,
        _synthesize_frontmatter_block,
    )

    body = "Just a body, no frontmatter.\n"
    out = _synthesize_frontmatter_block(body, "note", "my-slug", None)
    assert out.startswith("---\n")
    assert "source_type: note" in out
    assert "target_slug: my-slug" in out
    assert "entity_uri: null" in out
    assert out.rstrip().endswith("Just a body, no frontmatter.")

    # The downstream body helpers now function on the synthesized block and are
    # idempotent against it (proves synthesis produces a valid --- block).
    out2 = _rewrite_target_slug_in_body(out, "my-slug")
    out2 = _set_entity_uri_in_body(out2, None)
    assert out2.count("target_slug:") == 1
    assert out2.count("entity_uri:") == 1

    # entity_uri carried through when present.
    out_uri = _synthesize_frontmatter_block(body, "source", "s", "pkg:x/y/z")
    assert "entity_uri: pkg:x/y/z" in out_uri


def test_parse_extractor_response_accepts_rich_fields_and_limits_to_five() -> None:
    from graph_wiki_core.commands.suggest_pages import parse_extractor_response

    items = "\n".join(
        f"""  - kind: concept
    title: Candidate {i}
    slug: candidate-{i}
    mode: create_new
    existing_slug:
    rank: {i}
    confidence: medium
    rationale: Candidate {i} rationale.
    evidence:
      - Evidence {i}
    existing_pages_considered:
      - concepts/existing
    reasoning_summary: Reasoning {i}
    potential_conflicts:
      - Conflict {i}
    implementation_notes:
      - Note {i}"""
        for i in range(1, 7)
    )
    proposals, parsed = parse_extractor_response(f"suggestions:\n{items}")

    assert parsed is True
    assert len(proposals) == 5
    assert proposals[0]["rank"] == 1
    assert proposals[0]["confidence"] == "medium"
    assert proposals[0]["evidence"] == ["Evidence 1"]


def test_set_proposal_status_in_body_inserts_nested_block() -> None:
    from graph_wiki_core.commands.ingest import _set_proposal_status_in_body

    text = "---\ntitle: Spec\ntarget_slug: spec\n---\n\nBody"
    out = _set_proposal_status_in_body(
        text,
        {"reasoner": "ok", "extractor": "ok", "proposals": 2, "error": None},
        today="2026-06-06",
    )

    assert "proposal_status:" in out
    assert "  reasoner: ok" in out
    assert "  extractor: ok" in out
    assert "  proposals: 2" in out
    assert "  updated: 2026-06-06" in out
    assert "error:" not in out


def test_set_proposal_status_in_body_replaces_existing_block() -> None:
    from graph_wiki_core.commands.ingest import _set_proposal_status_in_body

    text = (
        "---\n"
        "title: Spec\n"
        "proposal_status:\n"
        "  reasoner: failed\n"
        "  extractor: skipped\n"
        "  proposals: 0\n"
        "  updated: 2026-06-05\n"
        "  error: old\n"
        "---\n\nBody"
    )
    out = _set_proposal_status_in_body(
        text,
        {"reasoner": "ok", "extractor": "ok", "proposals": 1, "error": None},
        today="2026-06-06",
    )

    assert out.count("proposal_status:") == 1
    assert "old" not in out
    assert "  proposals: 1" in out


def test_set_proposal_status_in_body_leaves_invalid_frontmatter_unchanged() -> None:
    from graph_wiki_core.commands.ingest import _set_proposal_status_in_body

    text = "---\ntitle: Spec\nmalformed: [\n---\n\nBody"

    out = _set_proposal_status_in_body(
        text,
        {"reasoner": "ok", "extractor": "ok", "proposals": 1, "error": None},
        today="2026-06-06",
    )

    assert out == text


def test_set_proposal_status_in_body_quotes_error_scalar() -> None:
    from graph_wiki_core.commands.ingest import _set_proposal_status_in_body

    text = "---\ntitle: Spec\ntarget_slug: spec\n---\n\nBody"
    out = _set_proposal_status_in_body(
        text,
        {"reasoner": "failed", "extractor": "skipped", "proposals": 0, "error": "reasoner failed"},
        today="2026-06-06",
    )

    assert 'error: "reasoner failed"' in out
    assert "\n...\n" not in out
    assert "proposal_status:" in out


def test_set_proposal_status_in_body_quotes_colon_error_scalar() -> None:
    from graph_wiki_core.commands.ingest import _set_proposal_status_in_body

    text = "---\ntitle: Spec\ntarget_slug: spec\n---\n\nBody"
    out = _set_proposal_status_in_body(
        text,
        {"reasoner": "failed", "extractor": "skipped", "proposals": 0, "error": "bedrock: access denied"},
        today="2026-06-06",
    )

    assert 'error: "bedrock: access denied"' in out
    assert "\n...\n" not in out


# ---------------------------------------------------------------------------
# Task 11 — skill-branch helpers (plan parse, synthesis fan-out, source body)
# ---------------------------------------------------------------------------


def test_parse_skill_plan_reads_yaml_list():
    from graph_wiki_core.commands.ingest import _parse_skill_plan

    text = (
        "- title: Use a Virtualizer\n"
        "  slug: use-virtualizer\n"
        "  topic: react-native\n"
        "  content: |\n"
        "    Use a virtualizer.\n"
    )
    plan = _parse_skill_plan(text)
    assert isinstance(plan, list)
    assert plan[0]["topic"] == "react-native"
    assert plan[0]["slug"] == "use-virtualizer"


def test_parse_skill_plan_strips_code_fence():
    from graph_wiki_core.commands.ingest import _parse_skill_plan

    text = "```yaml\n- title: A\n  topic: t\n  content: body\n```\n"
    plan = _parse_skill_plan(text)
    assert plan and plan[0]["title"] == "A"


def test_parse_skill_plan_returns_none_on_garbage():
    from graph_wiki_core.commands.ingest import _parse_skill_plan

    assert _parse_skill_plan("not yaml: [unclosed") is None
    assert _parse_skill_plan("title: not-a-list") is None  # mapping, not a list
    assert _parse_skill_plan("") is None


def test_guidance_wikilink_target_from_relpath():
    from graph_wiki_core.commands.ingest import _guidance_wikilink_target

    assert _guidance_wikilink_target("wiki/guidance/react-native/use-virtualizer.md") == (
        "guidance/react-native/use-virtualizer"
    )


def test_compose_skill_source_body_lists_generates():
    from graph_wiki_core.commands.ingest import _compose_skill_source_body

    body = _compose_skill_source_body(
        title="React Native Skill",
        written_rel_paths=[
            "wiki/guidance/react-native/use-virtualizer.md",
            "wiki/guidance/react-native/avoid-inline-styles.md",
        ],
    )
    assert body.lstrip().startswith("---")
    assert "## Generates" in body
    assert "[[guidance/react-native/use-virtualizer]]" in body
    assert "[[guidance/react-native/avoid-inline-styles]]" in body


@pytest.mark.asyncio
async def test_synthesize_guidance_pages_writes_validated_pages(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    workspace_root = tmp_path
    (workspace_root / "wiki").mkdir()

    valid_page = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: s\napplies_when: a\nimpact: high\nupdated: 2026-06-08\ntokens: 0\n---\n\n"
        "## Guidance\nUse a virtualizer.\n"
    )

    class _FakeLLM:
        async def ainvoke(self, messages):
            class _R:
                content = valid_page
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _FakeLLM())

    plan = [
        {"title": "Use a Virtualizer", "slug": "use-virtualizer", "topic": "react-native", "content": "x"},
    ]
    written = await ingest_mod._synthesize_guidance_pages(
        plan,
        workspace_root=workspace_root,
        project_ctx="",
        model_override=None,
    )
    assert written == ["wiki/guidance/react-native/use-virtualizer.md"]
    page = workspace_root / "wiki" / "guidance" / "react-native" / "use-virtualizer.md"
    assert page.is_file()
    assert "## Guidance" in page.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_synthesize_guidance_pages_strips_leading_whitespace(tmp_path, monkeypatch):
    """Some synthesizer models (e.g. kimi-k2.5) prepend a space before the `---`
    fence despite the prompt; the page must still parse and be written clean."""
    from graph_wiki_core.commands import ingest as ingest_mod

    workspace_root = tmp_path
    (workspace_root / "wiki").mkdir()

    # Note the leading " " before --- (and a trailing newline) — the defect.
    valid_page = (
        " ---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: s\napplies_when: a\nimpact: high\nupdated: 2026-06-08\ntokens: 0\n---\n\n"
        "## Guidance\nUse a virtualizer.\n"
    )

    class _FakeLLM:
        async def ainvoke(self, messages):
            class _R:
                content = valid_page
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _FakeLLM())

    plan = [{"title": "Use a Virtualizer", "slug": "use-virtualizer", "topic": "react-native", "content": "x"}]
    written = await ingest_mod._synthesize_guidance_pages(
        plan, workspace_root=workspace_root, project_ctx="", model_override=None
    )
    assert written == ["wiki/guidance/react-native/use-virtualizer.md"]
    page = workspace_root / "wiki" / "guidance" / "react-native" / "use-virtualizer.md"
    # Written file must not carry the stray leading whitespace.
    assert page.read_text(encoding="utf-8").startswith("---")


@pytest.mark.asyncio
async def test_synthesize_guidance_pages_post_stamps_updated_date(tmp_path, monkeypatch):
    """The model hallucinates `updated:`; the written page must carry the real
    date (here injected via `today`), not whatever the synthesizer emitted."""
    from graph_wiki_core.commands import ingest as ingest_mod

    workspace_root = tmp_path
    (workspace_root / "wiki").mkdir()

    # Model emits a stale/wrong date.
    page_with_wrong_date = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: s\napplies_when: a\nimpact: high\nupdated: 2025-01-16\ntokens: 0\n---\n\n"
        "## Guidance\nUse a virtualizer.\n"
    )

    class _FakeLLM:
        async def ainvoke(self, messages):
            class _R:
                content = page_with_wrong_date
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _FakeLLM())

    plan = [{"title": "Use a Virtualizer", "slug": "use-virtualizer", "topic": "react-native", "content": "x"}]
    written = await ingest_mod._synthesize_guidance_pages(
        plan, workspace_root=workspace_root, project_ctx="", model_override=None, today="2026-06-09"
    )
    assert written == ["wiki/guidance/react-native/use-virtualizer.md"]
    text = (workspace_root / "wiki" / "guidance" / "react-native" / "use-virtualizer.md").read_text(encoding="utf-8")
    from guidance_io.frontmatter import parse as parse_guidance_fm

    fm, _body = parse_guidance_fm(text)
    assert fm["updated"] == "2026-06-09"
    assert "2025-01-16" not in text
    # Body content survives the re-emit round-trip.
    assert "Use a virtualizer." in text


@pytest.mark.asyncio
async def test_synthesize_guidance_pages_skips_invalid(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    workspace_root = tmp_path
    (workspace_root / "wiki").mkdir()

    class _FakeLLM:
        async def ainvoke(self, messages):
            class _R:
                content = "this is not a guidance page"
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _FakeLLM())

    plan = [{"title": "Bad", "slug": "bad", "topic": "t", "content": "x"}]
    written = await ingest_mod._synthesize_guidance_pages(
        plan, workspace_root=workspace_root, project_ctx="", model_override=None
    )
    assert written == []


@pytest.mark.asyncio
async def test_run_ingest_source_skill_writes_guidance_and_skips_suggest(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    # --- workspace layout: <ws>/raw/skill/<file>, <ws>/wiki/ ---
    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")
    skill_dir = ws / "raw" / "skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "react-native.md"
    skill_file.write_text("# RN Skill\nAlways use a virtualizer for lists.\n", encoding="utf-8")

    # resolve_wiki_and_repo -> (wiki, repo); point both into the tmp workspace.
    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    # Graph conn + entity lookups: no graph, no match.
    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)

    planner_yaml = (
        "- title: Use a Virtualizer\n"
        "  slug: use-virtualizer\n"
        "  topic: react-native\n"
        "  summary: Use a virtualizer.\n"
        "  applies_when: Rendering a list.\n"
        "  impact: high\n"
        "  triggers:\n    globs: []\n    keywords: []\n    entities: []\n"
        "  content: Use a virtualizer instead of ScrollView.\n"
    )
    guidance_page = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: Use a virtualizer.\napplies_when: Rendering a list.\nimpact: high\n"
        "updated: 2026-06-08\ntokens: 0\n---\n\n## Guidance\nUse a virtualizer.\n"
    )

    def _fake_make_llm(role, model_override=None):
        out = planner_yaml if role == "skill_planner" else guidance_page

        class _LLM:
            async def ainvoke(self, messages):
                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)

    result = await ingest_mod.run_ingest_source(skill_file, workspace_path=ws)

    # Source page filed under sources/, source_type skill.
    assert result.source_type == "skill"
    assert result.page_type == "source"
    # Guidance page written (workspace-relative path).
    assert result.guidance_pages_written == ["wiki/guidance/react-native/use-virtualizer.md"]
    assert (ws / "wiki" / "guidance" / "react-native" / "use-virtualizer.md").is_file()
    # Suggest phase skipped.
    assert result.suggested_pages == []
    assert result.proposal_reasoner_status == "skipped"
    # Source page lists the generated page under ## Generates (link resolved, not stripped).
    src = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "## Generates" in src
    assert "[[guidance/react-native/use-virtualizer]]" in src
    assert result.stripped_wikilinks == []


@pytest.mark.asyncio
async def test_run_ingest_source_skill_falls_back_when_plan_unparseable(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")
    skill_dir = ws / "raw" / "skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "x.md"
    skill_file.write_text("# X\nbody\n", encoding="utf-8")

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)
    # Default branch's suggest phase: stub it out so no graph tools are needed.
    monkeypatch.setattr(ingest_mod, "build_graph_tools", lambda conn: [])

    async def _fake_suggest(**kwargs):
        return [], {"reasoner": "skipped", "extractor": "skipped", "proposals": 0, "error": None}

    monkeypatch.setattr(ingest_mod, "run_suggest_phase", _fake_suggest)

    def _fake_make_llm(role, model_override=None):
        # Planner returns garbage (not a YAML list) → branch returns None → fallback.
        out = (
            "title: not-a-list"
            if role == "skill_planner"
            else ("---\nsource_type: skill\ntarget_slug: x\n---\n\n## Summary\nFallback source page.\n")
        )

        class _LLM:
            async def ainvoke(self, messages):
                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)

    result = await ingest_mod.run_ingest_source(skill_file, workspace_path=ws)

    # Fell back to default branch: a Source page, no guidance pages.
    assert result.guidance_pages_written == []
    assert result.page_type == "source"
    # raw/skill/ is authoritative for source_type even on the default branch.
    assert result.source_type == "skill"


# ---------------------------------------------------------------------------
# Skill-branch ## Excluded section (directory-aware skill ingest)
# ---------------------------------------------------------------------------


def test_compose_skill_source_body_renders_excluded_section() -> None:
    from graph_wiki_core.commands.ingest import _compose_skill_source_body

    body = _compose_skill_source_body(
        "My Skill",
        ["wiki/guidance/topic/a.md"],
        excluded_files=["scripts/run.sh", "logo.png"],
    )
    assert "## Excluded" in body
    assert "2 non-markdown file(s)" in body
    assert "`scripts/run.sh`" in body
    assert "`logo.png`" in body
    # The ## Generates section is still present (additive, not a replacement).
    assert "## Generates" in body


def test_compose_skill_source_body_omits_excluded_when_empty() -> None:
    from graph_wiki_core.commands.ingest import _compose_skill_source_body

    assert "## Excluded" not in _compose_skill_source_body("My Skill", [], excluded_files=[])
    assert "## Excluded" not in _compose_skill_source_body("My Skill", [])  # default None


# ---------------------------------------------------------------------------
# Directory anchor forces the skill branch + renders ## Excluded end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_skill_directory_forces_skill_and_excludes(tmp_path, monkeypatch):
    """A skill DIRECTORY (outside raw/skill/) is anchored on SKILL.md, gathers a
    linked companion .md, excludes a script, and renders ## Excluded."""
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")

    # Skill directory lives OUTSIDE raw/ — only the anchor (not the path-guess)
    # can route this to the skill branch.
    skill_dir = ws / "skills" / "my-skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Skill\n---\n\n# My Skill\n\nSee [adv](references/advanced.md).\n",
        encoding="utf-8",
    )
    (skill_dir / "references" / "advanced.md").write_text("# Advanced\n\nDeep guidance.\n", encoding="utf-8")
    (skill_dir / "run.py").write_text("print('workflow')\n", encoding="utf-8")  # excluded

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)

    captured: dict = {}

    planner_yaml = (
        "- title: Deep Guidance\n"
        "  slug: deep-guidance\n"
        "  topic: my-skill\n"
        "  summary: Deep guidance.\n"
        "  applies_when: Working on the skill.\n"
        "  impact: high\n"
        "  content: Deep guidance from the companion file.\n"
    )
    guidance_page = (
        "---\ntitle: Deep Guidance\ncategory: guidance\ntopic: my-skill\n"
        "summary: Deep guidance.\napplies_when: Working on the skill.\nimpact: high\n"
        "updated: 2026-06-09\ntokens: 0\n---\n\n## Guidance\nDeep guidance.\n"
    )

    def _fake_make_llm(role, model_override=None):
        out = planner_yaml if role == "skill_planner" else guidance_page

        class _LLM:
            async def ainvoke(self, messages):
                # Capture the planner human message to assert the companion text
                # made it into the combined blob the planner sees.
                if role == "skill_planner":
                    captured["planner_human"] = messages[-1].content

                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)

    # Pass the DIRECTORY, not a file.
    result = await ingest_mod.run_ingest_source(skill_dir, workspace_path=ws)

    # Directory anchor forced the skill branch despite living outside raw/skill/.
    assert result.source_type == "skill"
    assert result.page_type == "source"
    # Title came from SKILL.md frontmatter `name:`.
    assert result.title == "My Skill"
    # Companion markdown was gathered into the combined text the planner saw.
    assert "Deep guidance" in captured["planner_human"]
    assert "<!-- skill-file: references/advanced.md -->" in captured["planner_human"]
    # Guidance page written from the plan.
    assert result.guidance_pages_written == ["wiki/guidance/my-skill/deep-guidance.md"]
    # ## Excluded section recorded the non-markdown file.
    src = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "## Excluded" in src
    assert "`run.py`" in src


@pytest.mark.asyncio
async def test_run_ingest_source_raw_skill_single_file_still_works(tmp_path, monkeypatch):
    """Regression: a raw/skill/<file>.md single file (NOT named SKILL.md) has no
    anchor, so bundle is None — it still routes to the skill branch via the
    path-guess and renders no ## Excluded section."""
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")
    skill_dir = ws / "raw" / "skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "react-native.md"
    skill_file.write_text("# RN Skill\nAlways use a virtualizer.\n", encoding="utf-8")

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)

    planner_yaml = (
        "- title: Use a Virtualizer\n"
        "  slug: use-virtualizer\n"
        "  topic: react-native\n"
        "  summary: Use a virtualizer.\n"
        "  applies_when: Rendering a list.\n"
        "  impact: high\n"
        "  content: Use a virtualizer instead of ScrollView.\n"
    )
    guidance_page = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: Use a virtualizer.\napplies_when: Rendering a list.\nimpact: high\n"
        "updated: 2026-06-09\ntokens: 0\n---\n\n## Guidance\nUse a virtualizer.\n"
    )

    def _fake_make_llm(role, model_override=None):
        out = planner_yaml if role == "skill_planner" else guidance_page

        class _LLM:
            async def ainvoke(self, messages):
                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)

    result = await ingest_mod.run_ingest_source(skill_file, workspace_path=ws)

    assert result.source_type == "skill"
    assert result.guidance_pages_written == ["wiki/guidance/react-native/use-virtualizer.md"]
    src = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "## Excluded" not in src  # no bundle -> no excluded section


# ---------------------------------------------------------------------------
# Raw-source archive after ingest (design 2026-06-09)
# ---------------------------------------------------------------------------


def _setup_archive_test_workspace(tmp_path, monkeypatch):
    """Workspace with a raw/ inbox; graph conn, entity lookups, and the suggest
    phase stubbed so default-branch ingests run offline."""
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")
    (ws / "raw").mkdir()

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)
    monkeypatch.setattr(ingest_mod, "build_graph_tools", lambda conn: [])

    async def _fake_suggest(**kwargs):
        return [], {"reasoner": "skipped", "extractor": "skipped", "proposals": 0, "error": None}

    monkeypatch.setattr(ingest_mod, "run_suggest_phase", _fake_suggest)
    return ws


def _patch_default_branch_llm(monkeypatch, target_slug="auth-spec"):
    from graph_wiki_core.commands import ingest as ingest_mod

    response = f"---\ntarget_slug: {target_slug}\ntitle: Auth Spec\n---\n\nBody text.\n"

    class _LLM:
        async def ainvoke(self, messages):
            class _R:
                content = response
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _LLM())


@pytest.mark.asyncio
async def test_run_ingest_source_archives_raw_source(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "raw" / "specs" / "auth.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Auth Spec\n\nbody\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to == "raw/_archive/specs/auth.md"
    # source_path keeps the ORIGINAL path (spec §3).
    assert result.source_path == str(src)
    assert not src.exists()
    archived = ws / "raw" / "_archive" / "specs" / "auth.md"
    assert archived.read_text(encoding="utf-8") == "# Auth Spec\n\nbody\n"
    # The ingest log records the destination.
    log_text = (ws / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "archived: raw/_archive/specs/auth.md" in log_text
    # The PAGE frontmatter now records the archive location (2026-06-14).
    page = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "source_path: raw/_archive/specs/auth.md" in page


@pytest.mark.asyncio
async def test_run_ingest_source_outside_raw_page_keeps_source_path(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "notes.md"
    src.write_text("# Loose Note\n\nbody\n", encoding="utf-8")
    response = "---\ntarget_slug: loose-note\ntitle: Loose Note\nsource_path: notes.md\n---\n\nBody.\n"

    class _LLM:
        async def ainvoke(self, messages):
            class _R:
                content = response
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _LLM())

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)
    assert result.archived_to is None
    page = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "source_path: notes.md" in page
    assert "_archive" not in page


@pytest.mark.asyncio
async def test_run_ingest_source_archive_overwrites_existing_destination(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    stale = ws / "raw" / "_archive" / "specs" / "auth.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old version", encoding="utf-8")
    src = ws / "raw" / "specs" / "auth.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Auth Spec v2\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.archived_to == "raw/_archive/specs/auth.md"
    assert stale.read_text(encoding="utf-8") == "# Auth Spec v2\n"


@pytest.mark.asyncio
async def test_run_ingest_source_leaves_sources_outside_raw_untouched(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "notes.md"
    src.write_text("# Loose Note\n\nbody\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch, target_slug="loose-note")

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to is None
    assert src.exists()
    assert not (ws / "raw" / "_archive").exists()


@pytest.mark.asyncio
async def test_run_ingest_source_move_failure_does_not_fail_ingest(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "raw" / "specs" / "auth.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Auth Spec\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch)

    def _boom(src_arg, dst_arg):
        raise OSError("disk says no")

    monkeypatch.setattr(ingest_mod.shutil, "move", _boom)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to is None
    assert src.exists()


def test_ingest_result_archive_to_defaults_none_and_serializes():
    from graph_wiki_core.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="sources/x.md",
        slug="x",
        title="X",
        page_type="source",
        source_path="/tmp/x.md",
        cross_refs_updated=1,
    )
    assert result.archived_to is None
    result.archived_to = "raw/_archive/specs/x.md"
    parsed = json.loads(json.dumps(dataclasses.asdict(result)))
    assert parsed["archived_to"] == "raw/_archive/specs/x.md"


def _patch_skill_branch_llm(monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    planner_yaml = (
        "- title: Use a Virtualizer\n"
        "  slug: use-virtualizer\n"
        "  topic: react-native\n"
        "  summary: Use a virtualizer.\n"
        "  applies_when: Rendering a list.\n"
        "  impact: high\n"
        "  triggers:\n    globs: []\n    keywords: []\n    entities: []\n"
        "  content: Use a virtualizer instead of ScrollView.\n"
    )
    guidance_page = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: Use a virtualizer.\napplies_when: Rendering a list.\nimpact: high\n"
        "updated: 2026-06-08\ntokens: 0\n---\n\n## Guidance\nUse a virtualizer.\n"
    )

    def _fake_make_llm(role, model_override=None):
        out = planner_yaml if role == "skill_planner" else guidance_page

        class _LLM:
            async def ainvoke(self, messages):
                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)


@pytest.mark.asyncio
async def test_run_ingest_source_archives_skill_directory_wholesale(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    skill_dir = ws / "raw" / "skill" / "react-native"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# RN Skill\nUse a virtualizer.\n", encoding="utf-8")
    (skill_dir / "extra.txt").write_text("companion\n", encoding="utf-8")
    _patch_skill_branch_llm(monkeypatch)

    # Pass the SKILL.md file — the anchor's PARENT directory must move wholesale.
    result = await ingest_mod.run_ingest_source(skill_dir / "SKILL.md", workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to == "raw/_archive/skill/react-native"
    assert not skill_dir.exists()
    archived = ws / "raw" / "_archive" / "skill" / "react-native"
    assert (archived / "SKILL.md").is_file()
    assert (archived / "extra.txt").is_file()
    # The kind folder itself stays put.
    assert (ws / "raw" / "skill").is_dir()


@pytest.mark.asyncio
async def test_run_ingest_source_skill_md_directly_in_kind_folder_moves_only_file(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    kind_dir = ws / "raw" / "skill"
    kind_dir.mkdir(parents=True)
    src = kind_dir / "SKILL.md"
    src.write_text("# Bare Skill\nGuidance.\n", encoding="utf-8")
    # A sibling awaiting ingestion must NOT be swept along.
    sibling = kind_dir / "other-skill.md"
    sibling.write_text("# Other\n", encoding="utf-8")
    _patch_skill_branch_llm(monkeypatch)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to == "raw/_archive/skill/SKILL.md"
    assert not src.exists()
    assert sibling.exists()
    assert kind_dir.is_dir()
    assert (ws / "raw" / "_archive" / "skill" / "SKILL.md").is_file()


# ---------------------------------------------------------------------------
# test_run_ingest_source_repoints_work_doc_pointer (doc-pointer repair)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_repoints_work_doc_pointer(tmp_path, monkeypatch):
    """Ingesting a raw/specs source archives it and repoints a work item's spec_doc."""
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)

    # Source lives under raw/specs so the archive move triggers.
    src = ws / "raw" / "specs" / "foo.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Foo\n\nSpec content.", encoding="utf-8")

    # A resolved work item still points at the pre-archive location.
    work_item = ws / "wiki" / "work" / "2026-01-01-foo.md"
    work_item.parent.mkdir(parents=True, exist_ok=True)
    work_item.write_text(
        "---\nstatus: resolved\nspec_doc: raw/specs/foo.md\n---\n\nbody\n",
        encoding="utf-8",
    )

    _patch_default_branch_llm(monkeypatch, target_slug="foo")

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    # The source moved to the archive, and the work pointer followed it.
    assert (ws / "raw" / "_archive" / "specs" / "foo.md").exists()
    assert result.archived_to == "raw/_archive/specs/foo.md"
    assert "spec_doc: raw/_archive/specs/foo.md" in work_item.read_text(encoding="utf-8")
