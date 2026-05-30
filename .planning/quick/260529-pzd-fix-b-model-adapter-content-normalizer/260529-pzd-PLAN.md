---
phase: quick-260529-pzd
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/model-adapter/src/model_adapter/loader.py
  - packages/model-adapter/tests/test_loader.py
autonomous: true
requirements: [FIX-B]

must_haves:
  truths:
    - "A list-shaped AIMessage.content is collapsed to a plain str on .content"
    - "Dropped reasoning/thinking blocks are preserved on additional_kwargs['reasoning']"
    - "Both sync invoke and async ainvoke normalize content and translate AccessDenied"
    - "String-content and non-message returns pass through unchanged"
  artifacts:
    - path: "packages/model-adapter/src/model_adapter/loader.py"
      provides: "_normalize_content helper + ainvoke override on _GuardedChatBedrockConverse"
      contains: "_normalize_content"
    - path: "packages/model-adapter/tests/test_loader.py"
      provides: "sync + async normalization tests and async AccessDenied test"
      contains: "ainvoke"
  key_links:
    - from: "_GuardedChatBedrockConverse.invoke"
      to: "_normalize_content"
      via: "return _normalize_content(response)"
      pattern: "_normalize_content\\(response\\)"
    - from: "_GuardedChatBedrockConverse.ainvoke"
      to: "_original_ainvoke"
      via: "await self._original_ainvoke(...)"
      pattern: "await self\\._original_ainvoke"
---

<objective>
Add a content normalizer at the model-adapter boundary so every consumer receives
a plain `str` on `response.content`, regardless of whether the model returned
plain-string content or a list of content blocks (text + reasoning). Extend the
AccessDenied guard to the async path while in here.

Purpose: list-shaped ("thinking"/multi-block) content currently breaks downstream
`.strip()` and regex consumers (synthesizer, ingestor). gpt-oss-120b and
minimax-m2.5 proved the trigger is content SHAPE, not model ID — so detection is
`isinstance(response.content, list)`, never a model-name check. Decision LOCKED:
preserve reasoning blocks (do not drop them).

Output: `_normalize_content` module helper + `ainvoke`/`_original_ainvoke` on
`_GuardedChatBedrockConverse`, with offline sync+async tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@packages/model-adapter/src/model_adapter/loader.py
@packages/model-adapter/tests/test_loader.py

<interfaces>
<!-- Verified content-block shapes from langchain-aws bedrock_converse.py docstring. -->
<!-- response.content is a Python list of dicts (or bare str items) when multi-block: -->
<!--   text block:      {'type': 'text', 'text': '...'} -->
<!--   reasoning block: {'type': 'reasoning_content', 'reasoning_content': {'type': 'text', 'text': '...', 'signature': '...'}} -->
<!--   bare str item:   treat as text -->
<!-- AIMessage is mutable: response.content = "..." and response.additional_kwargs["reasoning"] = [...] both work. -->
<!--   additional_kwargs defaults to {} on langchain_core AIMessage. -->

