from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool


@pytest.mark.asyncio
async def test_run_tool_loop_returns_terminal_no_tool_response() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="final answer", tool_calls=[]))

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "final answer"
    assert result.error is None
    assert llm.bind_tools.call_count == 0
    assert llm.ainvoke.call_count == 1


@pytest.mark.asyncio
async def test_run_tool_loop_dispatches_one_tool_call_and_feeds_result_back() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    @tool
    def echo(value: str) -> str:
        """Echo a value."""
        return f"tool:{value}"

    first = MagicMock(content="", tool_calls=[{"name": "echo", "args": {"value": "one"}, "id": "call_1"}])
    second = MagicMock(content="done", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

    result = await run_tool_loop(
        llm=llm,
        tools=[echo],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "done"
    assert result.error is None
    assert llm.bind_tools.call_count == 1
    second_messages = llm.ainvoke.call_args_list[1].args[0]
    assert second_messages[-1] == ToolMessage(content="tool:one", tool_call_id="call_1")


@pytest.mark.asyncio
async def test_run_tool_loop_turns_unknown_tool_into_tool_message() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    first = MagicMock(content="", tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}])
    second = MagicMock(content="recovered", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "recovered"
    second_messages = llm.ainvoke.call_args_list[1].args[0]
    assert second_messages[-1] == ToolMessage(content="ERROR: unknown tool 'missing_tool'", tool_call_id="call_1")


@pytest.mark.asyncio
async def test_run_tool_loop_turns_tool_exception_into_tool_message() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    @tool
    def explode() -> str:
        """Raise a controlled error."""
        raise RuntimeError("boom")

    first = MagicMock(content="", tool_calls=[{"name": "explode", "args": {}, "id": "call_1"}])
    second = MagicMock(content="recovered", tool_calls=[])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first, second])

    result = await run_tool_loop(
        llm=llm,
        tools=[explode],
        messages=[HumanMessage(content="hello")],
        max_iterations=3,
    )

    assert result.status == "ok"
    assert result.final_text == "recovered"
    second_messages = llm.ainvoke.call_args_list[1].args[0]
    assert second_messages[-1] == ToolMessage(content="ERROR: boom", tool_call_id="call_1")


@pytest.mark.asyncio
async def test_run_tool_loop_iteration_cap_with_prior_text_returns_ok_with_error() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    first = MagicMock(content="partial answer", tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=first)

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=1,
    )

    assert result.status == "ok"
    assert result.final_text == "partial answer"
    assert result.error == "tool loop hit iteration cap (1) after producing text"


@pytest.mark.asyncio
async def test_run_tool_loop_iteration_cap_without_prior_text_returns_failed() -> None:
    from graph_wiki_core.agent_loop import run_tool_loop

    first = MagicMock(content="", tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_1"}])
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=first)

    result = await run_tool_loop(
        llm=llm,
        tools=[],
        messages=[HumanMessage(content="hello")],
        max_iterations=1,
    )

    assert result.status == "failed"
    assert result.final_text == ""
    assert result.error == "tool loop hit iteration cap (1)"
