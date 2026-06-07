"""Reusable capped LangChain tool-call loop for graph-wiki agent roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class ToolLoopResult:
    status: str
    final_text: str
    error: str | None = None


def tool_call_parts(call: Any) -> tuple[str, dict[str, Any], str]:
    if not isinstance(call, dict):
        return "", {}, ""
    name = str(call.get("name", ""))
    args = call.get("args", {})
    if not isinstance(args, dict):
        args = {}
    call_id = str(call.get("id", ""))
    return name, args, call_id


async def run_tool_loop(
    *,
    llm: Any,
    tools: list[BaseTool],
    messages: list[Any],
    max_iterations: int,
    cap_label: str = "tool loop",
) -> ToolLoopResult:
    bound_llm = llm.bind_tools(tools) if tools else llm
    tool_by_name = {agent_tool.name: agent_tool for agent_tool in tools}
    loop_messages = list(messages)
    last_text = ""

    for _iteration in range(max_iterations):
        response = await bound_llm.ainvoke(loop_messages)
        text = getattr(response, "content", "") or ""
        if text:
            last_text = str(text)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return ToolLoopResult(status="ok", final_text=str(text))

        loop_messages.append(response)
        for call in tool_calls:
            call_name, call_args, call_id = tool_call_parts(call)
            agent_tool = tool_by_name.get(call_name)
            if agent_tool is None:
                tool_output = f"ERROR: unknown tool {call_name!r}"
            else:
                try:
                    tool_output = agent_tool.invoke(call_args)
                except Exception as exc:
                    tool_output = f"ERROR: {exc}"
            if not isinstance(tool_output, str):
                tool_output = str(tool_output)
            loop_messages.append(ToolMessage(content=tool_output, tool_call_id=call_id))

    if last_text:
        return ToolLoopResult(
            status="ok",
            final_text=last_text,
            error=f"{cap_label} hit iteration cap ({max_iterations}) after producing text",
        )
    return ToolLoopResult(
        status="failed",
        final_text="",
        error=f"{cap_label} hit iteration cap ({max_iterations})",
    )
