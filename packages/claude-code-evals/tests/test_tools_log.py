from __future__ import annotations

import json

from claude_code_evals.tools_log import TRUNCATE_CHARS, render_tools_json
from claude_code_evals.transcript import ToolCallEvent, Transcript


def _transcript(*calls: ToolCallEvent, warnings: list[str] | None = None) -> Transcript:
    t = Transcript()
    t.tool_calls = list(calls)
    t.warnings = warnings or []
    return t


def _call(tool: str = "Read", inp: dict | None = None, **kw) -> ToolCallEvent:
    inp = inp if inp is not None else {"file_path": "README.md"}
    return ToolCallEvent(tool=tool, input_keys=list(inp.keys()), input=inp, **kw)


def test_render_shape():
    t = _transcript(
        _call(seq=0),
        _call(
            tool="Write",
            inp={"file_path": "out.md", "content": "x"},
            seq=1,
            source="subagent",
            parent_tool_use_id="toolu_01abc",
        ),
    )
    doc = render_tools_json(t)
    assert doc["total_calls"] == 2
    assert doc["warnings"] == []
    assert doc["calls"][0] == {
        "seq": 0,
        "tool": "Read",
        "source": "main",
        "parent_tool_use_id": None,
        "input": {"file_path": "README.md"},
    }
    assert doc["calls"][1]["source"] == "subagent"
    assert doc["calls"][1]["parent_tool_use_id"] == "toolu_01abc"
    json.dumps(doc)  # must be JSON-serializable


def test_string_truncation_boundary():
    under = "a" * (TRUNCATE_CHARS - 1)
    at = "a" * TRUNCATE_CHARS
    over = "a" * (TRUNCATE_CHARS + 1)
    t = _transcript(_call(inp={"u": under, "a": at, "o": over}))
    out = render_tools_json(t)["calls"][0]["input"]
    assert out["u"] == under
    assert out["a"] == at
    assert out["o"] == "a" * TRUNCATE_CHARS + f"…[truncated, {TRUNCATE_CHARS + 1} chars total]"


def test_small_nested_value_stays_native():
    t = _transcript(_call(tool="mcp__x__y", inp={"opts": {"depth": 2}, "n": 7}))
    out = render_tools_json(t)["calls"][0]["input"]
    assert out["opts"] == {"depth": 2}
    assert out["n"] == 7


def test_large_nested_value_serialized_and_truncated():
    big = {"items": ["x" * 50] * 20}  # json.dumps well over the cap
    rendered = json.dumps(big)
    assert len(rendered) > TRUNCATE_CHARS  # sanity
    t = _transcript(_call(inp={"payload": big}))
    out = render_tools_json(t)["calls"][0]["input"]["payload"]
    assert isinstance(out, str)
    assert out.startswith(rendered[:TRUNCATE_CHARS])
    assert out.endswith(f"…[truncated, {len(rendered)} chars total]")


def test_warnings_passed_through():
    t = _transcript(warnings=["subagent transcripts unavailable: boom"])
    assert render_tools_json(t)["warnings"] == ["subagent transcripts unavailable: boom"]
