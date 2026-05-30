---
phase: quick-260530-ehv
plan: 01
subsystem: model-adapter
tags: [sweep, models, haiku-purge, cost-frontier]
dependency_graph:
  requires: []
  provides: [haiku-free-sweep-model-set, updated-config-pinning-tests, judge-independence-note]
  affects: [packages/model-adapter/src/model_adapter/models.toml, packages/model-adapter/tests/test_loader.py]
tech_stack:
  added: []
  patterns: []
key_files:
  created:
    - .planning/notes/sweep-judge-independence-deferred.md
  modified:
    - packages/model-adapter/src/model_adapter/models.toml
    - packages/model-adapter/tests/test_loader.py
decisions:
  - "preflight moved from Haiku to qwen.qwen3-32b-v1:0 as connectivity ping"
  - "librarian default: moonshotai.kimi-k2.5"
  - "code_reader default: minimax.minimax-m2.5"
  - "scanner default: openai.gpt-oss-20b-1:0"
  - "linter default: us.amazon.nova-lite-v1:0 (unchanged); nova-lite added as candidate"
  - "ingestor default: zai.glm-4.7-flash; removed qwen-vl-235b (vision overkill)"
  - "synthesizer default: qwen.qwen3-32b-v1:0 (unchanged); removed deepseek.r1 (toolCalling unsupported)"
  - "judges intentionally held (Mistral/Nova) despite post-purge family-independence violation in code_reader"
  - "narrator + domain-proposer deferred (still on Haiku)"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-30"
  tasks_completed: 3
  files_changed: 3
---

# Phase quick-260530-ehv Plan 01: Refresh Sweep Model Set in models.toml Summary

**One-liner:** Purged Haiku from all 6 swept roles + preflight in models.toml, set per-role defaults via /gsd-explore session (kimi-k2.5/minimax-m2.5/gpt-oss-20b/nova-lite/glm-4.7-flash/qwen3-32b), and captured the post-purge judge family-independence violation as a deferred finding.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Refresh swept-role defaults + candidates in models.toml (purge Haiku) | 949adc7 | models.toml |
| 2 | Sync config-pinning tests + run model-adapter suite | 187f83e | test_loader.py |
| 3 | Write deferred judge-independence note + update STATE.md pointer | (uncommitted per constraints) | sweep-judge-independence-deferred.md, STATE.md |

## Invariant Verification

All invariants confirmed green before committing:

- No `claude-haiku-4-5` in any swept role or preflight
- Every swept role's `model_id` is present in its own `sweep_candidates`
- preflight default = `qwen.qwen3-32b-v1:0`
- narrator + domain-proposer still on `global.anthropic.claude-haiku-4-5-20251001-v1:0` (intentionally deferred)
- `uv run --package model-adapter pytest`: **29/29 passed**

## Model Set After Refresh

| Role | Default (old) | Default (new) | Notes |
|------|--------------|---------------|-------|
| preflight | Haiku | qwen.qwen3-32b-v1:0 | cheap/fast connectivity ping |
| librarian | Haiku | moonshotai.kimi-k2.5 | |
| code_reader | Haiku | minimax.minimax-m2.5 | |
| scanner | Haiku | openai.gpt-oss-20b-1:0 | |
| linter | nova-lite (unchanged) | us.amazon.nova-lite-v1:0 | nova-lite now also in candidates |
| ingestor | qwen3-32b | zai.glm-4.7-flash | removed qwen-vl-235b (vision overkill) |
| synthesizer | qwen3-32b (unchanged) | qwen.qwen3-32b-v1:0 | removed deepseek.r1 (toolCalling unsupported) |
| narrator | Haiku | Haiku (deferred) | intentionally unchanged |
| domain-proposer | Haiku | Haiku (deferred) | intentionally unchanged |
| judge_a | Mistral Large 3 | Mistral Large 3 (deferred) | family collision w/ devstral in code_reader — deferred |
| judge_b | Nova Pro | Nova Pro (deferred) | future collision if judging extended to linter — deferred |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

- `packages/model-adapter/src/model_adapter/models.toml` — exists, TOML-valid, invariants verified
- `packages/model-adapter/tests/test_loader.py` — exists, 29/29 green
- `.planning/notes/sweep-judge-independence-deferred.md` — exists, contains JUDGE_PANEL_CONFIG
- `.planning/STATE.md` — contains kimi-k2.5 + sweep-judge-independence-deferred reference
- Commits: 949adc7 (models.toml), 187f83e (tests) — both confirmed in git log
