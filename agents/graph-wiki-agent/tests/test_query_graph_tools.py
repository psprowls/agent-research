"""Regression tests for empty-DB graph-tool-binding fix (jc1, 2026-05-30).

Root cause: EvalWorktree provisions an empty schema-valid code.db.
read_only_connect() succeeds on the empty DB, causing build_graph_tools()
to return real callables that the librarian uses — then loops to the
iteration cap returning NO_RELEVANT_CONTENT because every query returns
empty rows. This triggers the code-fallback chain, yielding
CODE_FALLBACK_DISCLAIMER answers scored 0.10 by judges.

Fix: after read_only_connect() succeeds, check node count. If 0, treat
as uninitialized (no tools bound, fallback addendum, stderr signal).

Tests:
    test_run_query_binds_graph_tools_when_initialized:
        non-empty DB (node_count > 0) → build_graph_tools called, bind_tools called.

    test_run_query_skips_graph_tools_when_db_empty:
        empty DB (node_count == 0) → build_graph_tools NOT called, bind_tools NOT called,
        stderr carries _GRAPH_UNAVAILABLE_STDERR, addendum in librarian system prompt.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graph_wiki_agent.commands.query import (
    _GRAPH_UNAVAILABLE_STDERR,
    _LIBRARIAN_FALLBACK_ADDENDUM,
)


# ---------------------------------------------------------------------------
# Shared helpers (mirrors _FakeLLM pattern from wiring tests)
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path) -> Path:
    """Minimal fake vault with indices and one page on disk."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()
    (vault / "page1.md").write_text("# page1\n\nbody")
    return vault


def _make_librarian_llm(content: str = "useful excerpt") -> MagicMock:
    """Return a fake librarian LLM that immediately returns content with no tool calls."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content=content, tool_calls=[]))
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


def _make_synth_llm(answer: str = "synthesized answer") -> MagicMock:
    """Return a fake synthesizer LLM."""
    from langchain_core.messages import AIMessage

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=answer))
    return llm


def _base_patches(vault: Path) -> list:
    """Common patches for every run_query call in this module."""
    return [
        patch(
            "graph_wiki_agent.commands.query.resolve_wiki_and_repo",
            return_value=(vault, None),
        ),
        patch(
            "graph_wiki_agent.commands.query.bm25_query",
            return_value=(["page1.md"], [2.0]),
        ),
        patch(
            "graph_wiki_agent.commands.query._cosine_search_sqlite",
            return_value=[("page1.md", 0.9)],
        ),
        patch("graph_wiki_agent.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_agent.commands.query.count_tokens", return_value=10),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_query_binds_graph_tools_when_initialized(tmp_path: Path) -> None:
    """Non-empty DB: build_graph_tools IS called and bind_tools IS called.

    Baseline: confirms that when the graph DB has nodes, the normal
    grounding-tools path fires (the fix must not break the happy path).
    """
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    librarian_llm = _make_librarian_llm()
    synth_llm = _make_synth_llm()

    fake_conn = MagicMock()
    # Simulate non-empty DB: COUNT(*) returns 42 nodes.
    fake_conn.execute.return_value.fetchone.return_value = (42,)

    fake_tool = MagicMock()
    fake_tool.name = "cg_find"

    fan_result = FanOutResult(
        successes=[("page1.md", "useful excerpt content here")], errors=[]
    )

    def _make_llm_side_effect(role: str, *, model_override=None):
        if role == "librarian":
            return librarian_llm
        return synth_llm

    extra = [
        patch(
            "graph_wiki_agent.commands.query.read_only_connect",
            return_value=fake_conn,
        ),
        patch(
            "graph_wiki_agent.commands.query.build_graph_tools",
            return_value=[fake_tool],
        ),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]

    with ExitStack() as stack:
        patches = _base_patches(vault) + extra
        mocks = [stack.enter_context(p) for p in patches]
        # mocks: resolve, bm25, cosine, embed, count_tokens, read_only, build_graph, make_llm, pool
        mock_make_llm = mocks[7]
        mock_pool_cls = mocks[8]
        mock_build_graph = mocks[6]

        mock_make_llm.side_effect = _make_llm_side_effect
        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=fan_result)
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("q", workspace_path=vault, top_k=3)

    # build_graph_tools must have been called (non-empty DB path).
    mock_build_graph.assert_called_once()
    # bind_tools must have been called because graph_tools is non-empty.
    librarian_llm.bind_tools.assert_called_once_with([fake_tool])


@pytest.mark.asyncio
async def test_run_query_skips_graph_tools_when_db_empty(
    tmp_path: Path, capsys
) -> None:
    """Empty DB (node_count == 0): build_graph_tools NOT called, bind_tools NOT called.

    Regression test for jc1 fix: EvalWorktree provisions an empty schema-valid
    code.db. This test verifies that a zero-node DB is treated as uninitialized,
    preventing the code-fallback loop that collapsed eval quality scores.
    """
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    librarian_llm = _make_librarian_llm()
    synth_llm = _make_synth_llm()

    fake_conn = MagicMock()
    # Simulate empty DB: COUNT(*) returns 0 nodes.
    fake_conn.execute.return_value.fetchone.return_value = (0,)

    fan_result = FanOutResult(
        successes=[("page1.md", "useful excerpt content here")], errors=[]
    )

    def _make_llm_side_effect(role: str, *, model_override=None):
        if role == "librarian":
            return librarian_llm
        return synth_llm

    extra = [
        patch(
            "graph_wiki_agent.commands.query.read_only_connect",
            return_value=fake_conn,
        ),
        patch(
            "graph_wiki_agent.commands.query.build_graph_tools",
            return_value=[],
        ),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]

    with ExitStack() as stack:
        patches = _base_patches(vault) + extra
        mocks = [stack.enter_context(p) for p in patches]
        mock_make_llm = mocks[7]
        mock_pool_cls = mocks[8]
        mock_build_graph = mocks[6]

        mock_make_llm.side_effect = _make_llm_side_effect

        mock_pool_inst = MagicMock()

        async def _fake_run_all(*, items, task, **_):
            results = []
            for it in items:
                tr = await task(it)
                results.append((it, tr.value if hasattr(tr, "value") else tr))
            return FanOutResult(successes=results, errors=[])

        mock_pool_inst.run_all = AsyncMock(side_effect=_fake_run_all)
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("q", workspace_path=vault, top_k=3)

    # build_graph_tools must NOT be called (empty DB treated as uninitialized).
    mock_build_graph.assert_not_called()
    # bind_tools must NOT be called.
    librarian_llm.bind_tools.assert_not_called()
    # Empty DB signals the same stderr message as a missing DB.
    err = capsys.readouterr().err
    assert _GRAPH_UNAVAILABLE_STDERR in err
    # The librarian system prompt must include the fallback addendum.
    invoke_msgs = librarian_llm.ainvoke.call_args.args[0]
    sys_msg = invoke_msgs[0]
    assert _LIBRARIAN_FALLBACK_ADDENDUM.strip() in sys_msg.content
    # The conn must be closed (not leaked).
    fake_conn.close.assert_called_once()
