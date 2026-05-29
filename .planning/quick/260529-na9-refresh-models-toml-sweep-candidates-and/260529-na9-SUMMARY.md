---
phase: quick-260529-na9
plan: "01"
subsystem: eval-harness / model-adapter
tags: [sweep, models, pricing, judge, dry-run]
dependency_graph:
  requires: []
  provides: [refreshed-sweep-candidates-2026-05-29, repriced-39-cell-matrix, bias-reduced-judge-panel]
  affects: [eval-harness/preflight, eval-harness/judge, model-adapter/loader]
tech_stack:
  added: []
  patterns: [toml-role-config, pricing-dict-lookup, uv-run-dry-run]
key_files:
  created: []
  modified:
    - packages/model-adapter/src/model_adapter/models.toml
    - packages/eval-harness/src/eval_harness/judge.py
    - packages/eval-harness/src/eval_harness/pricing.py
decisions:
  - Sonnet dropped from judge panel to remove Claude self-preference bias; Mistral Large 3 added as judge_a
  - Nova Pro kept as judge_b at existing pinned price (0.80/3.20) — not in bedrock-models-considering.json
  - qwen3-32b existing price 0.40/1.60 left unchanged with TODO comment (JSON shows 0.15/0.60)
  - linter incumbent (nova-lite) left as default even though not in new candidate set; flagged with comment
metrics:
  duration: "~8 minutes"
  completed: "2026-05-29"
  tasks_completed: 3
  tasks_total: 3
---

# Phase quick-260529-na9 Plan 01: Refresh models.toml Sweep Candidates and Judge Panel Summary

**One-liner:** Refreshed 39-cell sweep queue for 2026-05-29 with global Haiku profile migration, bias-reduced Mistral+Nova judge panel, and full pricing coverage; dry-run cost estimate is $2.72.

---

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Refresh models.toml — Haiku→global, six candidate lists, decision comments | 6206c70 | models.toml |
| 2 | Re-pin judge panel (judge.py + models.toml) and add candidate pricing (pricing.py) | 60c8d77 | judge.py, pricing.py |
| 3 | Dry-run validation — 39-cell matrix, zero spend | (no files changed) | — |

---

## Dry-Run Result

```
estimated_cost_usd=2.7173  cells=39  headroom_to_cap=$22.28
DRY-RUN OK — no Bedrock spend
```

- `n_cases=4`, `repeats=3` (documented estimator baseline)
- All 39 candidates present in `pricing.PRICES` (zero silent skips)
- `estimate_sweep_cost` and `preflight_check(skip_bed01=True, auto_confirm=True)` return identical float
- Estimate $2.72 is well under $25 hard cap ($22.28 headroom)

---

## Key Changes

### models.toml
- **Haiku migration:** All `us.anthropic.claude-haiku-4-5-20251001-v1:0` → `global.anthropic.claude-haiku-4-5-20251001-v1:0` (preflight, librarian, code_reader, scanner, narrator, domain-proposer defaults + all candidate list entries)
- **Six sweep_candidates arrays** replaced with 2026-05-29 queued lists (39 total cells):
  - librarian×6, synthesizer×8, linter×6, ingestor×7, scanner×6, code_reader×6
- **Comment refresh:** Stale raw-results comment blocks replaced with `# Sweep candidates queued 2026-05-29` + `# Previous default:` provenance lines
- **Linter flag:** `# NOTE: incumbent default us.amazon.nova-lite-v1:0 is NOT in the 2026-05-29 candidate set — default left as-is; needs a decision after the sweep runs.`
- **judge_a:** `us.anthropic.claude-sonnet-4-6` → `mistral.mistral-large-3-675b-instruct`

### judge.py
- `JUDGE_PANEL_CONFIG` re-pinned: Sonnet dropped, Mistral Large 3 added as judge_a
- Updated module comment explaining Claude self-preference bias rationale and alias drift caveat
- Nova Pro judge_b unchanged at 0.80/3.20

### pricing.py
- 17 new entries added (all new sweep candidates + Mistral Large 3 judge)
- `qwen.qwen3-32b-v1:0` entry left at 0.40/1.60 with TODO reconcile comment

---

## Flags and Notes

### Linter incumbent-not-a-candidate
`us.amazon.nova-lite-v1:0` is the current linter default but is NOT in the 2026-05-29 candidate set. Default left unchanged; the sweep will evaluate new candidates without a nova-lite baseline. A post-sweep decision is required on whether to add nova-lite to a future candidate set or accept a winner from the new set.

### qwen3-32b price-reconcile TODO
Existing `qwen.qwen3-32b-v1:0` entry is pinned at `input=0.40, output=1.60`. `bedrock-models-considering.json` now shows `0.15/0.60` for this ID. The spec does not ask to re-price existing entries; a TODO comment was added. Reconcile separately before or after the sweep runs.

### Nova-Pro pricing status
`us.amazon.nova-pro-v1:0` pricing (0.80/3.20) was NOT in `bedrock-models-considering.json`. The existing pinned value in `pricing.py` and `judge.py` was left as-is per the plan constraint — no fabricated number committed. No TODO needed since this is already the established pinned value.

---

## Deviations from Plan

None — plan executed exactly as written. Task 3 listed `packages/eval-harness/src/eval_harness/models.toml` as a file but this appears to be a plan typo (no such file exists; the validation ran against the model-adapter's `models.toml`). The validation ran successfully without any file modification needed.

---

## Self-Check

- [x] `packages/model-adapter/src/model_adapter/models.toml` exists and passes TOML parse
- [x] `packages/eval-harness/src/eval_harness/judge.py` exists with Mistral Large 3 as judge_a
- [x] `packages/eval-harness/src/eval_harness/pricing.py` exists with all 17 new entries
- [x] Commit 6206c70 exists (Task 1)
- [x] Commit 60c8d77 exists (Task 2)
- [x] Dry-run passed: estimated_cost_usd=2.7173, cells=39, no Bedrock spend

## Self-Check: PASSED
