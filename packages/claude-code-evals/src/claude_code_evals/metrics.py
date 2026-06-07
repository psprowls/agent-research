"""Compute flat metrics dict from Transcript + verify result."""

from __future__ import annotations

from claude_code_evals.transcript import Transcript

_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _tool_calls_before_first_edit(transcript: Transcript) -> int:
    for i, call in enumerate(transcript.tool_calls):
        if call.tool in _EDIT_TOOLS:
            return i
    return len(transcript.tool_calls)


def compute_metrics(transcript: Transcript, verify_result: dict) -> dict:
    """Return flat metrics dict from a Transcript and verify result dict."""
    all_paths = set(transcript.files_read + transcript.files_edited + transcript.files_written)
    return {
        "input_tokens": transcript.input_tokens,
        "output_tokens": transcript.output_tokens,
        "cache_read_tokens": transcript.cache_read_tokens,
        "cache_write_tokens": transcript.cache_write_tokens,
        "turn_count": transcript.turn_count,
        "tool_call_counts": dict(transcript.tool_call_counts),
        "files_read_count": len(transcript.files_read),
        "files_edited_count": len(transcript.files_edited),
        "files_written_count": len(transcript.files_written),
        "tool_calls_before_first_edit": _tool_calls_before_first_edit(transcript),
        "distinct_paths_touched": len(all_paths),
        "subagent_dispatches": transcript.subagent_dispatches,
        "skill_invocations_count": len(transcript.skill_invocations),
        "permission_prompt_count": transcript.permission_prompt_count,
        "verify_passed": verify_result.get("success", False),
    }
