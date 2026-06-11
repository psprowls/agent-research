"""AutoUserSimulator: Bedrock-LLM-driven reply driver for multi-turn eval runs."""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from model_adapter import make_llm

from claude_code_evals.schemas import AutoUser


class AutoUserSimulator:
    """Drive multi-turn conversations using a priority chain for each reply.

    Matching scopes: ``stop_on`` and triggers scan the turn's full text (all
    text blocks concatenated); the LLM conversation history records only the
    turn's final text block per agent turn.

    Priority per turn:
    1. stop_on found in full turn text → end conversation (return None)
    2. max_replies budget exhausted → end conversation (return None)
    3. Trigger match (contains/regex) on full turn text → trigger.reply,
       reset consecutive defaults
    4. LLM call on the conversation history → LLM reply, reset consecutive
       defaults
    5. LLM exception (including BedrockAccessDenied) → default chain:
       once abort_on_default_after consecutive default replies have been
       SENT, end the conversation (return None); otherwise send
       default_reply. ``abort_on_default_after: 2`` → two defaults max.

    Fully synchronous by design: _GuardedChatBedrockConverse guards sync
    ``invoke`` (AccessDeniedException → BedrockAccessDenied); the async
    runner calls ``reply`` via ``asyncio.to_thread``.
    """

    def __init__(self, config: AutoUser, task_prompt: str) -> None:
        self._config = config
        self._llm = make_llm("user_simulator", model_override=config.model)
        self._history: list[BaseMessage] = [
            SystemMessage(content=f"{config.system_prompt}\n\nThe agent was given this task:\n{task_prompt}")
        ]
        self._reply_count = 0
        self._consecutive_defaults = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def reply(self, full_text: str, final_block: str) -> str | None:
        """Return the next user message, or None to end the conversation."""
        self._history.append(HumanMessage(content=final_block))

        if self._config.stop_on in full_text:
            return None

        if self._reply_count >= self._config.max_replies:
            return None

        for trigger in self._config.triggers:
            if trigger.match.contains is not None:
                matched = trigger.match.contains in full_text
            else:
                matched = re.search(trigger.match.regex or "", full_text) is not None
            if matched:
                self._consecutive_defaults = 0
                return self._send(trigger.reply)

        try:
            response = self._llm.invoke(self._history)
        except Exception:
            if self._consecutive_defaults >= self._config.abort_on_default_after:
                return None
            self._consecutive_defaults += 1
            return self._send(self._config.default_reply)

        usage = getattr(response, "usage_metadata", None) or {}
        self.input_tokens += usage.get("input_tokens", 0)
        self.output_tokens += usage.get("output_tokens", 0)
        self._consecutive_defaults = 0
        # The adapter's _normalize_content guarantees a plain str at runtime;
        # the isinstance check narrows the str | list[str | dict] annotation.
        content = response.content
        return self._send(content if isinstance(content, str) else str(content))

    def _send(self, text: str) -> str:
        """Record a sent reply: count it and append it to the LLM history."""
        self._reply_count += 1
        self._history.append(AIMessage(content=text))
        return text
