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
    from graph_wiki_agent.commands.query import QueryResult

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
    from graph_wiki_agent.commands.query import QueryResult

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
    from graph_wiki_agent.commands.query import QueryResult

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
    from graph_wiki_agent.commands.query import QueryResult

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
    from graph_wiki_agent.commands.query import _extract_wikilinks

    text = "see [[Foo]] and [[bar/baz]] for details"
    result = _extract_wikilinks(text)
    assert result == ["Foo", "bar/baz"]


def test_extract_wikilinks_empty() -> None:
    """_extract_wikilinks returns empty list when no wikilinks present."""
    from graph_wiki_agent.commands.query import _extract_wikilinks

    assert _extract_wikilinks("no links here") == []


# ---------------------------------------------------------------------------
# apply_guardrails tests
# ---------------------------------------------------------------------------


def test_apply_guardrails_g4_clears_citations_on_empty_successes(
    tmp_path: Path,
) -> None:
    """G4: empty successes + non-empty citations -> citations cleared + warning prepended."""
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, apply_guardrails

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


def test_apply_guardrails_skip_g4_preserves_citations_on_empty_successes(
    tmp_path: Path,
) -> None:
    """CR-01 regression: skip_g4=True preserves citations even when fan_result.successes is empty.

    This is the code-fallback path: the librarian fan-out may have errored out
    or returned zero successes, but the code-reader fan-out produced a real
    answer with real citations. G4 must NOT strip those.
    """
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, apply_guardrails

    (tmp_path / "concepts").mkdir()
    (tmp_path / "concepts" / "pool.md").write_text("# Pool\n")

    fan_result = FanOutResult(successes=[], errors=[("p1.md", "boom")])
    result = QueryResult(
        answer="The pool uses a semaphore [[concepts/pool]].",
        citations=["concepts/pool"],
        pages_drilled=0,
        search_scores={},
    )
    guarded = apply_guardrails(result, tmp_path, fan_result, skip_g4=True)

    assert guarded.citations == ["concepts/pool"], (
        "skip_g4 must preserve citations on code-fallback path"
    )
    assert "no librarian excerpts" not in guarded.answer, (
        "skip_g4 must suppress the unsupported-answer warning"
    )


def test_apply_guardrails_skip_g4_still_runs_g1(tmp_path: Path) -> None:
    """skip_g4=True does NOT disable G1 — unresolved wikilinks still get flagged."""
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, apply_guardrails

    fan_result = FanOutResult(successes=[], errors=[])
    result = QueryResult(
        answer="Answer with [[nonexistent/page]] citation.",
        citations=["nonexistent/page"],
        pages_drilled=0,
        search_scores={},
    )
    guarded = apply_guardrails(result, tmp_path, fan_result, skip_g4=True)

    # G1 still fires: unresolved wikilink gets the warning footer
    assert "did not resolve" in guarded.answer
    # But citations are preserved (G4 didn't strip them)
    assert guarded.citations == ["nonexistent/page"]


def test_apply_guardrails_g4_no_change_when_no_citations(tmp_path: Path) -> None:
    """G4: empty successes with no citations -> no warning added."""
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, apply_guardrails

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

    from graph_wiki_agent.commands.query import QueryResult, apply_guardrails

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

    from graph_wiki_agent.commands.query import QueryResult, apply_guardrails

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

    from graph_wiki_agent.commands.query import QueryResult, apply_guardrails

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
    from graph_wiki_agent.commands.query import LIBRARIAN_SYSTEM

    assert isinstance(LIBRARIAN_SYSTEM, str)
    assert len(LIBRARIAN_SYSTEM) > 0


def test_synthesizer_system_constant_present() -> None:
    """SYNTHESIZER_SYSTEM module constant is defined."""
    from graph_wiki_agent.commands.query import SYNTHESIZER_SYSTEM

    assert isinstance(SYNTHESIZER_SYSTEM, str)
    assert len(SYNTHESIZER_SYSTEM) > 0


# ---------------------------------------------------------------------------
# Plan 03-08: Prompt contract tests (SC-1 gap closure)
# ---------------------------------------------------------------------------


def test_librarian_prompt_contains_no_invention_rule() -> None:
    """LIBRARIAN_SYSTEM must encode verbatim quoting + no-invention + NO_RELEVANT_CONTENT."""
    from graph_wiki_agent.commands.query import LIBRARIAN_SYSTEM

    lowered = LIBRARIAN_SYSTEM.lower()
    assert "verbatim" in lowered, "Librarian prompt must require verbatim quoting"
    assert "NO_RELEVANT_CONTENT" in LIBRARIAN_SYSTEM, (
        "Librarian prompt must keep the sentinel literal"
    )
    # No-invention phrase — accept any of several common phrasings
    no_invention_tokens = ["never invent", "do not invent", "don't invent", "no-invention"]
    assert any(tok in lowered for tok in no_invention_tokens), (
        "Librarian prompt must contain an explicit no-invention rule"
    )


