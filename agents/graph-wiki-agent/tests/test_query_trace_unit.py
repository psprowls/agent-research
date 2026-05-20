from __future__ import annotations

"""Fast unit tests for query.py synthesizer-token extraction (TRACE-FU-01 D-03).

Asserts the synthesizer usage_metadata None-guard captures tokens into the
per-query summary_record at BOTH synth call sites (librarian path and
code-fallback path). No real Bedrock calls.
"""

import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _read_summary(wiki: Path) -> dict:
    trace_dir = wiki / ".graph-wiki" / "traces"
    summary_files = list(trace_dir.glob("query_*.jsonl"))
    assert len(summary_files) == 1, f"expected one query_*.jsonl, got {summary_files}"
    raw = summary_files[0].read_text().strip()
    return json.loads(raw)


def _setup_query_patches(vault: Path):
    """Patch the same surface as the existing test_query_code_fallback fixtures."""
    return [
        patch(
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page1.md"], [1.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page1.md", 0.9)],
        ),
        patch("graph_wiki_agent.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]


@pytest.mark.asyncio
async def test_query_summary_record_includes_synthesizer_tokens(tmp_path: Path) -> None:
    """Librarian-path synth call: tokens flow from usage_metadata into summary_record."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()

    librarian_fan = FanOutResult(
        successes=[("page1.md", "Useful excerpt about the topic")],
        errors=[],
    )
    synth_resp = AIMessage(
        content="The answer is foo.",
        usage_metadata={"input_tokens": 200, "output_tokens": 75, "total_tokens": 275},
    )

    mock_synth = MagicMock()
    mock_synth.ainvoke = AsyncMock(return_value=synth_resp)

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _setup_query_patches(vault)]
        _r, _b, _c, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        mock_make_llm.side_effect = lambda role: mock_synth

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=librarian_fan)
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("what?", vault_path=vault, top_k=3)

    summary = _read_summary(vault)
    assert summary["tokens_in"] == 200
    assert summary["tokens_out"] == 75
    assert summary["code_fallback"] is False


@pytest.mark.asyncio
async def test_query_summary_record_handles_none_usage_metadata(tmp_path: Path) -> None:
    """When usage_metadata is None (Bedrock error response), tokens fields are None."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()

    librarian_fan = FanOutResult(
        successes=[("page1.md", "Useful excerpt about the topic")],
        errors=[],
    )
    synth_resp = AIMessage(content="The answer.", usage_metadata=None)

    mock_synth = MagicMock()
    mock_synth.ainvoke = AsyncMock(return_value=synth_resp)

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _setup_query_patches(vault)]
        _r, _b, _c, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        mock_make_llm.side_effect = lambda role: mock_synth

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=librarian_fan)
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("what?", vault_path=vault, top_k=3)

    summary = _read_summary(vault)
    assert summary["tokens_in"] is None
    assert summary["tokens_out"] is None


@pytest.mark.asyncio
async def test_code_fallback_path_threads_synth_tokens_into_summary(tmp_path: Path) -> None:
    """Code-fallback synth call: tokens flow into summary_record via tuple return."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()

    librarian_fan = FanOutResult(
        successes=[("page1.md", "NO_RELEVANT_CONTENT")],
        errors=[],
    )
    code_fan = FanOutResult(
        successes=[("page1.md", "`module.py:42` — relevant code excerpt")],
        errors=[],
    )
    synth_resp = AIMessage(
        content="From the source: foo.",
        usage_metadata={"input_tokens": 333, "output_tokens": 111, "total_tokens": 444},
    )

    mock_synth = MagicMock()
    mock_synth.ainvoke = AsyncMock(return_value=synth_resp)
    mock_code = MagicMock()
    mock_code.bind_tools = MagicMock(return_value=mock_code)

    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _setup_query_patches(vault)]
        _r, _b, _c, mock_embed_cls, mock_make_llm, mock_pool_cls = mocks

        mock_embed_inst = MagicMock()
        mock_embed_inst.embed_query.return_value = [0.1] * 1024
        mock_embed_cls.return_value = mock_embed_inst

        def _llm_for(role: str):
            if role == "code_reader":
                return mock_code
            return mock_synth

        mock_make_llm.side_effect = _llm_for

        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(side_effect=[librarian_fan, code_fan])
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("what?", vault_path=vault, top_k=3)

    summary = _read_summary(vault)
    assert summary["code_fallback"] is True
    assert summary["tokens_in"] == 333
    assert summary["tokens_out"] == 111
