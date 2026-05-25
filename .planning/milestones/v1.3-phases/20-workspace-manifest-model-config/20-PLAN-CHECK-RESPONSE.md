# Plan-Check Response — Phase 20

**Date:** 2026-05-19
**Checker findings addressed:** 1 BLOCKER + 5 WARNINGS (#2 and #3 fixes plus #4, #5, #6 cheap-and-done)

## BLOCKER framing — agreed, no pushback

The argument is structurally correct: stubbing `_workspace_role_override` to return `None` bypasses the production `try/except RuntimeError` inside the helper. SC#2's no-workspace contract demands that production path be exercised, not short-circuited. The original test was branch coverage for `make_llm`, not coverage for the helper's exception handling. Fixed by **adding a dedicated test that patches `workspace_io.resolve` to raise `RuntimeError`** and keeping the helper-stub test as a fourth (clearly labeled) branch-coverage test.

## Changes by plan file

### `20-01-PLAN.md`
- No changes. The plan-check raised no findings against Plan 01.

### `20-02-PLAN.md` (BLOCKER + warning #4)
- **BLOCKER fix:** added `test_make_llm_falls_back_to_packaged_when_resolve_raises` (Task 2 step 4) that drives `workspace_io.resolve` into raising `RuntimeError` directly (via `monkeypatch.setattr` on both `workspace_io` and `workspace_io.config`). Test explicitly asserts no reference to `_workspace_role_override` (acceptance criterion gates this via `grep -A 20 ... | grep -c '_workspace_role_override'` returns 0).
- Demoted the original helper-stub test to `test_make_llm_falls_back_when_helper_returns_none` (Task 2 step 5) with a docstring noting it does NOT cover the no-workspace contract.
- Removed the "OR monkeypatch ..." escape clause from the `<behavior>` description — the resolve-raises test is now unambiguously required.
- Added a `<truth>` line in `must_haves` documenting the production-path coverage requirement.
- Updated `acceptance_criteria` to grep for `except RuntimeError` in the loader and for the four new test names.
- **Warning #4 fix:** added `packages/model-adapter/tests/conftest.py` to `files_modified`. Task 2 step A creates the conftest with two fixtures:
  - `_isolate_model_adapter_from_workspace` (autouse) — neutralizes `GRAPH_WIKI_WORKSPACE` env-var inheritance and stubs `_workspace_role_override` to return `None` for every test by default.
  - `real_workspace_role_override` (opt-in) — restores the real helper for tests that need to exercise the production resolution path. Workspace-override tests request this fixture explicitly.
- Updated `<verification>` to add the resolve-raises invariant ("does not contain any reference to `_workspace_role_override`").

### `20-03-PLAN.md` (warnings #5 and #6)
- **Warning #5 fix:** Task 1 step 1a now specifies the exact replacement docstring text verbatim (preserved as a code block in the plan) instead of vague "update the module docstring". Added a dedicated grep gate to `<verify>` and `<acceptance_criteria>`: `grep -c '@app.callback\|--config\|GRAPH_WIKI_CONFIG\|set_models_path' agents/graph-wiki-agent/src/graph_wiki_agent/config.py` returns 0.
- Added a `<truth>` line in `must_haves` documenting the docstring-scrub requirement.
- **Warning #6 fix:** added a new Task 3 ("Agent-side docs sweep") with a recursive grep gate as the acceptance criterion: `grep -rln -- '--config\|GRAPH_WIKI_CONFIG' agents/graph-wiki-agent/ --include='*.md' --include='README*' --exclude-dir='tests' --exclude-dir='.pytest_cache'` returns 0. Task 3 also gates on `wiki-config.toml` references in the same surface (catches stale TOML mentions even when `--config` itself isn't present).
- Updated `<objective>`, `must_haves`, `<verification>`, and `<success_criteria>` to mention the SC#5 agent-side docs portion.

### `20-04-PLAN.md` (warnings #2 and #3)
- **Warning #2 fix:** Task 1 step 2 now lists THREE lines to correct in the workspace-io wiki page (was two). Added line 21 with its full replacement text. Added an aggregate grep gate to both `<verify>` and `<acceptance_criteria>`: `grep -E 'no PyYAML|minimal YAML parser|Pure standard library' <file>` returns 0. Also kept a dedicated `grep -c 'minimal YAML parser' <file>` returns 0 gate for explicit line-21 coverage.
- Added a `<truth>` line in `must_haves` noting "three lines" instead of "two lines".
- **Warning #3 fix:** Task 1 step 4 now mandates FOUR deletions in `.planning/intel/files.json` (was two). Added:
  - Step 4c: delete `"set_models_path"` from `packages/model-adapter/src/model_adapter/__init__.py` exports array (line ~50).
  - Step 4d: delete `"set_models_path"` from `packages/model-adapter/src/model_adapter/loader.py` exports array (line ~60).
  - Removed the prior "If trivially safe, drop ... otherwise leave for the intel regen" hedge — deletion is now non-optional.
  - Added grep gate `grep -c 'set_models_path' .planning/intel/files.json` returns 0 to `<verify>`, `<acceptance_criteria>`, and `<verification>`.
- Updated `<objective>`, `must_haves` artifacts, and `<success_criteria>` to mention the SC#3-related `set_models_path` intel cleanup.

## Confirmation

- All six findings have been addressed in the plan files.
- No pushback on the BLOCKER framing — the original test was structurally insufficient and the plan-check argument was correct. Replaced with a test that exercises the production `try/except RuntimeError` path directly.
- The conftest.py autouse fixture chosen for warning #4 is the cleaner option (vs. repeating monkeypatch lines in each pre-existing test) — also makes the opt-in pattern explicit via the `real_workspace_role_override` fixture.

## Files updated

- `/Users/pat/Personal/agent-research/.planning/phases/20-workspace-manifest-model-config/20-02-PLAN.md`
- `/Users/pat/Personal/agent-research/.planning/phases/20-workspace-manifest-model-config/20-03-PLAN.md`
- `/Users/pat/Personal/agent-research/.planning/phases/20-workspace-manifest-model-config/20-04-PLAN.md`

`20-01-PLAN.md` and `ROADMAP.md` were not modified — no findings against them.