def test_librarian_prompt_keeps_sentinel() -> None:
    """LIBRARIAN_SYSTEM must contain the exact NO_RELEVANT_CONTENT literal.

    The filter at query.py:568 depends on this sentinel being emitted verbatim.
    """
    from graph_wiki_agent.commands.query import LIBRARIAN_SYSTEM

    assert "NO_RELEVANT_CONTENT" in LIBRARIAN_SYSTEM


def test_synthesizer_prompt_requires_full_wikilink_paths() -> None:
    """SYNTHESIZER_SYSTEM must require full vault page paths (not slug-only)."""
    from graph_wiki_agent.commands.query import SYNTHESIZER_SYSTEM

    # Full-path example must appear
    assert "[[wiki/" in SYNTHESIZER_SYSTEM, (
        "Synthesizer prompt must show full-path wikilink form like [[wiki/...]]"
    )
    # Slug-only-forbidden directive — accept several phrasings
    lowered = SYNTHESIZER_SYSTEM.lower()
    slug_forbid_tokens = ["slug-only", "slug only", "never collapse", "do not collapse"]
    assert any(tok in lowered for tok in slug_forbid_tokens), (
        "Synthesizer prompt must explicitly forbid slug-only wikilinks"
    )


def test_synthesizer_prompt_requires_code_path_line_citations() -> None:
    """SYNTHESIZER_SYSTEM must instruct the model to preserve `path:line` code refs."""
    from graph_wiki_agent.commands.query import SYNTHESIZER_SYSTEM

    assert "path:line" in SYNTHESIZER_SYSTEM, (
        "Synthesizer prompt must reference the path:line citation format"
    )
    assert "`" in SYNTHESIZER_SYSTEM, (
        "Synthesizer prompt must show backticks for code-path citations"
    )


def test_synthesizer_prompt_forbids_invention() -> None:
    """SYNTHESIZER_SYSTEM must contain a no-invention / vault-thin acknowledgment directive."""
    from graph_wiki_agent.commands.query import SYNTHESIZER_SYSTEM

    lowered = SYNTHESIZER_SYSTEM.lower()
    no_invention_tokens = ["never invent", "do not invent", "don't invent", "no-invention"]
    assert any(tok in lowered for tok in no_invention_tokens), (
        "Synthesizer prompt must explicitly forbid inventing paths/symbols"
    )
    # Vault-thin acknowledgment
    ack_tokens = ["does not document", "vault does not", "vault doesn't", "not documented"]
    assert any(tok in lowered for tok in ack_tokens), (
        "Synthesizer prompt must require explicit acknowledgment when the vault lacks coverage"
    )


# ---------------------------------------------------------------------------
# run_query unit test (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_query_unit_with_mocks(tmp_path: Path) -> None:
    """run_query returns QueryResult with correct search_scores shape when all deps mocked."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, run_query

    # Build a mock vault with a .graph-wiki dir (so auto-build check passes)
    vault = tmp_path / "vault"
    vault.mkdir()
    bm25_dir = vault / ".graph-wiki" / "bm25"
    bm25_dir.mkdir(parents=True)
    db_path = vault / ".graph-wiki" / "search.db"
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
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page1.md", "page2.md", "page3.md"], [2.0, 1.5, 1.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page1.md", 0.9), ("page2.md", 0.8), ("page3.md", 0.7)],
        ),
        patch(
            "graph_wiki_agent.commands.query.BedrockEmbeddings",
        ) as mock_embeddings_cls,
        patch(
            "graph_wiki_agent.commands.query.make_llm",
        ) as mock_make_llm,
        patch(
            "graph_wiki_agent.commands.query.SubagentPool",
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


# ---------------------------------------------------------------------------
# Plan 03-08: run_query unresolved-wikilink retry tests (SC-1 gap closure)
# ---------------------------------------------------------------------------


def _patches_for_run_query(vault: Path, fan_result, synth_responses: list):
    """Build the patch stack and mock wiring for run_query unit tests.

    synth_responses is a list of AIMessage objects, returned by successive
    `synth_llm.ainvoke()` calls. Length must be >= number of expected synth calls.
    Returns (patch_context_manager_list, mock_synth_llm) so the test can inspect
    `mock_synth_llm.ainvoke.call_args_list` to verify retry-prompt content.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    # Setup synthesizer LLM mock that returns successive responses
    mock_synth_llm = MagicMock()
    mock_synth_llm.ainvoke = AsyncMock(side_effect=synth_responses)
    mock_librarian_llm = MagicMock()

    patches = [
        patch(
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page1.md", "page2.md", "page3.md"], [2.0, 1.5, 1.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page1.md", 0.9), ("page2.md", 0.8), ("page3.md", 0.7)],
        ),
        patch("graph_wiki_agent.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]
    return patches, mock_synth_llm, mock_librarian_llm


@pytest.mark.asyncio
async def test_run_query_retries_on_unresolved_wikilink(tmp_path: Path) -> None:
    """Unresolved wikilink in first synth answer triggers exactly one synth retry.

    Retry HumanMessage must literally contain the unresolved token (e.g. "[[ghost]]")
    so the model is told which tokens to repair/drop, not just "any unresolved ones".
    """
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()

    fan_result = FanOutResult(
        successes=[("page1.md", "excerpt with [[wiki/real]] reference")],
        errors=[],
    )

    first_resp = AIMessage(content="Answer with [[ghost]] unresolved.")
    retry_resp = AIMessage(content="Answer without unresolved links.")

    patches, mock_synth_llm, mock_librarian_llm = _patches_for_run_query(
        vault, fan_result, [first_resp, retry_resp]
    )
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        _resolve, _bm25, _cos, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        mock_make_llm.side_effect = lambda role: (
            mock_librarian_llm if role == "librarian" else mock_synth_llm
        )

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=fan_result)
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("test query", vault_path=vault, top_k=3)

    assert isinstance(result, QueryResult)
    # Retry answer was used (no warning footer because retry succeeded)
    assert "Answer without unresolved links." in result.answer
    assert "did not resolve" not in result.answer
    # Two synth calls: original + retry
    assert mock_synth_llm.ainvoke.call_count == 2
    # Retry HumanMessage content must literally name the unresolved token
    retry_call_args = mock_synth_llm.ainvoke.call_args_list[1]
    retry_msgs = retry_call_args.args[0]
    # The last message (HumanMessage) must contain the unresolved token literally
    assert "[[ghost]]" in retry_msgs[-1].content, (
        "Retry prompt must literally list the unresolved token [[ghost]], "
        "not just a generic 'remove unresolved links' instruction. "
        f"Got: {retry_msgs[-1].content!r}"
    )


