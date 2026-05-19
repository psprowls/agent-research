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

## Coverage improvements (later in session)

- **Hardcoded alias map** (`_PRICING_NAME_ALIASES`) for known catalog↔Pricing
  API name mismatches. Currently: 5 Mistral, 2 NVIDIA, 1 Qwen, 4 Amazon Nova
  2.x. Recovered 11 newly-priced records in one go.
- **Inference-profile fallback**: when a profile has no direct pricing match,
  walk its `models[].modelArn` and inherit the underlying foundation model's
  rate. Marked `pricing.source = "aws-pricing-api+profile-fallback"`.
  Infrastructure in place but didn't fire in the us-east-1 run — the only
  unpriced profiles were Claude 4.x, which AWS hasn't published *any* SKU
  for yet (foundation or profile).
- **`pricingKind` tag** on every record: one of `tokens`, `image`,
  `embedding`, `rerank`, `video`, `speech`. Classifies via ID substring
  patterns (`stable-`, `rerank`, `embed`, `marengo`, `pegasus`, `sonic`) and
  `outputModalities`. Makes null token-pricing self-explanatory for the 21
  models that are billed per-image / per-document / per-second.
- **Sort order**: priced records first, by `(providerName, modelId)`; then
  unpriced records at the end, same sort. The unpriced tail is what needs
  manual triage (override file or scraping).

Coverage after this pass (us-east-1, 110 entries):
  - 97 priced via direct Pricing API match
  - 11 priced via alias map
  - 21 still unpriced with `pricingKind=tokens` (AI21 Jamba 1.5, Cohere
    Command R/R+, Writer Palmyra X4/X5, all Claude 4.x inference profiles —
    AWS Pricing API does not carry these as of this run)
  - 21 unpriced with non-token `pricingKind` (expected; tagged so consumers
    know not to expect per-1M-token rates)

## Follow-up changes (same session)

- Renamed `toolCalling` → `toolCallingSupported`, `probeError` → `toolProbeError`
  (always emitted, null when no error).
- Pricing normalised to per-1,000,000 tokens: `input_per_1k` → `input_per_1m`,
  `output_per_1k` → `output_per_1m`. Per-1K → per-1M conversion done in
  `Decimal` space so the output is exact (e.g. `0.06` instead of
  `0.060000000000000005`).
- Added `pricingProbeError`: `"NotFoundInPricingAPI"` when no SKU matched,
  the upstream Pricing API error class name when the global fetch failed,
  null otherwise. (Pricing absence ≠ inaccessibility — Bedrock invocation
  and the AWS Pricing API are independent services.)
- Output split into two files in `--out-dir` (default `.`):
  - `bedrock-models-available.json` — always written; models that returned
    anything other than `AccessDeniedException` from the probe.
  - `bedrock-models-unavailable.json` — only with `--all`; access-denied models.
- Replaced `--out PATH` flag with `--out-dir PATH` (filenames are fixed).
- Records sorted by `(providerName, modelId)`. Inference profiles (which
  lack `providerName`) inherit canonical casing from the foundation-model
  list by matching on the model ID prefix — so `DeepSeek` stays `DeepSeek`
  instead of becoming `Deepseek`.
- Float output forced to decimal notation via custom `_DecimalFloatEncoder`
  that routes floats through `Decimal(repr(x))` before formatting — no
  scientific notation in the JSON.

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
