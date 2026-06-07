from claude_code_evals.metrics import compute_metrics
from claude_code_evals.transcript import ToolCallEvent, Transcript


def _transcript(**kwargs) -> Transcript:
    defaults = dict(
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
        turn_count=2,
        tool_calls=[],
        tool_call_counts={},
        files_read=[],
        files_edited=[],
        files_written=[],
        subagent_dispatches=0,
        skill_invocations=[],
        hook_loaded_skills=[],
        permission_prompt_count=0,
        final_assistant_text="done",
    )
    defaults.update(kwargs)
    return Transcript(**defaults)


def test_basic_metrics():
    t = _transcript()
    m = compute_metrics(t, {"success": True})
    assert m["input_tokens"] == 100
    assert m["output_tokens"] == 50
    assert m["turn_count"] == 2
    assert m["verify_passed"] is True


def test_distinct_paths_touched():
    t = _transcript(
        files_read=["a.py", "b.py"],
        files_edited=["a.py"],
        files_written=["c.py"],
    )
    m = compute_metrics(t, {})
    assert m["distinct_paths_touched"] == 3  # a.py, b.py, c.py


def test_tool_calls_before_first_edit_no_edit():
    calls = [ToolCallEvent("Read", []), ToolCallEvent("Grep", [])]
    t = _transcript(tool_calls=calls)
    m = compute_metrics(t, {})
    assert m["tool_calls_before_first_edit"] == 2


def test_tool_calls_before_first_edit_with_edit():
    calls = [
        ToolCallEvent("Read", []),
        ToolCallEvent("Grep", []),
        ToolCallEvent("Edit", []),
        ToolCallEvent("Read", []),
    ]
    t = _transcript(tool_calls=calls)
    m = compute_metrics(t, {})
    assert m["tool_calls_before_first_edit"] == 2
