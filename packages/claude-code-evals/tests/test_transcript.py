from __future__ import annotations

import json

from claude_code_evals.transcript import Transcript, extract_tool_calls_from_jsonl, parse_transcript


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


def test_extract_tool_calls_empty():
    """Verify empty input returns empty list."""
    result = extract_tool_calls_from_jsonl("")
    assert result == []


def test_extract_tool_calls_single():
    """Verify extraction of single tool call."""
    tool_call_event = {
        "type": "tool_call",
        "tool_name": "Read",
        "id": "tc1",
        "input": {"file_path": "README.md"},
    }
    jsonl = json.dumps(tool_call_event)
    result = extract_tool_calls_from_jsonl(jsonl)

    assert len(result) == 1
    assert result[0]["tool_name"] == "Read"
    assert result[0]["tool_id"] == "tc1"
    assert isinstance(result[0]["input_length"], int)
    assert result[0]["input_length"] > 0


def test_extract_tool_calls_multiple():
    """Verify extraction of multiple tool calls."""
    event1 = {
        "type": "tool_call",
        "tool_name": "Read",
        "id": "tc1",
        "input": {"file_path": "README.md"},
    }
    event2 = {
        "type": "tool_call",
        "tool_name": "Edit",
        "id": "tc2",
        "input": {"file_path": "src/foo.py", "old_string": "a", "new_string": "b"},
    }
    jsonl = _make_jsonl(event1, event2)
    result = extract_tool_calls_from_jsonl(jsonl)

    assert len(result) == 2
    assert result[0]["tool_name"] == "Read"
    assert result[1]["tool_name"] == "Edit"


def test_extract_tool_calls_ignores_non_tool_events():
    """Verify non-tool_call events are skipped."""
    assistant_event = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Hello"}]},
    }
    tool_call_event = {
        "type": "tool_call",
        "tool_name": "Read",
        "id": "tc1",
        "input": {"file_path": "README.md"},
    }
    result_event = {
        "type": "result",
        "subtype": "success",
        "usage": {"input_tokens": 100},
    }
    jsonl = _make_jsonl(assistant_event, tool_call_event, result_event)
    result = extract_tool_calls_from_jsonl(jsonl)

    assert len(result) == 1
    assert result[0]["tool_name"] == "Read"


def test_extract_tool_calls_handles_malformed_json():
    """Verify malformed JSON lines are skipped gracefully."""
    good_event = {
        "type": "tool_call",
        "tool_name": "Read",
        "id": "tc1",
        "input": {"file_path": "README.md"},
    }
    jsonl = f"not valid json\n{json.dumps(good_event)}\n{{incomplete"
    result = extract_tool_calls_from_jsonl(jsonl)

    assert len(result) == 1
    assert result[0]["tool_name"] == "Read"


def test_extract_tool_calls_input_length():
    """Verify input_length is correctly calculated."""
    tool_call_event = {
        "type": "tool_call",
        "tool_name": "Write",
        "id": "tc1",
        "input": {
            "file_path": "output.txt",
            "content": "Hello, World!",
        },
    }
    jsonl = json.dumps(tool_call_event)
    result = extract_tool_calls_from_jsonl(jsonl)

    assert len(result) == 1
    # input_length should be the length of the JSON-encoded input dict
    expected_length = len(json.dumps({"file_path": "output.txt", "content": "Hello, World!"}))
    assert result[0]["input_length"] == expected_length
