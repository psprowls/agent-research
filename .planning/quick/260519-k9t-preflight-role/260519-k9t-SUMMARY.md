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

## Notes

`haiku` role left intact per user instruction — still used by IAM integration
tests (`agents/code-wiki-agent/tests/integration/test_bedrock_iam.py`) and as
the generic cheap-model handle in `test_loader.py`.
