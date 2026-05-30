---
title: "Sweep judge family-independence — deferred finding"
date: 2026-05-30
context: "v1.11 Phase 60 cost-frontier sweep / /gsd-explore"
---

# Sweep Judge Family-Independence — Deferred Finding

## D-07 Rule Recap

A judge must NOT belong to a model family that is also a sweep candidate. This rule
was introduced because Haiku (Anthropic/Claude) appeared as a candidate in every swept
role, making any Claude-family judge structurally biased to self-prefer. Sonnet was
dropped as a judge for exactly this reason.

## Current Violation After the 2026-05-30 Haiku Purge

After the Haiku purge, candidate families shifted. The following collision now exists:

**judge_a = Mistral Large 3** (`mistral.mistral-large-3-675b-instruct`)

Mistral is now a candidate family via `mistral.devstral-2-123b` in `code_reader`, and
`code_reader` IS a judge-scored (query-style) role. This means judge_a can self-prefer
the devstral candidate in code_reader scoring.

**judge_b = Nova Pro** (`us.amazon.nova-pro-v1:0`, Amazon family)

Nova Pro is clean for judged roles TODAY — `nova-lite` only appears in `linter` and
`ingestor`, which are not currently judge-scored. However, judge_b becomes a collision
the moment judging is extended to `linter` (where `nova-lite` is now both default AND a
candidate in the refreshed set).

## Reversal: Claude Is Now the Clean Independent Judge

With Haiku removed from all candidate lists, NO Claude model is a candidate in any
swept role. Claude/Sonnet (including extended-thinking variants) is now the only major
family completely absent from all candidate lists, making it:

1. The natural clean independent judge for all query-style roles.
2. A viable reasoning judge (stronger than candidates, which is desirable for a judge).

## Reasoning-Model-as-Judge Analysis

Judging fits reasoning models well: the eval rubric is multi-step (EVAL_STEPS), requires
hallucination detection, and a judge stronger than the candidates is desirable. However:

1. **Determinism:** The panel pins `temperature=0`. Many reasoning models do not honor
   `temperature=0`; variable-length thinking traces hurt reproducibility across repeated
   runs within the same sweep cell.

2. **Cost/latency:** Judges fire on every judged cell × repeats × 2 judges. Token-heavy
   reasoning models blow up judge spend far more than a single candidate swap. This is
   the same reason `us.deepseek.r1-v1:0` was cut as a candidate — it applies even more
   forcefully to judges.

3. **Score extraction:** `deepeval`'s score-extraction logic may trip on thinking-block
   output (cf. Fix B / quick task pzd content normalization). Additional adapter work
   may be required.

4. **Family-cleanliness:** Most Bedrock reasoning models belong to candidate families
   (DeepSeek, Moonshot/Kimi, Qwen, OpenAI gpt-oss). Only Claude extended-thinking is
   family-clean after the Haiku purge.

## Decision

**Judges left UNCHANGED this pass.** Pat: "fine for now with what we have."

The Mistral collision in code_reader is noted but not considered blocking for the next
clean sweep run. Scores from that role should be interpreted with the collision in mind.

## Trigger to Revisit

1. **Before trusting code_reader judge scores** from the next sweep — the Mistral
   judge_a / devstral candidate collision means those scores may be systematically biased.

2. **Before extending the judge panel to non-query roles** (linter, ingestor, scanner) —
   Amazon Nova Pro (judge_b) would collide with `nova-lite` in linter/ingestor.

## Binding Configuration Note

The binding judge configuration lives in:

```
packages/eval-harness/src/eval_harness/judge.py  (JUDGE_PANEL_CONFIG)
```

The `[roles.judge_a]` / `[roles.judge_b]` blocks in `models.toml` are kept in sync
for reference only and are NOT read by the judge harness. Any judge swap must update
`JUDGE_PANEL_CONFIG` in `judge.py`, not just `models.toml`.
