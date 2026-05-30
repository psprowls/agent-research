"""Wiring tests for Phase 37: librarian grounding tools in run_query.

Covers connection lifetime (LIBTOOLS-04 + LIBTOOLS-03), CountTokens
pre-flight gate (LIBTOOLS-05, D-04..D-06), NOT_INITIALIZED fallback
(D-07, D-08), agentic tool-call loop (LIBTOOLS-04 + D-11), and
the Plan 01 pyproject sanity check.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graph_io.store import GraphNotInitializedError
from graph_wiki_agent.commands.query import (
    BUDGET_EXCEEDED_EXIT_CODE,
    LIBRARIAN_BUDGET_FRACTION,
    LIBRARIAN_CONTEXT_WINDOW,
    _GRAPH_UNAVAILABLE_STDERR,
    _LIBRARIAN_FALLBACK_ADDENDUM,
    _LIBRARIAN_MAX_ITERS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal fake vault with the indices and one page on disk."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".graph-wiki" / "bm25").mkdir(parents=True)
    (vault / ".graph-wiki" / "search.db").touch()
    (vault / "page1.md").write_text("# page1\n\nbody")
    return vault


def _patches(
    vault: Path,
    *,
    fan_result,
    librarian_llm,
    synth_llm,
    extra_patches: list | None = None,
):
    """Return the list of context-managed patches used by every wiring test.

    Doesn't include the read_only_connect / count_tokens / build_graph_tools
    patches — those are test-specific.
    """
    base = [
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
    ]
    base.extend(extra_patches or [])
    return base


def _mock_llm_for(librarian_llm, synth_llm):
    def _llm_for(role: str, *, model_override: str | None = None):
        if role == "librarian":
            return librarian_llm
        return synth_llm

    return _llm_for


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_connection_open_close(tmp_path: Path) -> None:
    """Successful run opens read_only_connect once, closes the returned conn once."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    fake_conn = MagicMock()
    open_calls: list = []

    def _fake_open(path):
        open_calls.append(path)
        return fake_conn

    librarian_resp = MagicMock(content="excerpt", tool_calls=[])
    librarian_llm = MagicMock()
    librarian_llm.ainvoke = AsyncMock(return_value=librarian_resp)
    librarian_llm.bind_tools = MagicMock(return_value=librarian_llm)
    synth_llm = MagicMock()
    synth_llm.ainvoke = AsyncMock(return_value=AIMessage(content="answer"))
    fan_result = FanOutResult(
        successes=[("page1.md", "useful excerpt content here")], errors=[]
    )

    extra = [
        patch("graph_wiki_agent.commands.query.read_only_connect", side_effect=_fake_open),
        patch("graph_wiki_agent.commands.query.build_graph_tools", return_value=[]),
        patch("graph_wiki_agent.commands.query.count_tokens", return_value=10),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _patches(vault, fan_result=fan_result, librarian_llm=librarian_llm, synth_llm=synth_llm, extra_patches=extra)]
        _r, _b, _c, _e, _ro, _bt, _ct, mock_make_llm, mock_pool_cls = mocks
        mock_make_llm.side_effect = _mock_llm_for(librarian_llm, synth_llm)
        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=fan_result)
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("q", workspace_path=vault, top_k=3)

    assert len(open_calls) == 1
    assert fake_conn.close.call_count == 1


