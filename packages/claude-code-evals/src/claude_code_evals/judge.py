"""ClaudeCodeJudge: a DeepEvalBaseLLM that uses `claude -p` as its backend."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass

from deepeval.models.base_model import DeepEvalBaseLLM


@dataclass
class JudgeResult:
    stdout: str
    input_tokens: int
    output_tokens: int


def _run_claude_judge(prompt: str, *, model: str) -> JudgeResult:
    """Spawn `claude -p --model <model> --output-format stream-json` and parse output.

    Security: cmd is always a list; prompt is the final element — never interpolated.
    """
    cmd = ["claude", "-p", "--model", model, "--output-format", "stream-json", prompt]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    text_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
        elif ev.get("type") == "result":
            usage = ev.get("usage") or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

    proc.wait()
    return JudgeResult(
        stdout="".join(text_parts),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


class ClaudeCodeJudge(DeepEvalBaseLLM):
    """DeepEvalBaseLLM implementation backed by `claude -p`."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self._model_name = model
        super().__init__(model=model)

    def load_model(self) -> ClaudeCodeJudge:
        """Return self as the model object."""
        return self

    def generate(self, prompt: str) -> str:
        return _run_claude_judge(prompt, model=self._model_name).stdout

    async def a_generate(self, prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, prompt)

    def get_model_name(self) -> str:
        return self._model_name
