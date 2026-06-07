"""RubricVerifier: GEval + ClaudeCodeJudge, privacy-scrubbed tool inputs."""

from __future__ import annotations

import subprocess
from pathlib import Path

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from claude_code_evals.judge import ClaudeCodeJudge
from claude_code_evals.transcript import Transcript
from claude_code_evals.verify.base import VerifierBase

_SCRUBBED_TOOLS = {"Edit", "Write", "Bash"}
_MAX_CHARS = 16_000


class RubricVerifier(VerifierBase):
    """Score using GEval with ClaudeCodeJudge backend.

    pass_threshold follows the 0–5 rubric scale: threshold=4 → 0.8 normalised.
    """

    def __init__(
        self,
        *,
        rubric_path: Path,
        worktree_path: Path,
        transcript: Transcript,
        judge_model: str = "claude-haiku-4-5-20251001",
        pass_threshold: float = 4.0,
    ) -> None:
        normalised_threshold = pass_threshold / 5.0
        super().__init__(threshold=normalised_threshold)
        self._rubric_path = rubric_path
        self._worktree_path = worktree_path
        self._transcript = transcript
        self._judge_model = judge_model

    def measure(self, test_case: LLMTestCase) -> float:
        rubric_text = self._rubric_path.read_text()
        assistant_text = self._transcript.final_assistant_text[:_MAX_CHARS]
        tool_summary = self._build_tool_summary()
        diff_text = self._get_diff()

        augmented_output = (
            f"{assistant_text}\n\n<tool_summary>\n{tool_summary}\n</tool_summary>\n\n<diff>\n{diff_text}\n</diff>"
        )
        augmented_tc = LLMTestCase(
            input=test_case.input,
            actual_output=augmented_output,
        )

        judge = ClaudeCodeJudge(model=self._judge_model)
        metric = GEval(
            name="rubric",
            criteria=rubric_text,
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],  # type: ignore[attr-defined]
            model=judge,  # ALWAYS explicit — deepeval defaults to OpenAI when omitted
            threshold=self.threshold,
        )
        metric.measure(augmented_tc)
        self.score = metric.score or 0.0
        self.reason = metric.reason or ""
        return self.score

    def _build_tool_summary(self) -> str:
        lines = []
        for call in self._transcript.tool_calls:
            if call.tool in _SCRUBBED_TOOLS:
                lines.append(f"{call.tool}({', '.join(call.input_keys)})")
            else:
                lines.append(call.tool)
        return "\n".join(lines)

    def _get_diff(self) -> str:
        subprocess.run(["git", "add", "-N", "."], cwd=str(self._worktree_path), capture_output=True)
        result = subprocess.run(
            ["git", "diff"],
            cwd=str(self._worktree_path),
            capture_output=True,
            text=True,
        )
        return result.stdout[:_MAX_CHARS]