@pytest.mark.asyncio
async def test_not_initialized_fallback(tmp_path: Path, capsys) -> None:
    """GraphNotInitializedError → one stderr line, addendum in system prompt, no bind_tools."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    librarian_resp = MagicMock(content="excerpt", tool_calls=[])
    librarian_llm = MagicMock()
    librarian_llm.ainvoke = AsyncMock(return_value=librarian_resp)
    librarian_llm.bind_tools = MagicMock(return_value=librarian_llm)
    synth_llm = MagicMock()
    synth_llm.ainvoke = AsyncMock(return_value=AIMessage(content="answer"))
    fan_result = FanOutResult(
        successes=[("page1.md", "useful excerpt content here")], errors=[]
    )

    def _raise(_):
        raise GraphNotInitializedError("missing")

    extra = [
        patch("graph_wiki_agent.commands.query.read_only_connect", side_effect=_raise),
        patch("graph_wiki_agent.commands.query.build_graph_tools", return_value=[]),
        patch("graph_wiki_agent.commands.query.count_tokens", return_value=10),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _patches(vault, fan_result=fan_result, librarian_llm=librarian_llm, synth_llm=synth_llm, extra_patches=extra)]
        _r, _b, _c, _e, _ro, _bt, _ct, mock_make_llm, mock_pool_cls = mocks
        mock_make_llm.side_effect = _mock_llm_for(librarian_llm, synth_llm)
        mock_pool_inst = MagicMock()

        async def _fake_run_all(*, items, task, **_):
            # Drive drill_page so its SystemMessage content is captured by ainvoke.
            results = []
            for it in items:
                tr = await task(it)
                results.append((it, tr.value if hasattr(tr, "value") else tr))
            return FanOutResult(successes=results, errors=[])

        mock_pool_inst.run_all = AsyncMock(side_effect=_fake_run_all)
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("q", workspace_path=vault, top_k=3)

    err = capsys.readouterr().err
    assert err.count(_GRAPH_UNAVAILABLE_STDERR) == 1
    # bind_tools must NOT be called (no graph_tools to bind)
    assert librarian_llm.bind_tools.call_count == 0
    # SystemMessage content includes the addendum
    invoke_msgs = librarian_llm.ainvoke.call_args.args[0]
    sys_msg = invoke_msgs[0]
    assert _LIBRARIAN_FALLBACK_ADDENDUM.strip() in sys_msg.content


@pytest.mark.asyncio
async def test_budget_overflow_hard_aborts(tmp_path: Path, capsys) -> None:
    """measured > budget → sys.exit(BUDGET_EXCEEDED_EXIT_CODE) + stderr line, no fan-out."""
    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    librarian_llm = MagicMock()
    librarian_llm.bind_tools = MagicMock(return_value=librarian_llm)
    synth_llm = MagicMock()

    extra = [
        patch(
            "graph_wiki_agent.commands.query.read_only_connect",
            return_value=MagicMock(),
        ),
        patch("graph_wiki_agent.commands.query.build_graph_tools", return_value=[]),
        patch(
            "graph_wiki_agent.commands.query.count_tokens", return_value=9_999_999
        ),
        patch(
            "graph_wiki_agent.commands.query._estimate_tool_schema_tokens",
            return_value=0,
        ),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _patches(vault, fan_result=None, librarian_llm=librarian_llm, synth_llm=synth_llm, extra_patches=extra)]
        _r, _b, _c, _e, _ro, _bt, _ct, _et, mock_make_llm, mock_pool_cls = mocks
        mock_make_llm.side_effect = _mock_llm_for(librarian_llm, synth_llm)
        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock()
        mock_pool_cls.return_value = mock_pool_inst

        with pytest.raises(SystemExit) as excinfo:
            await run_query("q", workspace_path=vault, top_k=3)

    assert excinfo.value.code == BUDGET_EXCEEDED_EXIT_CODE
    err = capsys.readouterr().err
    assert "librarian: token budget exceeded" in err
    budget = int(LIBRARIAN_CONTEXT_WINDOW * LIBRARIAN_BUDGET_FRACTION)
    assert f"of {budget} tokens" in err
    # Fan-out must NOT have been called (abort happens BEFORE fan-out per D-06)
    assert mock_pool_inst.run_all.await_count == 0


@pytest.mark.asyncio
async def test_budget_under_proceeds(tmp_path: Path) -> None:
    """measured < budget → run_query completes, pool.run_all called exactly once."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    librarian_resp = MagicMock(content="excerpt", tool_calls=[])
    librarian_llm = MagicMock()
    librarian_llm.ainvoke = AsyncMock(return_value=librarian_resp)
    librarian_llm.bind_tools = MagicMock(return_value=librarian_llm)
    synth_llm = MagicMock()
    synth_llm.ainvoke = AsyncMock(return_value=AIMessage(content="answer"))
    fan_result = FanOutResult(
        successes=[("page1.md", "useful excerpt content here")], errors=[]
    )

    extra = [
        patch(
            "graph_wiki_agent.commands.query.read_only_connect",
            return_value=MagicMock(),
        ),
        patch("graph_wiki_agent.commands.query.build_graph_tools", return_value=[]),
        patch("graph_wiki_agent.commands.query.count_tokens", return_value=100),
        patch(
            "graph_wiki_agent.commands.query._estimate_tool_schema_tokens",
            return_value=50,
        ),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _patches(vault, fan_result=fan_result, librarian_llm=librarian_llm, synth_llm=synth_llm, extra_patches=extra)]
        _r, _b, _c, _e, _ro, _bt, _ct, _et, mock_make_llm, mock_pool_cls = mocks
        mock_make_llm.side_effect = _mock_llm_for(librarian_llm, synth_llm)
        mock_pool_inst = MagicMock()
        mock_pool_inst.run_all = AsyncMock(return_value=fan_result)
        mock_pool_cls.return_value = mock_pool_inst

        result = await run_query("q", workspace_path=vault, top_k=3)

    assert mock_pool_inst.run_all.await_count == 1
    assert result.answer == "answer"


