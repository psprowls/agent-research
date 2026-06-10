"""ToolsVerifier: pure-Python tool-call assertions against the in-memory Transcript."""

from __future__ import annotations

import json
import re

from deepeval.test_case import LLMTestCase

from claude_code_evals.schemas import ToolAssertion
from claude_code_evals.transcript import ToolCallEvent, Transcript
from claude_code_evals.verify.base import VerifierBase


def _param_value(call: ToolCallEvent, name: str) -> str | None:
    """The call's value for a param as a string, or None if the param is absent."""
    if name not in call.input:
        return None
    value = call.input[name]
    return value if isinstance(value, str) else json.dumps(value)


def _call_matches(call: ToolCallEvent, tool: str, params: dict[str, str]) -> bool:
    if call.tool != tool:
        return False
    for name, pattern in params.items():
        value = _param_value(call, name)
        if value is None or re.search(pattern, value) is None:
            return False
    return True


def _scoped_calls(transcript: Transcript, include_subagents: bool) -> list[ToolCallEvent]:
    calls = sorted(transcript.tool_calls, key=lambda c: c.seq)
    if include_subagents:
        return calls
    return [c for c in calls if c.source == "main"]


def _render_target(tool: str, params: dict[str, str]) -> str:
    if not params:
        return tool
    inner = ", ".join(f"{k}=~{v}" for k, v in params.items())
    return f"{tool}({inner})"


def _nearest_miss(assertion: ToolAssertion, calls: list[ToolCallEvent]) -> str:
    """Same-tool call whose params best matched, rendered for the failure reason."""
    assert assertion.tool is not None
    same_tool = [c for c in calls if c.tool == assertion.tool]
    if not same_tool or not assertion.params:
        return ""

    def matched_params(c: ToolCallEvent) -> int:
        return sum(
            1
            for name, pattern in assertion.params.items()
            if (v := _param_value(c, name)) is not None and re.search(pattern, v)
        )

    best = max(same_tool, key=matched_params)
    shown = ", ".join(f"{k}={_param_value(best, k)!r}" for k in assertion.params)
    return f"seq {best.seq} {assertion.tool} with {shown}"


def _check_counts(assertion: ToolAssertion, calls: list[ToolCallEvent]) -> tuple[bool, str]:
    assert assertion.tool is not None
    matches = [c for c in calls if _call_matches(c, assertion.tool, assertion.params)]
    n = len(matches)
    target = _render_target(assertion.tool, assertion.params)

    if assertion.absent:
        if n == 0:
            return True, ""
        return False, f"expected no {target} calls, found {n} (first at seq {matches[0].seq})"

    min_count = assertion.min_count
    if min_count is None and assertion.max_count is None:
        min_count = 1  # a bare assertion means "called at least once"

    if min_count is not None and n < min_count:
        reason = f"expected {target} >={min_count} time(s), found {n}"
        near = _nearest_miss(assertion, calls)
        if near:
            reason += f"; nearest miss: {near}"
        return False, reason
    if assertion.max_count is not None and n > assertion.max_count:
        return False, f"expected {target} <={assertion.max_count} time(s), found {n}"
    return True, ""


def _check_order(assertion: ToolAssertion, calls: list[ToolCallEvent]) -> tuple[bool, str]:
    assert assertion.order is not None
    idx = 0
    for step_num, step in enumerate(assertion.order, start=1):
        while idx < len(calls) and not _call_matches(calls[idx], step.tool, step.params):
            idx += 1
        if idx == len(calls):
            return (
                False,
                f"order: step {step_num} ({_render_target(step.tool, step.params)}) "
                "not found after the preceding steps",
            )
        idx += 1
    return True, ""


def _check_assertion(assertion: ToolAssertion, transcript: Transcript) -> tuple[bool, str]:
    if assertion.include_subagents:
        subagent_warnings = [w for w in transcript.warnings if "subagent transcripts unavailable" in w]
        has_subagent_calls = any(c.source == "subagent" for c in transcript.tool_calls)
        if subagent_warnings and not has_subagent_calls:
            return False, f"include_subagents requested but {subagent_warnings[0]}"
    calls = _scoped_calls(transcript, assertion.include_subagents)
    if assertion.order is not None:
        return _check_order(assertion, calls)
    return _check_counts(assertion, calls)


class ToolsVerifier(VerifierBase):
    """Evaluate tool-call assertions against the parsed Transcript.

    score = fraction of assertions passed; success requires all (threshold 1.0).
    """

    def __init__(self, *, assertions: list[ToolAssertion], transcript: Transcript) -> None:
        super().__init__(threshold=1.0)
        self._assertions = assertions
        self._transcript = transcript

    def measure(self, test_case: LLMTestCase) -> float:  # noqa: ARG002
        failures: list[str] = []
        for i, assertion in enumerate(self._assertions):
            passed, reason = _check_assertion(assertion, self._transcript)
            if not passed:
                failures.append(f"assertion[{i}]: {reason}")
        total = len(self._assertions)
        self.score = (total - len(failures)) / total if total else 1.0
        self.reason = f"all {total} tool assertion(s) passed" if not failures else "; ".join(failures)
        return self.score
