---
quick_id: 260519-lf1
slug: bedrock-audit
status: complete
date: 2026-05-19
---

# Quick Task 260519-lf1 Summary

## Outcome

Created `scripts/bedrock_model_audit.py` — a standalone audit utility that:

1. Lists every TEXT-output, ON_DEMAND foundation model in the target region.
2. Lists every inference profile in the target region.
3. Probes each entry via `bedrock-runtime converse` with a minimal `toolConfig`
   (one trivial tool, ~50 input / ~20 output tokens) and classifies the result
   as `toolCalling: true | false | null`.
4. Fetches per-1K-token pricing from the AWS Pricing API (`AmazonBedrock`
   service code, filtered to the target `regionCode`).
5. Writes a JSON array file (default `bedrock-models.json`) with the original
   AWS catalog record plus `entryKind`, `toolCalling`, optional `probeError`,
   and `pricing`.

Classification semantics:
- HTTP 200, any `toolUse` block or `stopReason == "tool_use"` → `True`
- HTTP 200, no tool block (model accepted `toolConfig` but chose not to call)
  → `True` (API-level acceptance is the definition of "supports tool calling")
- `ValidationException` mentioning tool/toolConfig → `False`
- `AccessDeniedException` → `None`, `probeError = "AccessDenied"`
- Any other error → `None`, `probeError = <code or class name>`

Pricing fetched **regardless** of probe outcome — the JSON always carries a
`pricing` dict, with `input_per_1k`/`output_per_1k` possibly `null` if the
target model couldn't be matched against an AWS Pricing API SKU.

## CLI

```
uv run --package eval-harness python scripts/bedrock_model_audit.py [flags]
  --region REGION       (default us-east-1)
  --out PATH            (default bedrock-models.json)
  --concurrency N       (default 8)
  --dry-run             list models that would be probed; exits without calling
                        bedrock-runtime or AWS Pricing API
```

## Verification

- `--help` renders all four flags.
- `--dry-run` against real AWS lists 53 foundation models + 57 inference
  profiles (110 total) and exits 0 without invoking Bedrock or Pricing.

## Files Changed

- `scripts/bedrock_model_audit.py` (new)

## Notes

- Uses boto3 (already transitively pulled in by `langchain-aws`). No extra dep.
- Concurrency via `asyncio.to_thread` + `asyncio.Semaphore(N)` — no aiobotocore
  dependency added.
- Pricing matching is best-effort: tries `modelName`, `inferenceProfileName`,
  the model ID with/without cross-region prefixes (`us.`, `eu.`, `apac.`), and
  the underlying-model ARN names embedded in inference profiles. Unmatched
  models get `pricing.input_per_1k=null`.
- Live audit cost: ~$0.10–0.50 for ~110 models at ~50/20 tokens each. Many
  will fail with `AccessDenied` if not enabled in your account — those are
  surfaced via `probeError`, not silent skips.