Existing guard surface (loader.py):
  _format_access_denied_message(model_id, original) -> str   # KEEP message text EXACTLY
  class _GuardedChatBedrockConverse(ChatBedrockConverse):
      _model_id_for_errors: str
      _original_invoke(self, *args, **kwargs)   # defers to ChatBedrockConverse.invoke(self, ...)
      invoke(self, *args, **kwargs)             # try _original_invoke; translate AccessDeniedException ClientError
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add _normalize_content helper and async-capable guard to loader.py</name>
  <files>packages/model-adapter/src/model_adapter/loader.py</files>
  <behavior>
    - _normalize_content(response): when getattr(response, "content", None) is not a list, return response unchanged (covers bare object() and str-content messages).
    - List content: bare str items and dicts with type=="text" → joined into response.content; all other blocks collected.
    - Non-empty reasoning blocks → response.additional_kwargs["reasoning"]; if additional_kwargs is None, assign a fresh dict first.
    - invoke and ainvoke both translate AccessDeniedException ClientError → BedrockAccessDenied (message text unchanged) and return _normalize_content(response) on success.
  </behavior>
  <action>
    Add a module-level helper `_normalize_content(response)`:
    - `content = getattr(response, "content", None)`; if `not isinstance(content, list)`, return response unchanged.
    - Iterate blocks accumulating `text_parts` and `reasoning_blocks`: bare `str` → append to text_parts; `dict` with `block.get("type") == "text"` → append `block.get("text", "")`; any other block → append to reasoning_blocks.
    - Set `response.content = "".join(text_parts)`.
    - If reasoning_blocks: if `response.additional_kwargs` is None, set it to a fresh dict, then set `response.additional_kwargs["reasoning"] = reasoning_blocks`.
    - Return response.

    Factor the AccessDenied translation into `_wrap_client_error(self, e)` on the class: returns a `BedrockAccessDenied` (built via the existing `_format_access_denied_message(self._model_id_for_errors, e)`) when the ClientError Code is "AccessDeniedException", else `None`. Do NOT change the message text — the existing test asserts on the ARN, "bedrock:InvokeModel", and "arn:aws:bedrock:*::foundation-model/*".

    Rewrite `invoke`: try `self._original_invoke(*args, **kwargs)`; on `botocore.exceptions.ClientError as e`, `wrapped = self._wrap_client_error(e)`; `if wrapped is not None: raise wrapped from e` else `raise`; on success `return _normalize_content(response)`.

    Add `_original_ainvoke(self, *args, **kwargs)` (async) that `return await ChatBedrockConverse.ainvoke(self, *args, **kwargs)`. Add async `ainvoke` mirroring `invoke`: `response = await self._original_ainvoke(...)` inside the same ClientError guard, returning `_normalize_content(response)` on success.

    Keep `_original_invoke`, `_model_id_for_errors`, and all existing behavior intact — existing monkeypatch tests set `llm._original_invoke` and the success test returns a bare `object()` (must pass through unchanged because `getattr(object(), "content", None)` is not a list).
  </action>
  <verify>
    <automated>uv run --package model-adapter pytest packages/model-adapter -q -k "invoke or normalize or access_denied"</automated>
  </verify>
  <done>_normalize_content + _wrap_client_error + _original_ainvoke + ainvoke exist; invoke/ainvoke both normalize on success and translate AccessDenied; existing loader tests still pass.</done>
</task>

<task type="auto">
  <name>Task 2: Add offline sync + async normalization and async AccessDenied tests</name>
  <files>packages/model-adapter/tests/test_loader.py</files>
  <action>
    Add tests using the real `langchain_core.messages.AIMessage` (no Bedrock calls). Build a fake list-shaped message: `content = [reasoning_block, text_block_1, text_block_2]` where reasoning_block is `{'type': 'reasoning_content', 'reasoning_content': {'type': 'text', 'text': 'thinking...', 'signature': 'sig'}}` and the text blocks are `{'type': 'text', 'text': 'Hello'}` / `{'type': 'text', 'text': ' world'}`.

    - Sync: `llm = make_llm("preflight")`; monkeypatch `llm._original_invoke` to return the list-shaped message; after `llm.invoke("ping")` assert `.content == "Hello world"` and `additional_kwargs["reasoning"]` contains the reasoning block.
    - Async: monkeypatch `llm._original_ainvoke` to an `async def` returning the same message; `result = await llm.ainvoke("ping")`; assert the same `.content` and `additional_kwargs["reasoning"]`. Use a plain `async def test_...` (asyncio_mode="auto" per CLAUDE.md).
    - Pass-through: a string-content `AIMessage("plain text")` through `invoke` stays a `str` and gains no "reasoning" key.
    - Async AccessDenied: monkeypatch `llm._original_ainvoke` to an `async def` that raises `_build_client_error("AccessDeniedException")`; assert `await llm.ainvoke("ping")` raises `BedrockAccessDenied` with `HAIKU_ARN` in the message. Reuse the existing module-level `_build_client_error` and `HAIKU_ARN`.
  </action>
  <verify>
    <automated>uv run --package model-adapter pytest packages/model-adapter -q</automated>
  </verify>
  <done>New sync, async, pass-through, and async-AccessDenied tests pass; full model-adapter suite green.</done>
</task>

</tasks>

<verification>
- `uv run --package model-adapter pytest packages/model-adapter -q` passes (all existing + new tests).
- Final orchestrator gate: `uv run pytest -q` full suite green.
</verification>

<success_criteria>
- List-shaped content collapses to a concatenated `str` on `.content`; reasoning blocks preserved on `additional_kwargs["reasoning"]`.
- Both `invoke` and `ainvoke` normalize content and translate AccessDeniedException → BedrockAccessDenied.
- String-content messages and non-message returns (bare `object()`) pass through unchanged.
- Existing AccessDenied / success-path / workspace-override tests remain green.
</success_criteria>

<output>
Create `.planning/quick/260529-pzd-fix-b-model-adapter-content-normalizer/260529-pzd-SUMMARY.md` when done.
</output>