@pytest.mark.asyncio
async def test_run_query_keeps_warning_after_failed_retry(tmp_path: Path) -> None:
    """If retry also returns unresolved wikilinks, warning footer is preserved."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()

    fan_result = FanOutResult(
        successes=[("page1.md", "excerpt")],
        errors=[],
    )

    first_resp = AIMessage(content="Answer with [[ghost]] unresolved.")
    retry_resp = AIMessage(content="Still mentions [[ghost]] somehow.")

    patches, mock_synth_llm, mock_librarian_llm = _patches_for_run_query(
        vault, fan_result, [first_resp, retry_resp]
    )
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        _resolve, _bm25, _cos, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        mock_make_llm.side_effect = lambda role: (
            mock_librarian_llm if role == "librarian" else mock_synth_llm
        )

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=fan_result)
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("test query", vault_path=vault, top_k=3)

    assert isinstance(result, QueryResult)
    # Retry was tried (call count == 2) but failed; warning footer present
    assert mock_synth_llm.ainvoke.call_count == 2, "Retry must be attempted once"
    assert "did not resolve" in result.answer, (
        "After failed retry, warning footer must be appended as fallback"
    )
    # Final answer is the retry's answer (the latest synth output), not the first
    assert "Still mentions" in result.answer


@pytest.mark.asyncio
async def test_run_query_no_retry_when_librarian_empty(tmp_path: Path) -> None:
    """Empty librarian fan_result.successes -> Plan 09 code-fallback path takes over;
    the synthesizer's unresolved-wikilink retry is NOT attempted on the librarian
    excerpts (because there are none) and the original synth call does not happen
    on the empty-then-empty fallback path.

    Pre-Plan-09 behavior (now superseded): G4 fired immediately, synth was called
    once, and citations were cleared. Plan 09 redirects empty-librarian-results
    through the code-reader fan-out; when the code-reader ALSO returns nothing,
    the disclaimer is returned without invoking the synthesizer.
    """
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import QueryResult, run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()

    # Empty librarian successes — Plan 09 code-fallback path
    librarian_fan = FanOutResult(successes=[], errors=[])
    code_fan = FanOutResult(successes=[], errors=[])

    # No synth responses staged — the disclaimer path should not call synth.
    patches, mock_synth_llm, mock_librarian_llm = _patches_for_run_query(
        vault, librarian_fan, []
    )
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in patches]
        _resolve, _bm25, _cos, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        mock_code_llm = MagicMock()
        mock_code_llm.bind_tools = MagicMock(return_value=mock_code_llm)

        def _llm_for(role: str):
            if role == "librarian":
                return mock_librarian_llm
            if role == "code_reader":
                return mock_code_llm
            return mock_synth_llm

        mock_make_llm.side_effect = _llm_for

        mock_pool_inst = MagicMock()
        # First run_all → librarian (empty); second → code-fallback (also empty)
        mock_pool_inst.run_all = AsyncMock(side_effect=[librarian_fan, code_fan])
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("test query", vault_path=vault, top_k=3)

    assert isinstance(result, QueryResult)
    # Synthesizer was NOT called on the disclaimer path (no synth response staged
    # — StopAsyncIteration would have been raised if it had been called)
    assert mock_synth_llm.ainvoke.call_count == 0, (
        "Code-fallback disclaimer path must not invoke the synthesizer"
    )
    # Disclaimer line, no fabrication
    assert "vault does not document this" in result.answer
    assert result.citations == []
