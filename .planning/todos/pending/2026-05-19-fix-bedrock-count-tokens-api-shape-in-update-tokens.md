---
created: 2026-05-19T02:06:35.957Z
title: Fix Bedrock count_tokens API shape in update_tokens
area: tooling
resolves_phase: 17
files:
  - packages/vault-io/src/vault_io/update_tokens.py:38-44
---

## Problem

`vault_io.update_tokens.count_tokens()` calls the Bedrock CountTokens API with the wrong parameter name. Every page fails to be stamped during `/graph-wiki:scan`:

```
Parameter validation failed:
Missing required parameter in input: "input"
Unknown parameter in input: "content", must be one of: modelId, input
```

Current code at `update_tokens.py:38-44`:

```python
def count_tokens(text: str, model_id: str = DEFAULT_MODEL_ID, region: str = DEFAULT_REGION) -> int:
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.count_tokens(
        modelId=model_id,
        content=[{"text": text}],
    )
    return response["inputTokenCount"]
```

The current boto3 shape for `bedrock-runtime.count_tokens` expects `input=...`, not `content=...`. Discovered during the bootstrap scan of the deep-agents repo (2026-05-18) — all 35 newly-stubbed pages have `tokens: 0` because every CountTokens call failed.

## Solution

1. Verify the current `bedrock-runtime.count_tokens` signature against the installed boto3 version (`uv run python -c "import boto3; c=boto3.client('bedrock-runtime', region_name='us-east-1'); help(c.count_tokens)"`). The AWS docs page is https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html — confirm whether the parameter is `input` (likely the dict shape `{"converse": {...}}` or `{"invokeModel": {"body": ...}}`) or plain text.

2. Update the call to match. Likely something like:
   ```python
   response = client.count_tokens(
       modelId=model_id,
       input={"converse": {"messages": [{"role": "user", "content": [{"text": text}]}]}},
   )
   ```
   The exact shape depends on whether `input` wraps Converse-API or InvokeModel-API messages — confirm from the boto3 introspection.

3. Add a unit test in `packages/vault-io/tests/test_update_tokens.py` that mocks the boto3 client and asserts the request payload matches the expected shape.

4. Re-run `/graph-wiki:scan` (or just `update_tokens.py`) to re-stamp the 35 existing wiki pages.

## Out of scope

- Switching to Bedrock CountTokens vs. another tokenizer (already decided in CLAUDE.md: Bedrock CountTokens, no tiktoken).
- The unrelated `wiki.parent` repo-resolution bug — captured separately.
