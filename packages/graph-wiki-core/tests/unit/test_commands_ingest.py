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
    fake = MagicMock()
    fake.ainvoke = AsyncMock(return_value=MagicMock(content="suggestions: []"))
    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake):
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

    fake_llm_response = (
        "---\ntarget_slug: foo\ntitle: My Source\nsummary: A test concept\n---\n\nBody text here."
    )

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
async def test_run_ingest_work_item_writes_to_workspace_work_dir(tmp_path: Path) -> None:
    """Valid YAML: page exists at workspace/work/<opened>-<slug>.md; page_type==work."""
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

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    work_dir = tmp_path / "work"

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.file_work_item") as mock_file_work_item,
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

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "log.md").write_text("", encoding="utf-8")

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.file_work_item") as mock_file_work_item,
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
    assert call_kwargs.kwargs.get("force") is True or (len(call_kwargs.args) > 3 and call_kwargs.args[3] is True), (
        f"force=True not found in call: {call_kwargs}"
    )


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
    fake_llm_response = (
        "---\ntitle: A Decision\npage_type: adr\ntarget_slug: a-decision\nsummary: x\n---\nBody."
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
