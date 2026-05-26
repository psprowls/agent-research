from __future__ import annotations

"""Unit tests for graph_wiki_agent.commands.ingest (Plan 05-05).

Requirements: CMD-03
Tests all public behaviors of run_ingest_source and run_ingest_work_item.
"""

import dataclasses
import json
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Phase 40 graph-seeding helper for ingest tests
# ---------------------------------------------------------------------------


def _seed_graph_db_for_ingest_tests(
    workspace: Path,
    packages: list[tuple[str, str, str | None]],
    extra_nodes: list[tuple[str, str, str | None, str | None]] | None = None,
) -> Path:
    """Create <workspace>/.graph/code.db with package nodes + (optional) file nodes.

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
                    "INSERT INTO edges (src, dst, kind, attrs_json) "
                    "VALUES (?, ?, 'contains', NULL)",
                    (pkg_id, file_id),
                )
        for entry in extra_nodes or []:
            kind, name, path, uri = entry
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                "VALUES (?, ?, ?, ?, NULL, NULL, ?)",
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

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

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
    # Phase 40: body now also contains an entity_uri: null line (no graph match);
    # use substring assertions rather than strict equality.
    written_body = expected_page.read_text(encoding="utf-8")
    assert "page_type: concept" in written_body
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

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

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

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

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

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

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

    _seed_graph_db_for_ingest_tests(wiki, packages=[])

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


# ===========================================================================
# Phase 40: graph-io integration tests (INGESTOR-01, INGESTOR-02)
# ===========================================================================

_FM_TEMPLATE = (
    "---\n"
    "title: {title}\n"
    "category: {category}\n"
    "page_type: {page_type}\n"
    "target_slug: {slug}\n"
    "summary: x\n"
    "---\n"
    "Body."
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
    """Missing .graph/code.db → IngestorGraphNotInitializedError; LLM not invoked."""
    from graph_wiki_agent.commands.ingest import (
        IngestorGraphNotInitializedError,
        run_ingest_source,
    )

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")

    # Do NOT create workspace/.graph/code.db — that is the test scenario.

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
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
    assert "graph-wiki-agent graph build" in msg
    assert mock_make_llm.call_count == 0, (
        f"LLM must NOT be invoked on NOT_INITIALIZED path; was called {mock_make_llm.call_count}x"
    )
    assert fake_llm.ainvoke.call_count == 0


# ---------------------------------------------------------------------------
# Test: path match overrides LLM slug
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_path_match_overrides_slug(tmp_path: Path) -> None:
    """Seeded path lookup returns canonical URI; LLM slug is replaced."""
    from graph_wiki_agent.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    rel_path = "packages/graph-io/src/graph_io/store.py"
    source_file = workspace / rel_path
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# store\n\nBody.", encoding="utf-8")

    canonical_uri = "pkg:agent-research/agent-research/graph-io"
    _seed_graph_db_for_ingest_tests(
        workspace,
        packages=[("graph-io", canonical_uri, rel_path)],
    )

    fake_llm_response = _FM_TEMPLATE.format(
        title="Store",
        category="package",
        page_type="package",
        slug="wrong-slug",  # the LLM's guess that we expect to be overridden
    )

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    expected_page = wiki / "packages" / "graph-io.md"
    assert expected_page.exists(), f"expected page at {expected_page}"
    body = expected_page.read_text(encoding="utf-8")
    assert f"entity_uri: {canonical_uri}" in body
    assert "target_slug: graph-io" in body
    assert "target_slug: wrong-slug" not in body
    assert result.entity_uri == canonical_uri
    assert result.slug == "graph-io"


# ---------------------------------------------------------------------------
# Test: name fallback overrides slug when path lookup misses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_name_fallback_overrides_slug(
    tmp_path: Path,
) -> None:
    """When path lookup misses, the name fallback resolves via title_guess."""
    from graph_wiki_agent.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    # Source file is OUTSIDE the package path used by the graph entry, so path
    # lookup misses and we fall through to the name lookup.
    source_file = workspace / "random" / "src.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# SubagentPool\n\nBody.", encoding="utf-8")

    canonical_uri = "cls:subagent_runtime.pool.SubagentPool"
    _seed_graph_db_for_ingest_tests(
        workspace,
        packages=[],
        extra_nodes=[("class", "SubagentPool", None, canonical_uri)],
    )

    # title_guess derives from extract() title -> source_path.stem fallback.
    # We set the LLM frontmatter title so the body keeps "SubagentPool"; the
    # in-code title_guess will be "Src" from filename. Force the name match
    # path by ALSO seeding the title path: extract() reads from the source
    # file's first heading. The file's first heading is "# SubagentPool".
    fake_llm_response = _FM_TEMPLATE.format(
        title="SubagentPool",
        category="concept",
        page_type="concept",
        slug="some-other-thing",
    )

    with (
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert result.entity_uri == canonical_uri
    # slug should be derived from the URI tail
    assert result.slug == "subagent_runtime.pool.SubagentPool"
    written = (wiki / "concepts" / f"{result.slug}.md").read_text(encoding="utf-8")
    assert f"entity_uri: {canonical_uri}" in written


# ---------------------------------------------------------------------------
# Test: no match writes entity_uri: null
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_no_match_writes_null_entity_uri(
    tmp_path: Path,
) -> None:
    """Empty graph DB → entity_uri is None and body has 'entity_uri: null'."""
    from graph_wiki_agent.commands.ingest import run_ingest_source

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
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert result.entity_uri is None
    written = (wiki / "concepts" / "my-thing.md").read_text(encoding="utf-8")
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
    from graph_wiki_agent.commands.ingest import run_ingest_source

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
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    captured = capsys.readouterr()
    assert "matches multiple graph nodes" in captured.err
    written = (wiki / "concepts" / "helper.md").read_text(encoding="utf-8")
    assert "entity_uri: null" in written
    assert result.entity_uri is None


# ---------------------------------------------------------------------------
# Test: conn closed even when LLM raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_closes_conn_on_exception(tmp_path: Path) -> None:
    """conn.close() is called in finally even if ainvoke raises."""
    from graph_wiki_agent.commands.ingest import run_ingest_source

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
        patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_agent.commands.ingest.read_only_connect") as mock_connect,
        patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_agent.commands.ingest.update_index"),
        patch("graph_wiki_agent.commands.ingest.append_log"),
        patch("graph_wiki_agent.commands.ingest.queries") as mock_queries,
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
    from graph_wiki_agent.commands.ingest import _set_entity_uri_in_body

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
