"""AutoUserSimulator: LLM-driven reply driver for multi-turn eval runs."""

from __future__ import annotations

import re

from claude_code_evals.judge import _run_claude_judge
from claude_code_evals.schemas import AutoUser


class AutoUserSimulator:
    """Drive multi-turn conversations using a priority chain for each reply.

    Priority per turn:
    1. stop_on found in assistant text → end conversation (return None)
    2. max_replies budget exhausted → end conversation (return None)
    3. Trigger match (contains/regex) → return trigger.reply, reset consecutive defaults
    4. LLM call → return LLM reply, reset consecutive defaults
    5. LLM exception → fall back to default_reply:
       - if consecutive defaults >= abort_on_default_after → end conversation (return None)
       - else increment consecutive defaults and return default_reply
    """

    def __init__(self, config: AutoUser) -> None:
        self._config = config
        self._reply_count = 0
        self._consecutive_defaults = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def reply(self, assistant_text: str) -> str | None:
        """Return next user message, or None to end the conversation."""
        if self._config.stop_on in assistant_text:
            return None

        if self._reply_count >= self._config.max_replies:
            return None

        for trigger in self._config.triggers:
            if trigger.match.contains is not None:
                if trigger.match.contains in assistant_text:
                    self._reply_count += 1
                    self._consecutive_defaults = 0
                    return trigger.reply
            elif trigger.match.regex is not None:
                if re.search(trigger.match.regex, assistant_text):
                    self._reply_count += 1
                    self._consecutive_defaults = 0
                    return trigger.reply

        try:
            prompt = f"{self._config.system_prompt}\n\nAgent said:\n{assistant_text}"
            result = _run_claude_judge(prompt, model=self._config.model)
            self.input_tokens += result.input_tokens
            self.output_tokens += result.output_tokens
            self._reply_count += 1
            self._consecutive_defaults = 0
            return result.stdout
        except Exception:
            if self._consecutive_defaults > 0 and self._consecutive_defaults >= self._config.abort_on_default_after - 1:
                return None
            self._consecutive_defaults += 1
            self._reply_count += 1
            return self._config.default_reply
