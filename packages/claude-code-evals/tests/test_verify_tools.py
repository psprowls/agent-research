from __future__ import annotations

from claude_code_evals.schemas import ToolAssertion
from claude_code_evals.transcript import ToolCallEvent, Transcript
from claude_code_evals.verify.tools import _check_assertion


def _call(tool: str, inp: dict | None = None, *, seq: int = 0, source: str = "main") -> ToolCallEvent:
    inp = inp or {}
    return ToolCallEvent(tool=tool, input_keys=list(inp.keys()), input=inp, seq=seq, source=source)


def _transcript(*calls: ToolCallEvent, warnings: list[str] | None = None) -> Transcript:
    t = Transcript()
    t.tool_calls = list(calls)
    t.warnings = warnings or []
    return t


def _a(**kw) -> ToolAssertion:
    return ToolAssertion.model_validate(kw)


def test_presence_pass_and_fail():
    t = _transcript(_call("Skill", {"skill": "graph-wiki:scan"}))
    assert _check_assertion(_a(tool="Skill"), t)[0] is True
    assert _check_assertion(_a(tool="Edit"), t)[0] is False


def test_multi_param_and_on_same_call():
    t = _transcript(
        _call("Edit", {"file_path": "a.py", "old_string": "x"}, seq=0),
        _call("Edit", {"file_path": "b.py", "old_string": "y"}, seq=1),
    )
    # both regexes must hit the SAME call
    ok, _ = _check_assertion(_a(tool="Edit", params={"file_path": "a", "old_string": "x"}), t)
    assert ok is True
    ok, _ = _check_assertion(_a(tool="Edit", params={"file_path": "a", "old_string": "y"}), t)
    assert ok is False


def test_re_search_is_unanchored():
    t = _transcript(_call("Read", {"file_path": "deep/wiki/entities/pkg.md"}))
    assert _check_assertion(_a(tool="Read", params={"file_path": "wiki/entities/.*"}), t)[0] is True
    # anchoring works when requested
    assert _check_assertion(_a(tool="Read", params={"file_path": "^wiki/"}), t)[0] is False


def test_missing_param_means_no_match():
    t = _transcript(_call("Read", {"file_path": "a.md"}))
    assert _check_assertion(_a(tool="Read", params={"pattern": ".*"}), t)[0] is False


def test_non_string_param_json_serialized():
    t = _transcript(_call("Agent", {"run_in_background": True, "depth": 3}))
    assert _check_assertion(_a(tool="Agent", params={"run_in_background": "true"}), t)[0] is True
    assert _check_assertion(_a(tool="Agent", params={"depth": "^3$"}), t)[0] is True


def test_min_and_max_counts():
    t = _transcript(*[_call("Read", {"file_path": f"{i}.md"}, seq=i) for i in range(3)])
    assert _check_assertion(_a(tool="Read", min_count=3), t)[0] is True
    assert _check_assertion(_a(tool="Read", min_count=4), t)[0] is False
    assert _check_assertion(_a(tool="Read", max_count=3), t)[0] is True
    assert _check_assertion(_a(tool="Read", max_count=2), t)[0] is False
    assert _check_assertion(_a(tool="Read", min_count=1, max_count=3), t)[0] is True


def test_absent():
    t = _transcript(_call("Write", {"file_path": "wiki/entities/p.md"}))
    ok, reason = _check_assertion(_a(tool="Write", params={"file_path": "wiki/entities/.*"}, absent=True), t)
    assert ok is False
    assert "expected no" in reason
    ok, _ = _check_assertion(_a(tool="Write", params={"file_path": "^src/"}, absent=True), t)
    assert ok is True


def test_order_pass():
    t = _transcript(
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Bash", {"command": "ls"}, seq=1),
        _call("Edit", {"file_path": "src/StatusBadge.tsx"}, seq=2),
    )
    a = _a(
        order=[
            {"tool": "Read", "params": {"file_path": "StatusBadge"}},
            {"tool": "Edit", "params": {"file_path": "StatusBadge"}},
        ]
    )
    assert _check_assertion(a, t)[0] is True


def test_order_fail_when_reversed():
    t = _transcript(
        _call("Edit", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=1),
    )
    a = _a(
        order=[
            {"tool": "Read", "params": {"file_path": "StatusBadge"}},
            {"tool": "Edit", "params": {"file_path": "StatusBadge"}},
        ]
    )
    ok, reason = _check_assertion(a, t)
    assert ok is False
    assert "step 2" in reason


def test_order_with_interleaved_decoys():
    # decoy Edits on OTHER files between the real steps must not satisfy step 2
    t = _transcript(
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Edit", {"file_path": "src/Other.tsx"}, seq=1),
        _call("Edit", {"file_path": "src/StatusBadge.tsx"}, seq=2),
    )
    a = _a(
        order=[
            {"tool": "Read", "params": {"file_path": "StatusBadge"}},
            {"tool": "Edit", "params": {"file_path": "StatusBadge"}},
        ]
    )
    assert _check_assertion(a, t)[0] is True
    t2 = _transcript(
        _call("Read", {"file_path": "src/StatusBadge.tsx"}, seq=0),
        _call("Edit", {"file_path": "src/Other.tsx"}, seq=1),
    )
    assert _check_assertion(a, t2)[0] is False


def test_subagent_calls_excluded_by_default():
    t = _transcript(
        _call("Read", {"file_path": "main.md"}, seq=0, source="main"),
        _call("Read", {"file_path": "sub.md"}, seq=1, source="subagent"),
    )
    assert _check_assertion(_a(tool="Read", min_count=2), t)[0] is False
    assert _check_assertion(_a(tool="Read", min_count=2, include_subagents=True), t)[0] is True


def test_include_subagents_fails_with_warning_when_data_unavailable():
    t = _transcript(
        _call("Read", {"file_path": "main.md"}, seq=0),
        warnings=["subagent transcripts unavailable: projects dir missing"],
    )
    ok, reason = _check_assertion(_a(tool="Read", min_count=1, include_subagents=True), t)
    assert ok is False
    assert "subagent transcripts unavailable" in reason


def test_presence_failure_reports_near_miss():
    t = _transcript(_call("Skill", {"skill": "graph-wiki:lint"}))
    ok, reason = _check_assertion(_a(tool="Skill", params={"skill": "graph-wiki:scan"}), t)
    assert ok is False
    assert "graph-wiki:lint" in reason  # nearest near-miss quoted
