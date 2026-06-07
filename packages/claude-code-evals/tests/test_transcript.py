from __future__ import annotations

import json

from claude_code_evals.transcript import Transcript, parse_transcript


def _make_jsonl(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


ASSISTANT_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {"type": "text", "text": "Hello"},
            {
                "type": "tool_use",
                "id": "tu1",
                "name": "Read",
                "input": {"file_path": "README.md"},
            },
        ]
    },
}

TOOL_RESULT_EVENT = {
    "type": "user",
    "message": {"content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "content"}]},
}

EDIT_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {
                "type": "tool_use",
                "id": "tu2",
                "name": "Edit",
                "input": {"file_path": "src/foo.py", "old_string": "a", "new_string": "b"},
            }
        ]
    },
}

RESULT_EVENT = {
    "type": "result",
    "subtype": "success",
    "usage": {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 20,
        "cache_creation_input_tokens": 10,
    },
}


def test_parse_empty():
    t = parse_transcript("")
    assert isinstance(t, Transcript)
    assert t.turn_count == 0
    assert t.input_tokens == 0


def test_parse_token_usage():
    jsonl = _make_jsonl(RESULT_EVENT)
    t = parse_transcript(jsonl)
    assert t.input_tokens == 100
    assert t.output_tokens == 50
    assert t.cache_read_tokens == 20
    assert t.cache_write_tokens == 10


def test_parse_turn_count():
    jsonl = _make_jsonl(ASSISTANT_EVENT, TOOL_RESULT_EVENT, ASSISTANT_EVENT)
    t = parse_transcript(jsonl)
    assert t.turn_count == 2


def test_parse_tool_calls():
    jsonl = _make_jsonl(ASSISTANT_EVENT)
    t = parse_transcript(jsonl)
    assert t.tool_call_counts["Read"] == 1
    assert len(t.tool_calls) == 1
    assert t.tool_calls[0].tool == "Read"


def test_files_read():
    jsonl = _make_jsonl(ASSISTANT_EVENT)
    t = parse_transcript(jsonl)
    assert "README.md" in t.files_read


def test_files_edited():
    jsonl = _make_jsonl(EDIT_EVENT)
    t = parse_transcript(jsonl)
    assert "src/foo.py" in t.files_edited


def test_files_written():
    write_event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu3",
                    "name": "Write",
                    "input": {"file_path": "out.txt", "content": "x"},
                }
            ]
        },
    }
    jsonl = _make_jsonl(write_event)
    t = parse_transcript(jsonl)
    assert "out.txt" in t.files_written


def test_final_assistant_text():
    jsonl = _make_jsonl(ASSISTANT_EVENT, RESULT_EVENT)
    t = parse_transcript(jsonl)
    assert t.final_assistant_text == "Hello"


def test_subagent_dispatches():
    agent_event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu4",
                    "name": "Agent",
                    "input": {"prompt": "do something"},
                }
            ]
        },
    }
    jsonl = _make_jsonl(agent_event)
    t = parse_transcript(jsonl)
    assert t.subagent_dispatches == 1


def test_permission_prompt_count():
    perm_event = {"type": "permission", "tool": "Bash", "input": {}}
    jsonl = _make_jsonl(perm_event)
    t = parse_transcript(jsonl)
    assert t.permission_prompt_count == 1


def test_skill_invocations():
    skill_event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu5",
                    "name": "Skill",
                    "input": {"skill": "my-skill"},
                }
            ]
        },
    }
    jsonl = _make_jsonl(skill_event)
    t = parse_transcript(jsonl)
    assert "my-skill" in t.skill_invocations
