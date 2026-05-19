---
quick_id: 260519-k9t
slug: preflight-role
status: complete
date: 2026-05-19
---

# Quick Task 260519-k9t Summary

## Outcome

- Added dedicated `[roles.preflight]` block (haiku-4.5 ARN, `max_tokens=64`) to
  `packages/model-adapter/src/model_adapter/models.toml`. Also mirrored into
  `packages/model-adapter/models.toml` stub, `models-claude.toml`, and
  `models-qwen.toml` profile snapshots.
- `eval_harness.preflight.preflight_bed01()` now calls `make_llm("preflight")`
  instead of `make_llm("haiku")`. Docstring updated.
- Removed `[roles.sonnet]` block from all four TOML files (no production caller).
- Updated `packages/model-adapter/tests/test_loader.py`: dropped
  `test_make_llm_sonnet_*` + `SONNET_ARN` constant; added
  `test_make_llm_preflight_*`; swapped `"sonnet"` → `"preflight"` in `ALL_ROLES`.

## Verification

- `uv run --package model-adapter pytest packages/model-adapter/tests/ -x -q` →
  20 passed.
- `uv run --package eval-harness pytest packages/eval-harness/tests/ -m "not eval" -x -q`
  → 158 passed, 4 skipped (unrelated env-gated divergence tests), 19 deselected.
- `grep -rn 'roles\.sonnet\|"sonnet"' packages/ agents/` → no remaining hits.

## Files Changed

- `packages/model-adapter/src/model_adapter/models.toml`
- `packages/model-adapter/models.toml`
- `packages/eval-harness/src/eval_harness/preflight.py`
- `packages/model-adapter/tests/test_loader.py`
- `models-claude.toml`
- `models-qwen.toml`

## Follow-up: haiku role also removed (same session)

After confirming `preflight` is the only handle the smoke-test code path needs,
the `[roles.haiku]` block was removed from all four TOML files. The remaining
`make_llm("haiku")` test references (3 in `test_loader.py`, 2 in
`test_bedrock_iam.py`) were retargeted to `make_llm("preflight")`, the
duplicate `test_make_llm_haiku_*` tests were deleted (preflight tests cover
them now), and `"haiku"` was dropped from `ALL_ROLES`. `HAIKU_ARN` constant
kept — it still describes the model ID `preflight` currently points at.

Verified: model-adapter (17 passed), eval-harness non-eval (158 passed),
integration test_bedrock_iam (1 passed + 1 skipped real-Bedrock path).
