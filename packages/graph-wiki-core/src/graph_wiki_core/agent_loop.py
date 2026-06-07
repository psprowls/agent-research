"""Reusable capped LangChain tool-call loop for graph-wiki agent roles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

_VALID_TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass(frozen=True)
class ToolLoopResult:
    status: str
    final_text: str
    error: str | None = None


def coerce_tool_name(raw_name: str, known_names: set[str]) -> str:
    """Coerce a model-emitted tool name to satisfy Bedrock's ``[a-zA-Z0-9_-]+`` rule.

    gpt-oss-class models occasionally echo a namespaced or malformed tool name
    (e.g. ``functions.read_repo_file``). Bedrock *accepts* such a name in a
    response but *rejects* it on the next request, so an un-coerced name poisons
    the replayed conversation history and aborts the whole loop. We first try to
    recover the intended tool by stripping a leading namespace; failing that we
    just make the name charset-valid so the existing unknown-tool path can guide
    the model.
    """
    if raw_name in known_names or _VALID_TOOL_NAME.match(raw_name):
        return raw_name
    candidate = re.split(r"[./:]", raw_name)[-1]
    candidate = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate)
    if candidate in known_names:
        return candidate
    return candidate or "unknown_tool"


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
            if not str(text).strip():
                return ToolLoopResult(status="failed", final_text="", error=f"{cap_label} returned empty response")
            return ToolLoopResult(status="ok", final_text=str(text))

        loop_messages.append(response)
        known_names = set(tool_by_name)
        for call in tool_calls:
            raw_name, call_args, call_id = tool_call_parts(call)
            call_name = coerce_tool_name(raw_name, known_names)
            if call_name != raw_name and isinstance(call, dict):
                # Repair the replayed history so Bedrock won't reject the next
                # request on a malformed toolUse.name (gpt-oss namespacing, etc.).
                call["name"] = call_name
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
