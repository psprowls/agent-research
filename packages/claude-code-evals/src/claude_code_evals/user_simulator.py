"""AutoUserSimulator: LLM-driven reply driver for multi-turn eval runs."""

from __future__ import annotations

from claude_code_evals.judge import _run_claude_judge
from claude_code_evals.schemas import AutoUser


class AutoUserSimulator:
    """Drive multi-turn conversations by calling claude -p for each reply.

    Stops when stop_on pattern appears in assistant text or max_replies exhausted.
    """

    def __init__(self, config: AutoUser) -> None:
        self._config = config
        self._reply_count = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def reply(self, assistant_text: str) -> str | None:
        """Return next user message, or None to stop the conversation."""
        if self._reply_count >= self._config.max_replies:
            return None
        if self._config.stop_on in assistant_text:
            return None

        prompt = f"{self._config.system_prompt}\n\nAgent said:\n{assistant_text}"
        result = _run_claude_judge(prompt, model=self._config.model)
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self._reply_count += 1
        return result.stdout
