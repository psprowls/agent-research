from __future__ import annotations

"""Unit tests for QueryResult dataclass, guardrails, and run_query pipeline (Plan 03).

Requirements covered: SEARCH-06, CMD-04, CMD-07.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# QueryResult shape tests
# ---------------------------------------------------------------------------


def test_query_result_is_dataclass() -> None:
    """QueryResult is a Python dataclass with the required fields."""
    from code_wiki_agent.commands.query import QueryResult

    qr = QueryResult(
        answer="test answer",
        citations=["PageA", "PageB"],
        pages_drilled=3,
        search_scores={"page.md": {"bm25": 0.5, "embed": 0.3, "rrf": 0.01}},
    )
    assert qr.answer == "test answer"
    assert qr.citations == ["PageA", "PageB"]
    assert qr.pages_drilled == 3
    assert dataclasses.is_dataclass(qr)


def test_query_result_asdict_has_required_keys() -> None:
    """dataclasses.asdict(QueryResult(...)) contains answer, citations, pages_drilled, search_scores."""
    from code_wiki_agent.commands.query import QueryResult

    qr = QueryResult(
        answer="x",
        citations=[],
        pages_drilled=0,
        search_scores={},
    )
    d = dataclasses.asdict(qr)
    assert set(d.keys()) == {"answer", "citations", "pages_drilled", "search_scores"}


def test_search_scores_shape_per_page() -> None:
    """search_scores dict maps page path to {bm25, embed, rrf} float keys (SEARCH-06)."""
    from code_wiki_agent.commands.query import QueryResult

    scores = {
        "concepts/foo.md": {"bm25": 1.5, "embed": 0.82, "rrf": 0.016},
        "concepts/bar.md": {"bm25": 0.0, "embed": 0.71, "rrf": 0.015},
    }
    qr = QueryResult(answer="a", citations=[], pages_drilled=2, search_scores=scores)
    for page, page_scores in qr.search_scores.items():
        assert "bm25" in page_scores
        assert "embed" in page_scores
        assert "rrf" in page_scores
        assert isinstance(page_scores["bm25"], float)
        assert isinstance(page_scores["embed"], float)
        assert isinstance(page_scores["rrf"], float)


def test_json_output_valid_schema() -> None:
    """JSON round-trip: dataclasses.asdict + json.dumps/loads preserves all keys (CMD-07)."""
    from code_wiki_agent.commands.query import QueryResult

    qr = QueryResult(
        answer="synthesized answer [[Foo]]",
        citations=["Foo"],
        pages_drilled=5,
        search_scores={"foo.md": {"bm25": 0.1, "embed": 0.2, "rrf": 0.03}},
    )
    raw = json.dumps(dataclasses.asdict(qr))
    parsed = json.loads(raw)
    assert parsed["answer"] == "synthesized answer [[Foo]]"
    assert parsed["citations"] == ["Foo"]
    assert parsed["pages_drilled"] == 5
    assert "foo.md" in parsed["search_scores"]


# ---------------------------------------------------------------------------
# _extract_wikilinks tests
# ---------------------------------------------------------------------------


def test_extract_wikilinks_basic() -> None:
    """_extract_wikilinks returns inner content of [[...]] tokens."""
    from code_wiki_agent.commands.query import _extract_wikilinks

    text = "see [[Foo]] and [[bar/baz]] for details"
    result = _extract_wikilinks(text)
    assert result == ["Foo", "bar/baz"]


def test_extract_wikilinks_empty() -> None:
    """_extract_wikilinks returns empty list when no wikilinks present."""
    from code_wiki_agent.commands.query import _extract_wikilinks

    assert _extract_wikilinks("no links here") == []


# ---------------------------------------------------------------------------
# apply_guardrails tests
# ---------------------------------------------------------------------------


def test_apply_guardrails_g4_clears_citations_on_empty_successes(
    tmp_path: Path,
) -> None:
    """G4: empty successes + non-empty citations -> citations cleared + warning prepended."""
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import QueryResult, apply_guardrails

    fan_result = FanOutResult(successes=[], errors=[])
    result = QueryResult(
        answer="confident answer",
        citations=["A"],
        pages_drilled=0,
        search_scores={},
    )
    guarded = apply_guardrails(result, tmp_path, fan_result)

    assert guarded.citations == []
    assert "no librarian excerpts" in guarded.answer


def test_apply_guardrails_g4_no_change_when_no_citations(tmp_path: Path) -> None:
    """G4: empty successes with no citations -> no warning added."""
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import QueryResult, apply_guardrails

    fan_result = FanOutResult(successes=[], errors=[])
    result = QueryResult(
        answer="no citations here",
        citations=[],
        pages_drilled=0,
        search_scores={},
    )
    guarded = apply_guardrails(result, tmp_path, fan_result)
    assert "no librarian excerpts" not in guarded.answer
    assert guarded.citations == []


def test_apply_guardrails_g1_flags_unresolved(tmp_path: Path) -> None:
    """G1: citation pointing to non-existent page -> warning appended to answer."""
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import QueryResult, apply_guardrails

    fan_result = FanOutResult(
        successes=[("page1.md", "excerpt")], errors=[]
    )
    result = QueryResult(
        answer="see [[NonExistentPage]] for info",
        citations=["NonExistentPage"],
        pages_drilled=1,
        search_scores={},
    )
    # tmp_path has no pages — NonExistentPage.md doesn't exist
    guarded = apply_guardrails(result, tmp_path, fan_result)
    assert "did not resolve" in guarded.answer
    assert "NonExistentPage" in guarded.answer


def test_apply_guardrails_g1_no_warning_when_page_exists(tmp_path: Path) -> None:
    """G1: citation pointing to existing page -> no warning."""
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import QueryResult, apply_guardrails

    # Create the page file so it resolves
    (tmp_path / "ExistingPage.md").write_text("content")

    fan_result = FanOutResult(successes=[("p.md", "excerpt")], errors=[])
    result = QueryResult(
        answer="see [[ExistingPage]] for info",
        citations=["ExistingPage"],
        pages_drilled=1,
        search_scores={},
    )
    guarded = apply_guardrails(result, tmp_path, fan_result)
    assert "did not resolve" not in guarded.answer


def test_apply_guardrails_g1_no_double_md_extension(tmp_path: Path) -> None:
    """G1: citation already containing .md suffix (e.g. [[concepts/foo.md]]) resolves correctly.

    Regression: prior implementation appended .md unconditionally, producing
    'concepts/foo.md.md' which never existed even for valid drilled pages.
    """
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import QueryResult, apply_guardrails

    # Create the page at its actual path (as returned by the search layer)
    (tmp_path / "concepts").mkdir()
    (tmp_path / "concepts" / "foo.md").write_text("content")

    fan_result = FanOutResult(successes=[("concepts/foo.md", "excerpt")], errors=[])
    result = QueryResult(
        answer="see [[concepts/foo.md]] for info",
        citations=["concepts/foo.md"],
        pages_drilled=1,
        search_scores={},
    )
    guarded = apply_guardrails(result, tmp_path, fan_result)
    assert "did not resolve" not in guarded.answer


# ---------------------------------------------------------------------------
# Constants present
# ---------------------------------------------------------------------------


def test_librarian_system_constant_present() -> None:
    """LIBRARIAN_SYSTEM module constant is defined."""
    from code_wiki_agent.commands.query import LIBRARIAN_SYSTEM

    assert isinstance(LIBRARIAN_SYSTEM, str)
    assert len(LIBRARIAN_SYSTEM) > 0


def test_synthesizer_system_constant_present() -> None:
    """SYNTHESIZER_SYSTEM module constant is defined."""
    from code_wiki_agent.commands.query import SYNTHESIZER_SYSTEM

    assert isinstance(SYNTHESIZER_SYSTEM, str)
    assert len(SYNTHESIZER_SYSTEM) > 0


# ---------------------------------------------------------------------------
# run_query unit test (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_query_unit_with_mocks(tmp_path: Path) -> None:
    """run_query returns QueryResult with correct search_scores shape when all deps mocked."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from code_wiki_agent.commands.query import QueryResult, run_query

    # Build a mock vault with a .code-wiki dir (so auto-build check passes)
    vault = tmp_path / "vault"
    vault.mkdir()
    bm25_dir = vault / ".code-wiki" / "bm25"
    bm25_dir.mkdir(parents=True)
    db_path = vault / ".code-wiki" / "search.db"
    db_path.touch()

    fake_fan_result = FanOutResult(
        successes=[
            ("page1.md", "excerpt from page 1"),
            ("page2.md", "NO_RELEVANT_CONTENT"),
        ],
        errors=[],
    )

    fake_synth_response = AIMessage(content="Answer about [[FakePage]].")

    with (
        patch(
            "code_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "code_wiki_agent.commands.query.bm25_query",
            return_value=(["page1.md", "page2.md", "page3.md"], [2.0, 1.5, 1.0]),
        ),
        patch(
            "code_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page1.md", 0.9), ("page2.md", 0.8), ("page3.md", 0.7)],
        ),
        patch(
            "code_wiki_agent.commands.query.BedrockEmbeddings",
        ) as mock_embeddings_cls,
        patch(
            "code_wiki_agent.commands.query.make_llm",
        ) as mock_make_llm,
        patch(
            "code_wiki_agent.commands.query.SubagentPool",
        ) as mock_pool_cls,
    ):
        # Setup embedding mock
        mock_embeddings_inst = MagicMock()
        mock_embeddings_inst.embed_query.return_value = [0.1] * 1024
        mock_embeddings_cls.return_value = mock_embeddings_inst

        # Setup make_llm mock — returns different mocks for librarian vs synthesizer
        mock_librarian_llm = MagicMock()
        mock_synth_llm = MagicMock()
        mock_synth_llm.ainvoke = AsyncMock(return_value=fake_synth_response)
        mock_make_llm.side_effect = lambda role: (
            mock_librarian_llm if role == "librarian" else mock_synth_llm
        )

        # Setup SubagentPool mock
        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=fake_fan_result)
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("test query", vault_path=vault, top_k=3)

    assert isinstance(result, QueryResult)
    # The synthesizer answer is present (guardrails may append warnings)
    assert "Answer about [[FakePage]]." in result.answer
    assert isinstance(result.citations, list)
    assert result.pages_drilled == 2  # two successes
    # search_scores must have bm25/embed/rrf for each top page
    for page_scores in result.search_scores.values():
        assert "bm25" in page_scores
        assert "embed" in page_scores
        assert "rrf" in page_scores
