---
phase: 02-subagent-fan-out-runtime
plan: "01"
subsystem: model-adapter, subagent-runtime
tags: [bedrock, model-registry, workspace-member, toml-config]
dependency_graph:
  requires: []
  provides:
    - load_role_config(role) -> dict with model_id/region/max_tokens/max_concurrency
    - make_llm(role) with max_tokens propagation
    - cores/subagent-runtime workspace member skeleton (importable, pytest-discoverable)
    - conftest.py fixtures for Plan 02 (fake_llm_response, fake_llm_response_error, make_task)
  affects:
    - cores/model-adapter/src/model_adapter/loader.py
    - cores/model-adapter/src/model_adapter/models.toml
    - cores/subagent-runtime (new)
tech_stack:
  added: []
  patterns:
    - 9-role TOML registry resolved by load_role_config(); KeyError on unknown role
    - max_tokens passed conditionally to ChatBedrockConverse via kwargs dict
    - uv workspace member with asyncio_mode=auto and integration marker
key_files:
  created:
    - cores/subagent-runtime/pyproject.toml
    - cores/subagent-runtime/src/subagent_runtime/__init__.py
    - cores/subagent-runtime/tests/__init__.py
    - cores/subagent-runtime/tests/conftest.py
  modified:
    - cores/model-adapter/src/model_adapter/models.toml
    - cores/model-adapter/src/model_adapter/loader.py
    - cores/model-adapter/tests/test_loader.py
    - uv.lock
decisions:
  - scanner max_tokens=500 and linter max_tokens=3000 per ROADMAP authority (AI-SPEC had different values)
  - judge_b uses claude-sonnet-4-6 (same as judge_a); switch to different family is one-line config change in Phase 4
  - subagent-runtime __init__.py is empty — SubagentPool/FanOutResult/PerItemError exports deferred to Plan 02
metrics:
  duration_mins: 4
  completed: "2026-05-13"
  tasks_completed: 2
  files_changed: 8
---

# Phase 02 Plan 01: ModelRegistry Extension and Subagent-Runtime Skeleton Summary

9-role TOML model registry (load_role_config/make_llm with max_tokens), plus cores/subagent-runtime workspace member skeleton with Plan 02 conftest fixtures.

## What Was Built

### Task 1: cores/subagent-runtime workspace member skeleton

New workspace member `cores/subagent-runtime` created with:

- `pyproject.toml`: name=subagent-runtime, deps (langchain-aws>=1.4.6, langchain-core>=1.4.0, model-adapter workspace dep), asyncio_mode=auto, integration marker
- `src/subagent_runtime/__init__.py`: empty package init (SubagentPool/FanOutResult/PerItemError added in Plan 02)
- `tests/__init__.py`: empty package marker
- `tests/conftest.py`: three fixtures ready for Plan 02 to import:
  - `fake_llm_response`: MagicMock with content="mocked response", usage_metadata={"input_tokens":10,"output_tokens":5,"total_tokens":15}
  - `fake_llm_response_error`: MagicMock with content="", usage_metadata=None
  - `make_task`: factory fixture returning an async task closure; raises ValueError for items in raise_for set

`uv sync` succeeded with subagent-runtime listed as a workspace member. `import subagent_runtime` exits 0.

### Task 2: 9-role models.toml and load_role_config()

**9-role models.toml table:**

| Role | model_id | max_tokens | max_concurrency |
|------|----------|------------|-----------------|
| haiku | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 1024 | 10 |
| sonnet | us.anthropic.claude-sonnet-4-6 | 4096 | 3 |
| librarian | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2048 | 5 |
| scanner | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 500 | 10 |
| linter | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 3000 | 10 |
| ingestor | us.anthropic.claude-haiku-4-5-20251001-v1:0 | 2048 | 5 |
| synthesizer | us.anthropic.claude-sonnet-4-6 | 4096 | 3 |
| judge_a | us.anthropic.claude-sonnet-4-6 | 2048 | 2 |
| judge_b | us.anthropic.claude-sonnet-4-6 | 2048 | 2 |

All roles use `region = "us-east-1"`.

**load_role_config(role: str) -> dict contract:**
- Calls `_load_models_config()` internally
- Returns the full dict from models.toml for the role: {model_id, region, max_tokens, max_concurrency}
- Raises `KeyError` on unknown role — intentional fail-loud behavior
- No user input flows into TOML lookup; role string comes from trusted caller code

**make_llm() extension:**
- Reads `role_cfg.get("max_tokens")` and passes to `_GuardedChatBedrockConverse` via kwargs dict only when not None
- Backward-compatible: roles without max_tokens in TOML use ChatBedrockConverse default
- Surgical diff: only the construction block touched; `_load_models_config`, `_GuardedChatBedrockConverse` class, and `object.__setattr__` line unchanged

**Tests:** 20 tests pass (6 pre-existing + 14 new). New tests:
- `test_load_role_config_returns_dict_for_all_seven_roles` (parametrized over 9 roles)
- `test_load_role_config_librarian_values`
- `test_load_role_config_synthesizer_uses_sonnet`
- `test_load_role_config_unknown_role_raises_keyerror`
- `test_make_llm_librarian_sets_max_tokens`
- `test_make_llm_haiku_still_works_after_extension`

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 347c329 | feat(02-01): create cores/subagent-runtime workspace member skeleton |
| 2 | 55ba1bb | feat(02-01): extend model-adapter with 9-role registry and load_role_config() |

## Deviations from Plan

### ROADMAP-Driven Token Ceiling Overrides

**Found during:** Task 2 analysis

The plan notes that ROADMAP Phase 2 success criterion #3 specifies `scanner: 500, linter: 3000` while the AI-SPEC had different values. The plan explicitly calls ROADMAP authoritative.

- scanner: max_tokens=500 (ROADMAP override)
- linter: max_tokens=3000 (ROADMAP override)
- librarian: max_tokens=2048 (AI-SPEC value; closest power-of-two to ROADMAP's "2000")

No code deviation — the plan documented this discrepancy and directed which values to use.

## Known Stubs

- `cores/subagent-runtime/src/subagent_runtime/__init__.py` is intentionally empty. SubagentPool, FanOutResult, PerItemError exports are deferred to Plan 02. This is by design — the plan states "empty package; pool added in Plan 02". The package is importable and the conftest fixtures are ready.

## Threat Flags

No new threat surfaces beyond what the plan's threat model covers. All changes are internal to the TOML registry and Python loader — no new network endpoints, auth paths, or trust boundaries introduced.

## Self-Check: PASSED

All required files found on disk. Both task commits (347c329, 55ba1bb) verified in git log.
