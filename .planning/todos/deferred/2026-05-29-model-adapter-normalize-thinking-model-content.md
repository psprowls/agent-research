---
created: 2026-05-29
title: Model-adapter should normalize list-shaped ("thinking" model) response content to a string
area: model-adapter
origin: 2026-05-29 live cost-frontier sweep — surfaced by Pat while watching the sweep log
files:
  - packages/model-adapter/src/model_adapter/loader.py            # _GuardedChatBedrockConverse (line 78); guard currently wraps invoke only (line 92)
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py # synthesizer consumers: _extract_wikilinks (279-281), _compute_unresolved_wikilinks (606/1122), synth_resp.content (1117), citations (1151)
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py # ingestor consumer: resp.content (660) -> _parse_ingestor_response -> text.strip() (410)
---

> **Update 2026-05-29 (ingestor sweep re-run):** This is broader than "thinking"
> models. After the graph-io fix unblocked the ingestor sweep cells, the ingestor
> ALSO failed for **`openai.gpt-oss-120b-1:0`** and **`minimax.minimax-m2.5`** with
> `'list' object has no attribute 'strip'` — `ingest.py:660` assigns `resp.content`
> (a list) and `_parse_ingestor_response` calls `.strip()` on it (`ingest.py:410`).
> Neither model is a reasoning/"thinking" model, so the trigger is the response
> SHAPE (block-list content), not the model class. This confirms the fix belongs
> at the model-adapter boundary (one normalizer fixes synthesizer + ingestor +
> any future role/model) and strengthens the "key off shape, never model ID"
> requirement below. Affected so far: synthesizer = {deepseek-r1, kimi-k2-thinking};
> ingestor = {gpt-oss-120b, minimax-m2.5}.

## Problem

During the live 39-cell cost-frontier sweep (2026-05-29), **every** synthesizer
cell for the two reasoning/"thinking" candidates failed uniformly, on every
repeat × every case:

- `us.deepseek.r1-v1:0` (DeepSeek-R1)
- `moonshot.kimi-k2-thinking` (Kimi K2 Thinking)

```
Role sweep cell failed: role=synthesizer model=us.deepseek.r1-v1:0 ...
  error=expected string or bytes-like object, got 'list'
```

This is **not** a Bedrock access denial and **not** a model defect — the models
respond fine. It is a content-shape incompatibility: thinking models return
`response.content` as a **list of content blocks** (separate reasoning + text
blocks) rather than a plain string. Downstream synthesizer post-processing
assumes a `str`:

- `commands/query.py:1117` — `answer = synth_resp.content` (becomes a list)
- `commands/query.py:279-281` — `_extract_wikilinks(text)` runs
  `re.findall(r"\[\[([^\]]+)\]\]", text)`, which raises `TypeError: expected
  string or bytes-like object, got 'list'` when `text` is a list
- same shape reached via `_compute_unresolved_wikilinks` (query.py:606 / 1122)
  and the `citations=_extract_wikilinks(answer)` call (query.py:1151)

Net effect: both thinking models drop out of the synthesizer frontier as
ALL-ERROR and produce no comparable data. The sweep itself still completes —
the 6 non-thinking synthesizer candidates yield a valid frontier — so this is a
follow-up, not a sweep blocker.

## Solution

Normalize response content **at the model-adapter boundary** so every consumer
(synthesizer, librarian, ingestor, linter, scanner, code_reader) receives a
plain string regardless of which model produced it — and so **future thinking
models work without any code change**. General, shape-driven, not per-model.

- Implement in `_GuardedChatBedrockConverse` (`model_adapter/loader.py:78`). The
  guard currently overrides **only** `invoke` (line 92); the agent and the sweep
  use the **async** path, so the normalizer MUST cover both `invoke` and
  `ainvoke` (and stream paths if/when used). This is also why the AccessDenied
  guard should probably extend to `ainvoke` while we're in here.
- **Detection must be structural, NOT model-ID-based:** when `response.content`
  is a `list` of content blocks, collapse it to a string by concatenating the
  text-type blocks (`block["type"] == "text"` / `block["text"]`), and either drop
  or stash the reasoning/thinking blocks on
  `response.additional_kwargs["reasoning"]` rather than discarding silently. Key
  off the content **shape**, so any reasoning model is handled automatically.
- Expose the normalized text via the standard `.content` so no downstream caller
  needs to change.

### Verify before building

- Confirm the exact block shape `langchain-aws` emits for DeepSeek-R1 /
  Kimi-K2-Thinking on the Bedrock Converse API (list of `{type, text}` dicts?
  `reasoning_content`? a separate key?). Don't assume — inspect a real response.
- Confirm the other roles also read `.content` (they do) and benefit from the
  same boundary fix.
- Decide whether reasoning/thinking blocks should be preserved for trace records
  (`subagent_runtime.trace_io`) or dropped.
- Add a model-adapter unit test that feeds a fake list-shaped `AIMessage.content`
  through the wrapper and asserts a normalized `str` out — for **both** the sync
  and async paths.
- After the fix, re-run the R1 + Kimi-K2-Thinking synthesizer cells to confirm
  they produce frontier data instead of ALL-ERROR.

Related: [[cost-frontier-sweep]], [[agent-role-taxonomy]] (synthesizer is the
single highest-stakes inference; this is exactly the reasoning-model risk flagged
during candidate selection — now confirmed as a hard harness incompatibility, not
just a quality concern).
