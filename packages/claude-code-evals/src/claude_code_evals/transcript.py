"""Parse Claude Code stream-json JSONL output into a structured Transcript."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolCallEvent:
    tool: str
    input_keys: list[str]
    input: dict = field(default_factory=dict)
    tool_use_id: str = ""
    seq: int = 0
    parent_tool_use_id: str | None = None
    source: str = "main"  # "main" | "subagent"
    feed: str = "stream"  # "stream" (main stream-json) | "jsonl" (subagent transcript file)


@dataclass
class Transcript:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    turn_count: int = 0
    tool_calls: list[ToolCallEvent] = field(default_factory=list)
    tool_call_counts: dict[str, int] = field(default_factory=dict)
    files_read: list[str] = field(default_factory=list)
    files_edited: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    subagent_dispatches: int = 0
    skill_invocations: list[str] = field(default_factory=list)
    hook_loaded_skills: list[str] = field(default_factory=list)
    permission_prompt_count: int = 0
    final_assistant_text: str = ""
    warnings: list[str] = field(default_factory=list)


_READ_TOOLS = {"Read", "Glob", "Grep"}
_EDIT_TOOLS = {"Edit"}
_WRITE_TOOLS = {"Write", "NotebookEdit"}


def parse_transcript(jsonl: str, *, subagent_projects_dir: Path | None = None) -> Transcript:
    """Parse stream-json JSONL into a Transcript.

    Processes each line as a JSON event. Unknown event types are silently
    skipped. JSONDecodeError lines are skipped.
    """
    t = Transcript()
    last_assistant_text = ""

    for line in jsonl.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue

        ev_type = ev.get("type")

        if ev_type == "assistant":
            t.turn_count += 1
            msg = ev.get("message") or {}
            parent_id = ev.get("parent_tool_use_id") or ev.get("parentToolUseId") or None
            text_parts: list[str] = []
            for block in msg.get("content") or []:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    _handle_tool_use(t, block, parent_tool_use_id=parent_id)
            if text_parts:
                last_assistant_text = "".join(text_parts)

        elif ev_type == "result":
            usage = ev.get("usage") or {}
            t.input_tokens = usage.get("input_tokens", 0)
            t.output_tokens = usage.get("output_tokens", 0)
            t.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            t.cache_write_tokens = usage.get("cache_creation_input_tokens", 0)

        elif ev_type == "permission":
            t.permission_prompt_count += 1

    t.final_assistant_text = last_assistant_text
    if subagent_projects_dir is not None:
        _merge_subagent_calls(t, subagent_projects_dir)
    return t


def _handle_tool_use(t: Transcript, block: dict, parent_tool_use_id: str | None = None) -> None:
    name = block.get("name", "")
    inp = block.get("input") or {}
    keys = list(inp.keys())

    t.tool_calls.append(
        ToolCallEvent(
            tool=name,
            input_keys=keys,
            input=inp,
            tool_use_id=block.get("id", ""),
            seq=len(t.tool_calls),
            parent_tool_use_id=parent_tool_use_id,
            source="subagent" if parent_tool_use_id else "main",
            feed="stream",
        )
    )
    t.tool_call_counts[name] = t.tool_call_counts.get(name, 0) + 1

    path = inp.get("file_path") or inp.get("path", "")
    if name in _READ_TOOLS and path:
        t.files_read.append(path)
    elif name in _EDIT_TOOLS and path:
        t.files_edited.append(path)
    elif name in _WRITE_TOOLS and path:
        t.files_written.append(path)
    elif name == "Agent":
        t.subagent_dispatches += 1
    elif name == "Skill":
        skill_name = inp.get("skill", "")
        if skill_name:
            t.skill_invocations.append(skill_name)


def _merge_subagent_calls(t: Transcript, projects_dir: Path) -> None:
    """Merge tool calls from subagent (sidechain) transcript JSONLs under projects_dir.

    Missing/unreadable files degrade to main-stream-only capture with a warning;
    merged calls never touch tool_call_counts/files_* so metrics.json is unaffected.
    """
    if not projects_dir.is_dir():
        if t.subagent_dispatches:
            t.warnings.append(f"subagent transcripts unavailable: {projects_dir} does not exist")
        return

    seen_ids = {c.tool_use_id for c in t.tool_calls if c.tool_use_id}
    for jsonl_path in sorted(projects_dir.glob("*/*.jsonl")):
        try:
            text = jsonl_path.read_text()
        except OSError as exc:
            t.warnings.append(f"subagent transcripts unavailable: {jsonl_path.name}: {exc}")
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant" or entry.get("isSidechain") is not True:
                continue
            parent_id = entry.get("parent_tool_use_id") or entry.get("parentToolUseId") or None
            msg = entry.get("message") or {}
            for block in msg.get("content") or []:
                if block.get("type") != "tool_use":
                    continue
                block_id = block.get("id", "")
                if block_id and block_id in seen_ids:
                    continue
                seen_ids.add(block_id)
                inp = block.get("input") or {}
                t.tool_calls.append(
                    ToolCallEvent(
                        tool=block.get("name", ""),
                        input_keys=list(inp.keys()),
                        input=inp,
                        tool_use_id=block_id,
                        seq=len(t.tool_calls),
                        parent_tool_use_id=parent_id,
                        source="subagent",
                        feed="jsonl",
                    )
                )


def extract_tool_calls_from_jsonl(raw_jsonl: str) -> list[dict[str, object]]:
    """Extract tool call details from raw stream-json output.

    Args:
        raw_jsonl: Raw output from claude -p in stream-json format (one JSON per line)

    Returns:
        List of dicts with keys: tool_name, tool_id, input_length (approx)
    """
    tool_calls: list[dict[str, object]] = []

    for line in raw_jsonl.splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            ev = json.loads(s)
        except json.JSONDecodeError:
            continue

        if ev.get("type") == "tool_call":
            tool_calls.append(
                {
                    "tool_name": ev.get("tool_name"),
                    "tool_id": ev.get("id"),
                    "input_length": len(json.dumps(ev.get("input", {}))),
                }
            )

    return tool_calls
