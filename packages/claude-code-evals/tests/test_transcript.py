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


# --- ToolCallEvent enrichment (tools.json capture) ---


def test_tool_call_full_input_captured():
    t = parse_transcript(_make_jsonl(EDIT_EVENT))
    call = t.tool_calls[0]
    assert call.input == {"file_path": "src/foo.py", "old_string": "a", "new_string": "b"}
    assert call.input_keys == ["file_path", "old_string", "new_string"]
    assert call.tool_use_id == "tu2"


def test_tool_call_seq_is_global_order():
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT, EDIT_EVENT))
    assert [c.seq for c in t.tool_calls] == [0, 1]
    assert [c.tool for c in t.tool_calls] == ["Read", "Edit"]


def test_main_stream_call_defaults():
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT))
    call = t.tool_calls[0]
    assert call.source == "main"
    assert call.parent_tool_use_id is None
    assert call.feed == "stream"


def test_main_stream_subagent_tagged_call():
    ev = {
        "type": "assistant",
        "parent_tool_use_id": "toolu_parent01",
        "message": {"content": [{"type": "tool_use", "id": "tu9", "name": "Read", "input": {"file_path": "x.md"}}]},
    }
    t = parse_transcript(_make_jsonl(ev))
    call = t.tool_calls[0]
    assert call.source == "subagent"
    assert call.parent_tool_use_id == "toolu_parent01"
    assert call.feed == "stream"


def test_main_stream_subagent_camelcase_tag():
    ev = {
        "type": "assistant",
        "parentToolUseId": "toolu_parent02",
        "message": {"content": [{"type": "tool_use", "id": "tu10", "name": "Bash", "input": {"command": "ls"}}]},
    }
    t = parse_transcript(_make_jsonl(ev))
    assert t.tool_calls[0].parent_tool_use_id == "toolu_parent02"
    assert t.tool_calls[0].source == "subagent"


# --- subagent JSONL merge ---


def _write_subagent_jsonl(projects_dir, entries, rel="myproj/session-1.jsonl"):
    path = projects_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries))
    return path


SIDECHAIN_ENTRY = {
    "type": "assistant",
    "isSidechain": True,
    "message": {"content": [{"type": "tool_use", "id": "sub_tu1", "name": "Grep", "input": {"pattern": "foo"}}]},
}


def test_subagent_jsonl_merged_after_stream_calls(tmp_path):
    projects = tmp_path / "projects"
    _write_subagent_jsonl(projects, [SIDECHAIN_ENTRY])
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=projects)
    assert len(t.tool_calls) == 2
    merged = t.tool_calls[1]
    assert merged.tool == "Grep"
    assert merged.input == {"pattern": "foo"}
    assert merged.source == "subagent"
    assert merged.feed == "jsonl"
    assert merged.seq == 1
    assert t.warnings == []


def test_subagent_jsonl_dedupes_by_tool_use_id(tmp_path):
    projects = tmp_path / "projects"
    dup = {
        "type": "assistant",
        "isSidechain": True,
        "message": {
            "content": [{"type": "tool_use", "id": "tu1", "name": "Read", "input": {"file_path": "README.md"}}]
        },
    }
    _write_subagent_jsonl(projects, [dup])
    # ASSISTANT_EVENT's Read already has id tu1 in the main stream
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=projects)
    assert len(t.tool_calls) == 1


def test_subagent_jsonl_skips_non_sidechain_entries(tmp_path):
    projects = tmp_path / "projects"
    main_session = {
        "type": "assistant",
        "isSidechain": False,
        "message": {"content": [{"type": "tool_use", "id": "main_tu", "name": "Bash", "input": {"command": "ls"}}]},
    }
    _write_subagent_jsonl(projects, [main_session])
    t = parse_transcript("", subagent_projects_dir=projects)
    assert t.tool_calls == []


def test_subagent_jsonl_malformed_lines_skipped(tmp_path):
    projects = tmp_path / "projects"
    path = projects / "myproj" / "session-1.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("not json\n" + json.dumps(SIDECHAIN_ENTRY) + "\n{broken")
    t = parse_transcript("", subagent_projects_dir=projects)
    assert [c.tool for c in t.tool_calls] == ["Grep"]


def test_subagent_jsonl_calls_do_not_touch_counts_or_files(tmp_path):
    projects = tmp_path / "projects"
    sidechain_read = {
        "type": "assistant",
        "isSidechain": True,
        "message": {
            "content": [{"type": "tool_use", "id": "sub_tu2", "name": "Read", "input": {"file_path": "sub.md"}}]
        },
    }
    _write_subagent_jsonl(projects, [sidechain_read])
    t = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=projects)
    # metrics inputs unchanged: only the main-stream Read is counted
    assert t.tool_call_counts == {"Read": 1}
    assert t.files_read == ["README.md"]


def test_missing_projects_dir_warns_only_with_dispatches(tmp_path):
    agent_event = {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": "tu4", "name": "Agent", "input": {"prompt": "go"}}]},
    }
    missing = tmp_path / "projects"  # never created
    t = parse_transcript(_make_jsonl(agent_event), subagent_projects_dir=missing)
    assert len(t.warnings) == 1
    assert "subagent transcripts unavailable" in t.warnings[0]

    t2 = parse_transcript(_make_jsonl(ASSISTANT_EVENT), subagent_projects_dir=missing)
    assert t2.warnings == []


def test_unreadable_jsonl_file_warns(tmp_path):
    projects = tmp_path / "projects"
    # a directory named *.jsonl makes read_text raise IsADirectoryError (an OSError)
    (projects / "myproj" / "bad.jsonl").mkdir(parents=True)
    t = parse_transcript("", subagent_projects_dir=projects)
    assert len(t.warnings) == 1
    assert "subagent transcripts unavailable" in t.warnings[0]


def test_parse_transcript_sums_usage_across_multi_turn_results():
    """Multi-turn streams emit one result per turn with per-turn (not cumulative) usage.

    Verified empirically 2026-06-11 via a real 2-turn claude CLI capture:
      turn-1 usage = {"input_tokens": 10, "cache_creation_input_tokens": 11976,
                      "cache_read_input_tokens": 18521, "output_tokens": 531}
      turn-2 usage = {"input_tokens": 10, "cache_creation_input_tokens": 845,
                      "cache_read_input_tokens": 30497, "output_tokens": 79}
    turn-2 output_tokens (79) < turn-1 output_tokens (531) — cannot be cumulative.
    Totals must be summed across result events; last-result-wins undercounts.
    """
    result_1 = {
        "type": "result",
        "subtype": "success",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 10,
            "cache_read_input_tokens": 50,
            "cache_creation_input_tokens": 5,
        },
    }
    result_2 = {
        "type": "result",
        "subtype": "success",
        "usage": {
            "input_tokens": 200,
            "output_tokens": 20,
            "cache_read_input_tokens": 60,
            "cache_creation_input_tokens": 3,
        },
    }
    t = parse_transcript(_make_jsonl(result_1, result_2))
    assert t.input_tokens == 300
    assert t.output_tokens == 30
    assert t.cache_read_tokens == 110
    assert t.cache_write_tokens == 8
