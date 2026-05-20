from __future__ import annotations

"""Unit tests for graph_wiki_agent.commands.ingest (Plan 05-05).

Requirements: CMD-03
Tests all public behaviors of run_ingest_source and run_ingest_work_item.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# test_run_ingest_source_extracts_and_routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_extracts_and_routes(tmp_path: Path) -> None:
    """Fake ingestor returns page_type=concept; page written under concepts/foo.md."""
    from graph_wiki_agent.commands.ingest import IngestResult, run_ingest_source

    # Create a fake source file
    source_file = tmp_path / "my-source.md"
    source_file.write_text("# My Source\n\nSome content here.", encoding="utf-8")

    # Build a fake wiki structure
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    fake_llm_response = "---\npage_type: concept\ntarget_slug: foo\ntitle: My Source\ncategory: concept\nsummary: A test concept\n---\n\nBody text here."

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index") as mock_update_index,
        patch("graph_wiki_agent.commands.ingest.append_log") as mock_append_log,
    ):
        mock_resolve.return_value = (wiki, tmp_path)

        # Set up fake LLM
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    # Page should be written under concepts/foo.md
    expected_page = wiki / "concepts" / "foo.md"
    assert expected_page.exists(), f"Expected page at {expected_page}"
    assert expected_page.read_text(encoding="utf-8") == fake_llm_response

    # update_index and append_log must be called
    mock_update_index.assert_called_once_with(wiki)
    mock_append_log.assert_called_once()

    # IngestResult shape check
    assert isinstance(result, IngestResult)
    assert result.status == "ok"
    assert result.slug == "foo"
    assert result.page_type == "concept"
    assert "concepts/foo.md" in result.page_path


# ---------------------------------------------------------------------------
# test_run_ingest_source_default_slug_from_title
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_default_slug_from_title(tmp_path: Path) -> None:
    """When LLM frontmatter omits target_slug, falls back to slugified title."""
    from graph_wiki_agent.commands.ingest import IngestResult, run_ingest_source

    source_file = tmp_path / "my-source.md"
    source_file.write_text("# My Cool Source\n\nContent.", encoding="utf-8")

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    # LLM response: no target_slug, but page_type=concept
    fake_llm_response = "---\npage_type: concept\ntitle: My Cool Source\ncategory: concept\nsummary: Cool\n---\n\nBody."

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
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
    from graph_wiki_agent.commands.ingest import run_ingest_work_item

    # Missing 'affects' field
    frontmatter_text = (
        "title: Fix Auth Bug\n"
        "category: work\n"
        "kind: bug\n"
        "status: open\n"
        "summary: Fix the auth bug\n"
        "opened: 2026-05-14\n"
    )

    wiki = tmp_path / "wiki"
    wiki.mkdir()

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
    ):
        mock_resolve.return_value = (wiki, tmp_path)

        with pytest.raises(ValueError) as exc_info:
            await run_ingest_work_item(frontmatter_text, "Some body.", workspace_path=wiki)

    assert "affects" in str(exc_info.value)


# ---------------------------------------------------------------------------
# test_run_ingest_work_item_writes_to_workspace_work_dir
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_work_item_writes_to_workspace_work_dir(tmp_path: Path) -> None:
    """Valid YAML: page exists at workspace/work/<opened>-<slug>.md; page_type==work."""
    from graph_wiki_agent.commands.ingest import IngestResult, run_ingest_work_item

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

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    work_dir = tmp_path / "work"

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.file_work_item") as mock_file_work_item,
    ):
        mock_resolve.return_value = (wiki, tmp_path)

        # file_work_item returns the expected dict
        expected_page_path = str(work_dir / "2026-05-14-fix-auth-bug.md")
        mock_file_work_item.return_value = {
            "status": "ok",
            "page_path": expected_page_path,
            "slug": "fix-auth-bug",
            "title": "Fix Auth Bug",
        }

        result = await run_ingest_work_item(frontmatter_text, "Some body.", workspace_path=wiki)

    assert isinstance(result, IngestResult)
    assert result.page_type == "work"
    assert result.status == "ok"
    assert result.slug == "fix-auth-bug"
    assert "2026-05-14-fix-auth-bug" in result.page_path


# ---------------------------------------------------------------------------
# test_run_ingest_work_item_invokes_file_work_item_with_force
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_work_item_invokes_file_work_item_with_force(tmp_path: Path) -> None:
    """force=True propagated to file_work_item()."""
    from graph_wiki_agent.commands.ingest import run_ingest_work_item

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

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.file_work_item") as mock_file_work_item,
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        mock_file_work_item.return_value = {
            "status": "ok",
            "page_path": str(tmp_path / "work" / "2026-05-14-some-item.md"),
            "slug": "some-item",
            "title": "Some Item",
        }

        await run_ingest_work_item(frontmatter_text, "Body.", force=True, workspace_path=wiki)

    # Verify force=True was passed to file_work_item
    call_kwargs = mock_file_work_item.call_args
    assert call_kwargs.kwargs.get("force") is True or (
        len(call_kwargs.args) > 3 and call_kwargs.args[3] is True
    ), f"force=True not found in call: {call_kwargs}"


# ---------------------------------------------------------------------------
# test_ingest_result_round_trips_to_json
# ---------------------------------------------------------------------------


def test_ingest_result_round_trips_to_json() -> None:
    """IngestResult serializes to JSON without error."""
    from graph_wiki_agent.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="concepts/foo.md",
        slug="foo",
        title="Foo",
        page_type="concept",
        source_path="/some/path/foo.md",
        cross_refs_updated=1,
    )

    # Should not raise
    serialized = json.dumps(dataclasses.asdict(result))
    parsed = json.loads(serialized)

    assert parsed["status"] == "ok"
    assert parsed["slug"] == "foo"
    assert parsed["page_type"] == "concept"
    assert parsed["cross_refs_updated"] == 1


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
def test_parse_ingestor_response_handles_fenced_and_unfenced(
    raw: str, expected_fm: dict, expected_body: str
) -> None:
    from graph_wiki_agent.commands.ingest import _parse_ingestor_response

    fm, body = _parse_ingestor_response(raw)
    for k, v in expected_fm.items():
        assert fm.get(k) == v, f"key {k}: expected {v}, got {fm.get(k)}"
    assert body.strip() == expected_body.strip()


def test_parse_ingestor_response_no_frontmatter_returns_empty() -> None:
    from graph_wiki_agent.commands.ingest import _parse_ingestor_response

    fm, body = _parse_ingestor_response("just some text, no frontmatter")
    assert fm == {}
    assert body == "just some text, no frontmatter"


def test_parse_ingestor_response_fence_without_dashes_returns_empty() -> None:
    """Fence present but no --- inside: treat as no-frontmatter, do not
    silently strip the fence and succeed on a non-YAML body."""
    from graph_wiki_agent.commands.ingest import _parse_ingestor_response

    raw = "```yaml\nkey: value\nno_dashes: here\n```"
    fm, body = _parse_ingestor_response(raw)
    assert fm == {}, f"expected empty dict, got {fm}"


# ---------------------------------------------------------------------------
# page_type=source routing + target_slug-filename equality (Plan 06-13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_routes_source_to_sources_dir(tmp_path: Path) -> None:
    """Fake ingestor returns page_type=source; page lands under sources/foo.md."""
    from graph_wiki_agent.commands.ingest import run_ingest_source

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

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    expected_page = wiki / "sources" / "an-article.md"
    assert expected_page.exists(), f"expected page at {expected_page}, got result={result}"
    assert (wiki / "concepts").exists() is False or not any(
        (wiki / "concepts").iterdir()
    ), "concepts/ should be empty for page_type=source"
    assert result.page_type == "source"
    assert "sources/an-article.md" in result.page_path
    assert result.slug == "an-article"


@pytest.mark.asyncio
async def test_run_ingest_source_target_slug_matches_filename(tmp_path: Path) -> None:
    """LLM emits a slug that slugify() transforms; frontmatter target_slug
    in the written file must equal the on-disk filename slug."""
    from graph_wiki_agent.commands.ingest import run_ingest_source

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

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    # Determine the actual on-disk path; assert filename slug == body target_slug
    written_path = wiki / "concepts" / f"{result.slug}.md"
    assert written_path.exists(), f"expected page at {written_path}"
    written_body = written_path.read_text(encoding="utf-8")
    assert f"target_slug: {result.slug}" in written_body, (
        f"target_slug in body must equal filename stem '{result.slug}'; "
        f"body excerpt:\n{written_body[:300]}"
    )
    # And the original LLM slug (pre-slugify) should NOT survive verbatim
    assert "target_slug: weird_slug_with_underscores" not in written_body


# ---------------------------------------------------------------------------
# _resolve_wikilinks unit tests (Plan 06-14)
# ---------------------------------------------------------------------------


def test_resolve_wikilinks_strips_unresolved(tmp_path: Path) -> None:
    from graph_wiki_agent.commands.ingest import _resolve_wikilinks

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
    from graph_wiki_agent.commands.ingest import _resolve_wikilinks

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "sources" / "otel-story.md").write_text("# OTel", encoding="utf-8")

    # The UAT G4 case form: [[sources/otel-story]]
    text = "Per [[sources/otel-story]] the trace is propagated…"
    out, stripped = _resolve_wikilinks(text, wiki)
    assert "[[sources/otel-story]]" in out
    assert stripped == []


def test_resolve_wikilinks_preserves_fenced_code(tmp_path: Path) -> None:
    from graph_wiki_agent.commands.ingest import _resolve_wikilinks

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
    from graph_wiki_agent.commands.ingest import run_ingest_source

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

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log") as mock_append_log,
    ):
        mock_resolve.return_value = (wiki, tmp_path)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, wiki)

    written = (wiki / "concepts" / "my-page.md").read_text(encoding="utf-8")
    assert "[[real-thing]]" in written
    assert "[[Hallucinated Person]]" not in written
    assert "Hallucinated Person" in written  # label preserved
    # append_log was called with a detail recording the strip count
    call_args = mock_append_log.call_args
    detail = call_args.kwargs.get("detail") or (call_args.args[3] if len(call_args.args) >= 4 else "")
    assert "stripped 1" in detail or "stripped 1 unresolved" in detail
    assert result.page_type == "concept"
