---
phase: 48-graph-propose-domains
plan: 01
subsystem: model-adapter
tags: [phase-48, propose-domains, model-adapter, role-loader]
requires:
  - "graph-wiki-agent project layout"
  - "model_adapter.loader.make_llm"
  - "packages/model-adapter/src/model_adapter/models.toml"
provides:
  - "[roles.domain-proposer] role config for Phase 48 LLM fan-out"
  - "make_llm(role, model_override=...) signature for CLI --model flag"
affects:
  - "packages/model-adapter/src/model_adapter/loader.py"
  - "packages/model-adapter/src/model_adapter/models.toml"
  - "packages/model-adapter/models.toml"
  - "packages/model-adapter/tests/test_loader.py"
tech-stack:
  added: []
  patterns:
    - "Role-keyed model_id with optional model_override (D-21)"
key-files:
  created: []
  modified:
    - "packages/model-adapter/src/model_adapter/models.toml"
    - "packages/model-adapter/models.toml"
    - "packages/model-adapter/src/model_adapter/loader.py"
    - "packages/model-adapter/tests/test_loader.py"
key-decisions:
  - "D-19: domain-proposer role added with initial config mirroring scanner (haiku-4.5, max_tokens=1024, max_concurrency=5); v1.9 eval will refine"
  - "D-21: make_llm now accepts model_override keyword to wire the --model CLI flag end-to-end"
requirements-completed: [PROPOSE-06]
duration: "2 min"
completed: "2026-05-27"
---

# Phase 48 Plan 01: domain-proposer role + model_override Summary

Added the `domain-proposer` role to `model_adapter` and extended `make_llm` with an optional `model_override` parameter so Phase 48's LLM fan-out has its own tier-tunable model handle (D-19) and the `--model` CLI flag can ride through to the role loader (D-21).

## Execution metrics

- **Duration:** 2 min
- **Start:** 2026-05-27T15:33:52Z
- **End:** 2026-05-27T15:35:32Z
- **Tasks executed:** 1/1
- **Files modified:** 4
- **Files created:** 0
- **Commit:** `34d019d feat(48-01): add domain-proposer role + model_override param to make_llm`

## What was built

1. **`[roles.domain-proposer]` in both `models.toml` files** (src and packaged mirror) with:
   - `model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"`
   - `region = "us-east-1"`
   - `max_tokens = 1024`
   - `max_concurrency = 5`
   - Header comment noting Phase 48 D-19 and the v1.9 eval revisit plan.
2. **`make_llm(role, *, model_override: str | None = None)`** signature in `loader.py`. When `model_override` is provided, it replaces the resolved role's `model_id` while preserving region, max_tokens, and the existing workspace-override resolution order.
3. **`test_domain_proposer_role`** in `tests/test_loader.py` modeled after `test_narrator_role`. Verifies:
   - `load_role_config("domain-proposer")` returns the expected dict shape.
   - `make_llm("domain-proposer")` instantiates a `ChatBedrockConverse` with the haiku ARN.
   - `make_llm("domain-proposer", model_override="us.amazon.nova-lite-v1:0")` swaps the model_id.

## Verification

- `uv run --package model-adapter pytest tests/test_loader.py::test_domain_proposer_role -x` → PASS (1/1)
- `uv run --package model-adapter pytest packages/model-adapter/tests -x` → PASS (25/25 — no regressions in role tests, narrator tests, or workspace-override resolution tests)
- `grep -n "\[roles.domain-proposer\]" packages/model-adapter/src/model_adapter/models.toml packages/model-adapter/models.toml` → 2 matches, exit 0

Plan-level acceptance criteria all satisfied:
- `[roles.domain-proposer]` block in both files with all four keys ✓
- `make_llm("domain-proposer")` returns working handle ✓
- `make_llm("domain-proposer", model_override=...)` overrides model_id ✓
- All pre-existing model-adapter tests still pass ✓

## Deviations from Plan

**[Rule 1 - missing critical] make_llm did not accept model_override** — Found during: Task 48-01-01 read_first phase | Issue: 48-RESEARCH.md F-4 documented `make_llm(role, *, model_override=None, ...)` as the current signature, but the live `loader.py` only had `make_llm(role: str)`. The plan's acceptance test asserts `make_llm("domain-proposer", model_override="us.amazon.nova-lite-v1:0")` returns an instance with the overridden model_id, and D-21 sits inside this plan's `<decisions_implemented>`. | Fix: Added `*, model_override: str | None = None` to `make_llm`; when provided, it replaces `role_cfg["model_id"]` before constructing the `_GuardedChatBedrockConverse`. Other resolution order semantics are unchanged. | Files modified: `packages/model-adapter/src/model_adapter/loader.py` | Verification: new test asserts both default and override paths; full model-adapter suite green. | Commit hash: `34d019d`.

**Total deviations:** 1 auto-fixed (Rule 1 - missing critical). **Impact:** D-21 wiring is now provably correct at the role-loader boundary. Plan 02 / Plan 03 can call `make_llm("domain-proposer", model_override=model)` directly when the `--model` Typer flag is set, with no further loader changes needed.

## Authentication Gates

None — no Bedrock or AWS calls during this plan.

## Issues Encountered

None blocking. One observation: the cross-tree `uv run --package model-adapter pytest -x` (without scoping to `packages/model-adapter/tests/`) reaches into `agents/graph-wiki-agent/tests/` and tripped a pre-existing flaky test `test_shared_impl_is_imported_from_commands` — confirmed unrelated by re-running it standalone (passed). Not introduced by this plan; surfaces likely due to Phase 46 in-flight uncommitted edits on the same working tree.

## Self-Check: PASSED

- key-files.modified all exist on disk: ✓
- `git log --oneline --all --grep="48-01"` returns ≥1 commit: ✓
- `<acceptance_criteria>` (Task 48-01-01 `<done>`): all three sub-criteria verified — `[roles.domain-proposer]` block in both files, `pytest test_domain_proposer_role` passes, full model-adapter pytest passes
- Plan-level `<verification>` commands rerun: full model-adapter pytest (25 passed), grep returns 2 matches
- `<success_criteria>` all met

## Ready for 48-02

`make_llm("domain-proposer", model_override=...)` works. Plan 02 can build the `propose_domains` core module on top of this — it'll call `make_llm("domain-proposer", model_override=model)` when the user passes `--model` and otherwise let the role's default take effect.