@pytest.mark.asyncio
async def test_librarian_tool_call_loop(tmp_path: Path) -> None:
    """ainvoke returns tool_calls → tool.invoke runs → second ainvoke sees ToolMessage."""
    from langchain_core.messages import AIMessage, ToolMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    first = MagicMock(
        content="",
        tool_calls=[
            {"name": "cg_find", "args": {"name": "foo"}, "id": "call_001"}
        ],
    )
    second = MagicMock(content="excerpt", tool_calls=[])
    librarian_llm = MagicMock()
    librarian_llm.ainvoke = AsyncMock(side_effect=[first, second])
    librarian_llm.bind_tools = MagicMock(return_value=librarian_llm)
    synth_llm = MagicMock()
    synth_llm.ainvoke = AsyncMock(return_value=AIMessage(content="answer"))

    fake_tool = MagicMock()
    fake_tool.name = "cg_find"
    fake_tool.invoke = MagicMock(return_value="row1\nrow2")

    extra = [
        patch(
            "graph_wiki_agent.commands.query.read_only_connect",
            return_value=MagicMock(),
        ),
        patch(
            "graph_wiki_agent.commands.query.build_graph_tools",
            return_value=[fake_tool],
        ),
        patch("graph_wiki_agent.commands.query.count_tokens", return_value=10),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
    ]
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _patches(vault, fan_result=None, librarian_llm=librarian_llm, synth_llm=synth_llm, extra_patches=extra)]
        _r, _b, _c, _e, _ro, _bt, _ct, mock_make_llm, mock_pool_cls = mocks
        mock_make_llm.side_effect = _mock_llm_for(librarian_llm, synth_llm)
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

    assert librarian_llm.ainvoke.await_count == 2
    fake_tool.invoke.assert_called_once_with({"name": "foo"})
    # Second ainvoke's first positional arg (messages list) should contain a ToolMessage
    second_msgs = librarian_llm.ainvoke.await_args_list[1].args[0]
    tool_msgs = [m for m in second_msgs if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].content == "row1\nrow2"


@pytest.mark.asyncio
async def test_librarian_loop_iter_cap(tmp_path: Path) -> None:
    """ainvoke always returns tool_calls → loop exits at _LIBRARIAN_MAX_ITERS."""
    from langchain_core.messages import AIMessage
    from subagent_runtime.pool import FanOutResult

    from graph_wiki_agent.commands.query import run_query

    vault = _make_vault(tmp_path)
    looping_resp = MagicMock(
        content="",
        tool_calls=[{"name": "cg_find", "args": {}, "id": "x"}],
    )
    librarian_llm = MagicMock()
    librarian_llm.ainvoke = AsyncMock(return_value=looping_resp)
    librarian_llm.bind_tools = MagicMock(return_value=librarian_llm)
    synth_llm = MagicMock()
    synth_llm.ainvoke = AsyncMock(return_value=AIMessage(content="answer"))

    fake_tool = MagicMock()
    fake_tool.name = "cg_find"
    fake_tool.invoke = MagicMock(return_value="rows")

    async def _fake_code_fallback(**_kw):
        return ("fallback answer", 0, 0)

    extra = [
        patch(
            "graph_wiki_agent.commands.query.read_only_connect",
            return_value=MagicMock(),
        ),
        patch(
            "graph_wiki_agent.commands.query.build_graph_tools",
            return_value=[fake_tool],
        ),
        patch("graph_wiki_agent.commands.query.count_tokens", return_value=10),
        patch("graph_wiki_agent.commands.query.make_llm"),
        patch("graph_wiki_agent.commands.query.SubagentPool"),
        patch(
            "graph_wiki_agent.commands.query._run_code_fallback",
            side_effect=_fake_code_fallback,
        ),
    ]
    with ExitStack() as stack:
        mocks = [stack.enter_context(p) for p in _patches(vault, fan_result=None, librarian_llm=librarian_llm, synth_llm=synth_llm, extra_patches=extra)]
        _r, _b, _c, _e, _ro, _bt, _ct, mock_make_llm, mock_pool_cls, _cf = mocks
        mock_make_llm.side_effect = _mock_llm_for(librarian_llm, synth_llm)
        mock_pool_inst = MagicMock()
        captured: list = []

        async def _fake_run_all(*, items, task, **_):
            for it in items:
                tr = await task(it)
                captured.append((it, tr.value if hasattr(tr, "value") else tr))
            return FanOutResult(successes=captured, errors=[])

        mock_pool_inst.run_all = AsyncMock(side_effect=_fake_run_all)
        mock_pool_cls.return_value = mock_pool_inst

        await run_query("q", workspace_path=vault, top_k=3)

    # 1 page * _LIBRARIAN_MAX_ITERS iterations
    assert librarian_llm.ainvoke.await_count == _LIBRARIAN_MAX_ITERS
    # drill_page returns NO_RELEVANT_CONTENT at the cap
    assert any(value == "NO_RELEVANT_CONTENT" for _, value in captured)


def test_pyproject_has_graph_io_and_langchain_aws_floor() -> None:
    """Sanity check that Plan 01's pyproject edits landed before Plan 02 ships."""
    here = Path(__file__).resolve()
    pyproject = (
        here.parent.parent.parent / "pyproject.toml"
    )  # agents/graph-wiki-agent/pyproject.toml
    text = pyproject.read_text()
    assert '"graph-io"' in text
    assert "langchain-aws>=1.4.7" in text
