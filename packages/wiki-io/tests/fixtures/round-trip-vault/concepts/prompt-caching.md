---
title: Anthropic prompt caching (cache_read / cache_write tokens)
category: concept
summary: How Claude's prompt cache works, how it shows up in token-usage metrics, and why it muddies cross-run cost comparisons without breaking behavioral isolation.
tags: [claude-api, caching, evals, cost, lattice-evals]
updated: 2026-05-09
tokens: 1182
---

# Anthropic prompt caching (`cache_read` / `cache_write` tokens)

## Definition

Anthropic's API supports **prompt caching**: callers mark prefixes of a request as cacheable, and the API stores the model's KV-cache for that prefix server-side. Subsequent requests that share the cached prefix skip recomputation, paying a deep discount on the cached portion. Caching is keyed by **exact byte content** of the prefix, **model**, **organization** (i.e. API key's account), and the position of `cache_control` breakpoints in the request.

Default TTL is **5 minutes** (ephemeral); a 1-hour cache class exists for longer-lived prefixes. Output is **never cached** — every request is sampled fresh.

## Token-usage shape

Anthropic reports four mutually-exclusive token counters per request, all visible in the `claude -p` stream-json `usage` blocks consumed by `packages/lattice-evals/src/lattice_evals/transcript.py`:

| Counter | What it counts | Pricing on Opus 4.7 |
|---|---:|---:|
| `input_tokens` | Tokens not covered by any cache hit | $15 / MTok |
| `cache_creation_input_tokens` | Tokens written into a fresh cache entry | $18.75 / MTok (1.25× input) |
| `cache_read_input_tokens` | Tokens served from an existing cache entry | $1.50 / MTok (0.1× input) |
| `output_tokens` | Sampled output | $75 / MTok |

The harness's `metrics.json` exposes these as `input_tokens`, `cache_write_tokens`, `cache_read_tokens`, `output_tokens`. **Total request size = input + cache_write + cache_read** — the three are partitions of the same prefix, not additive accounting layers.

## Why a "cold" run still shows cache hits

`claude -p` itself emits requests with cache breakpoints around the system prompt and the tool/skill catalog. A single multi-turn invocation calls the model multiple times; turns 2..N reuse turn 1's cache. So even a first-ever invocation reports both `cache_write` (turn 1 wrote it) and `cache_read` (turns 2..N read it). The agent loop's reuse pattern dominates the cache numbers — typically >90% of total tokens land in the cache columns.

## Implications for `lattice-evals`

### Behaviorally: not a leak

The cache stores the *input prefix*, not anything the model produced. Two cells running the same scenario back-to-back receive identical inputs whether the prefix was cached or not — the model behaves the same. Cache hits do not carry agent state, reasoning, or output across cells. Eval comparisons of *agent behavior* (did the right files get edited? did `verify.sh` pass?) are unaffected.

### Metric-wise: yes, it muddies cost and latency

Cache state is not deterministic across runs. The first cell in a runset writes the cache; the second cell often reads it. Cells therefore have systematically different `cost_usd` even when token totals match. The 2026-05-06 inaugural smoke is a clear example:

| Cell | Total tokens | `cache_write` | `cache_read` | Cost |
|---|---:|---:|---:|---:|
| `workflows` (first) | 202,983 | 72,193 | 130,633 | $1.5605 |
| `workflows+wiki` (second) | 203,026 | 39,283 | 163,610 | $0.9911 |

Same agent, same scenario, ~identical tokens. Cost gap is entirely cache warmth: the second cell rode some of the first cell's cache writes (within the 5-min TTL, same API key, mostly-identical Claude Code system prefix).

## Mitigations (for when metrics need to be comparable)

Tracked in 2026-05-05-lattice-evals-cache-warmth-affects-cost-metrics. Briefly:

1. **Document and accept** (current). Report `cache_write` / `cache_read` separately; note in the report header that order-dependent cells aren't apples-to-apples.
2. **Cold every cell.** Inject a unique nonce in the prompt to bust the cache. Reproducible, but always pays the write tax.
3. **Warm every cell.** Throwaway pre-pass per cell; measure the warm run. Eval cost ~doubles.
4. **Disable cache_control in the request.** Apples-to-apples and cheapest, but no longer reflects production cost.

## Related

- Spec: 2026-05-eval-harness-design (token accounting in §5)
- Followup: 2026-05-05-lattice-evals-cache-warmth-affects-cost-metrics
- First green smoke that surfaced the asymmetry: `evals/reports/2026-05-06-smoke.md`
- Code paths: `packages/lattice-evals/src/lattice_evals/transcript.py`, `packages/lattice-evals/src/lattice_evals/pricing.py`, `packages/lattice-evals/src/lattice_evals/metrics.py`
