---
phase: 20-workspace-manifest-model-config
plan: 02
subsystem: model-adapter
tags: [python, model-adapter, loader, workspace-io, fallback, pytest, tdd]

# Dependency graph
requires:
  - phase: 20-workspace-manifest-model-config
    plan: 01
    provides: "workspace_io.read_roles(plugin_name, manifest_path) -> list[dict] + plugins[].roles[] round-trip"
provides:
  - "model_adapter.loader.make_llm consults workspace manifest first (via workspace_io.read_roles for plugin 'graph-wiki-agent') and falls back per-role to packaged models.toml"
  - "model_adapter.loader._workspace_role_override(role) private helper — catches both ImportError and RuntimeError; returns None on either"
  - "model_adapter.__all__ no longer exposes set_models_path; the _models_path_override mechanism is deleted"
  - "packages/model-adapter/tests/conftest.py — autouse fixture neutralizes GRAPH_WIKI_WORKSPACE env-var inheritance and stubs the workspace helper to None for deterministic packaged-default test runs"
affects: [20-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Function-scoped import of workspace_io inside _workspace_role_override (keeps workspace_io optional at import time of model_adapter, and is the recommended way to make the resolve-raises test work via setattr on workspace_io.config.resolve)"
    - "Per-role fallback (NOT all-or-nothing): workspace silence on a role falls through to packaged models.toml only for that role"
    - "Autouse-fixture-based test isolation against env-var inheritance: capture the real helper at conftest import time, stub it via monkeypatch for every test, restore via opt-in fixture"

key-files:
  created:
    - packages/model-adapter/tests/conftest.py
  modified:
    - packages/model-adapter/src/model_adapter/loader.py
    - packages/model-adapter/src/model_adapter/__init__.py
    - packages/model-adapter/tests/test_loader.py

key-decisions:
  - "Resolution order in make_llm: (1) workspace_io.read_roles('graph-wiki-agent', workspace/.graph-wiki.yaml) match by name == role, (2) packaged models.toml [roles.<role>]"
  - "load_role_config stays packaged-only — eval-harness sweep_candidates and subagent-runtime max_concurrency consumers depend on the packaged shape; workspace overrides do NOT bleed into this accessor"
  - "RuntimeError from workspace_io.resolve() is caught inside _workspace_role_override (single point of swallowing) — callers see None and fall through to packaged"
  - "resolve-raises test patches workspace_io.resolve + workspace_io.config.resolve (not the helper) to drive the production try/except; helper-returns-None test gives branch coverage but does NOT prove the try/except works"
  - "Test isolation via captured-at-import-time helper + autouse-stub + opt-in fixture — avoids importlib.reload heaviness"

patterns-established:
  - "TDD execution: Task 1 (loader refactor) committed first as `feat`; Task 2 (tests + conftest) committed second as `test`. Both tasks individually green; no separate RED commit because Task 1's refactor is verified by the existing pre-existing tests AND the four new tests in Task 2 against the same loader implementation."

requirements-completed: [WMC-02]

# Metrics
duration: 3min
completed: 2026-05-20
---

# Phase 20 Plan 02: Workspace-Aware make_llm + Per-Role Fallback Summary

**`model_adapter.loader.make_llm(role)` now resolves role config from `<workspace>/.graph-wiki.yaml` (`plugins[].roles[]` for `graph-wiki-agent`) when present and falls back per-role to packaged `models.toml` when the workspace is unreachable or silent on a role — `set_models_path()` and the `_models_path_override` mechanism are deleted.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-20
- **Completed:** 2026-05-20
- **Tasks:** 2 (Task 1: loader refactor + `__init__.py` re-export cleanup; Task 2: conftest + 4 new tests)
- **Files modified:** 4 (1 created, 3 modified)
- **Tests added:** 4 (workspace-wins, per-role fallback, resolve-raises, helper-None)
- **Tests passing:** model-adapter 21/21, workspace-io 78/78, eval-harness `test_models_toml_sweep_candidates.py` 6/6 — no regression across the workspace

## Accomplishments

- Added the `_workspace_role_override(role) -> dict | None` private helper to `loader.py`. Uses function-scoped imports (`from workspace_io import read_roles, resolve`) so a missing `workspace_io` does not break loader import; catches both `ImportError` (defensive) and `RuntimeError` (the documented `resolve()` raise contract).
- Rewrote `make_llm(role)` to consult the helper first, falling back per-role to `_load_models_config()` when the helper returns `None`. The `_GuardedChatBedrockConverse._model_id_for_errors` binding is preserved for BOTH resolution paths so AccessDenied error messages always name the model that was actually attempted.
- Deleted `_models_path_override` (module global), `set_models_path()` (public function), and the override-path branch in `_load_models_config()`. Removed `set_models_path` from the package `__init__.py` import line and from `__all__`.
- `load_role_config(role)` is untouched (still packaged-only); added a docstring note clarifying that workspace overrides apply to `make_llm()` only — not to this raw accessor (eval-harness consumers depend on `sweep_candidates`).
- Created `packages/model-adapter/tests/conftest.py`. Captures the real `_workspace_role_override` at import time, then exposes:
  - `_isolate_model_adapter_from_workspace` (autouse): drops `GRAPH_WIKI_WORKSPACE`, stubs the helper to `lambda role: None`. Runs before every test.
  - `real_workspace_role_override` (opt-in): restores the production helper for tests that exercise the workspace path.
- Added 4 new tests to `test_loader.py`:
  1. `test_make_llm_uses_workspace_role_when_present` — synthetic workspace declares `librarian` with `qwen.qwen3-32b-v1:0`; `make_llm("librarian")` returns the Qwen ARN (not the packaged Haiku default).
  2. `test_make_llm_falls_back_to_packaged_when_role_absent_in_workspace` — same synthetic workspace declares only `librarian`; `make_llm("scanner")` returns the packaged Haiku default. Per-role fallback guarantee.
  3. `test_make_llm_falls_back_to_packaged_when_resolve_raises` — **BLOCKER fix from plan-check.** Patches both `workspace_io.resolve` AND `workspace_io.config.resolve` to raise `RuntimeError`; asserts `make_llm("preflight")` returns the packaged Haiku default. Does NOT stub `_workspace_role_override` — drives the real production `try/except` path.
  4. `test_make_llm_falls_back_when_helper_returns_none` — branch coverage of the `if workspace_cfg is not None` arm via the autouse stub. Docstring explicitly notes this does not prove the try/except.

## Task Commits

Atomic commits per the project's recent style:

1. **Task 1:** `6123b93` — `feat(20-02): add workspace-aware override layer in make_llm + drop set_models_path` — loader refactor + `__init__.py` re-export cleanup. 17 existing tests stay green.
2. **Task 2:** `30d1480` — `test(20-02): add workspace-override tests + test-isolation conftest for model-adapter` — conftest + 4 new tests. 21/21 model-adapter tests pass; full workspace stays green.

## Files Created/Modified

- `packages/model-adapter/src/model_adapter/loader.py` — added `_workspace_role_override` helper; rewrote `make_llm` to consult workspace first; simplified `_load_models_config`; deleted `set_models_path` and `_models_path_override`; added docstring note to `load_role_config`.
- `packages/model-adapter/src/model_adapter/__init__.py` — dropped `set_models_path` from the import line and `__all__`.
- `packages/model-adapter/tests/conftest.py` — NEW. Autouse isolation + opt-in `real_workspace_role_override` fixture (45 LOC inc. docstrings).
- `packages/model-adapter/tests/test_loader.py` — appended `WORKSPACE_OVERRIDE_ARN` constant, `_write_synthetic_workspace` helper, and 4 new test functions (~135 LOC added).

## Decisions Made

- **Function-scoped `from workspace_io import ...`** inside the helper (not top-level). Keeps `workspace_io` an optional import for `model_adapter` consumers and is the cleanest way for the resolve-raises test to swap `workspace_io.config.resolve` via `monkeypatch.setattr` and have the helper pick it up.
- **`load_role_config` stays packaged-only.** The accessor is consumed by eval-harness (`packages/eval-harness/src/eval_harness/sweep.py`) which depends on the packaged `sweep_candidates` shape. Workspace `roles[]` entries do not carry sweep candidates; leaking workspace overrides into `load_role_config` would silently break the eval harness.
- **Resolve-raises is the load-bearing no-workspace test, not helper-returns-None.** The fourth test (`test_make_llm_falls_back_when_helper_returns_none`) is kept for branch coverage but documented as structurally insufficient to prove the production `try/except` works.
- **Test isolation via captured-at-import-time real helper + opt-in fixture.** Cleaner than `importlib.reload`; avoids order-of-fixture-resolution issues by making the real-helper restore explicit in the test signature.
- **Workspace plugin name is `"graph-wiki-agent"`.** Matches `graph-wiki/.graph-wiki.yaml` line 4 (the live workspace) and is the plugin that owns the role tiers per Phase 14 plugin port.

## Deviations from Plan

**1. [Rule 3 — Blocking issue / annotation only] Acceptance-criterion grep wording vs. literal compliance.**
- **Found during:** Task 2 verification.
- **Issue:** Plan acceptance criterion reads `grep -A 20 'def test_make_llm_falls_back_to_packaged_when_resolve_raises' ... | grep -c '_workspace_role_override'` returns 0. The literal grep returns 2 hits in the executed test: (1) the `real_workspace_role_override` fixture name in the function signature, (2) the `_workspace_role_override` reference inside the docstring describing what the production try/except catches. Neither hit *stubs* the helper.
- **Resolution:** No code change. The structural intent of the gate is "the test does NOT stub `_workspace_role_override` via `monkeypatch.setattr` to bypass the production try/except." Verified with the tighter grep `grep -A 30 ... | grep -c 'monkeypatch.setattr.*_workspace_role_override\|setattr(_loader.*_workspace_role_override'` → returns 0. The plan's literal wording is over-restrictive; the BLOCKER fix is satisfied in spirit (test drives `workspace_io.resolve` into raising via `monkeypatch.setattr(_wsio_config, "resolve", _raise)` + `monkeypatch.setattr(workspace_io, "resolve", _raise)`).
- **Files modified:** None.
- **Commit:** N/A.

No other deviations. The plan executed exactly as written: 2 tasks, 4 new tests, 1 new conftest, 2 atomic commits.

## Issues Encountered

None.

## User Setup Required

None — pure source/test change inside `packages/model-adapter/`.

## TDD Gate Compliance

- **Task 1 (loader refactor)** is a structural refactor verified by the pre-existing 17 loader tests (which continue to pass) AND by the 4 new tests in Task 2. The plan marked Task 1 `tdd="true"` but the new behavioral tests for it live in Task 2; Task 1 standalone has no new test — the refactor is gated by the existing tests acting as RED-already-GREEN against the new code, and by Task 2's new tests landing immediately after as proper RED→GREEN at the package level. This is an intentional consequence of the plan's two-task split (loader change in Task 1, conftest + tests in Task 2).
- **Task 2** lands the 4 new tests against the already-implemented `_workspace_role_override` helper. Tests pass on first commit (no separate RED).
- **REFACTOR gate:** not required — implementation is already minimal (Karpathy §2).

## Self-Check

Files modified (verified via `git log --stat 30d1480 ^73e656a`):
- `packages/model-adapter/src/model_adapter/loader.py` — VERIFIED MODIFIED (commit `6123b93`)
- `packages/model-adapter/src/model_adapter/__init__.py` — VERIFIED MODIFIED (commit `6123b93`)
- `packages/model-adapter/tests/conftest.py` — VERIFIED CREATED (commit `30d1480`)
- `packages/model-adapter/tests/test_loader.py` — VERIFIED MODIFIED (commit `30d1480`)

Commits verified via `git log --oneline -3`:
- `30d1480` — FOUND
- `6123b93` — FOUND

Acceptance-criteria grep gates (re-run post-commit):

Task 1 gates:
- `grep -c 'def set_models_path' packages/model-adapter/src/model_adapter/loader.py` → 0 — PASS
- `grep -c '_models_path_override' packages/model-adapter/src/model_adapter/loader.py` → 0 — PASS
- `grep -c 'set_models_path' packages/model-adapter/src/model_adapter/__init__.py` → 0 — PASS
- `grep -n 'def _workspace_role_override' packages/model-adapter/src/model_adapter/loader.py` → 1 — PASS
- `grep -n 'from workspace_io import' packages/model-adapter/src/model_adapter/loader.py | grep -v '^#'` → 1 — PASS
- `grep -n 'except RuntimeError' packages/model-adapter/src/model_adapter/loader.py` → 1 — PASS
- `grep -n 'object.__setattr__(llm, "_model_id_for_errors"' packages/model-adapter/src/model_adapter/loader.py` → 1 — PASS
- `uv run --package model-adapter python -c "import model_adapter; print(model_adapter.__all__)"` → `['BedrockAccessDenied', 'load_role_config', 'make_llm']` — PASS

Task 2 gates:
- `packages/model-adapter/tests/conftest.py` exists with both fixtures — PASS
- `grep -c 'autouse=True' packages/model-adapter/tests/conftest.py` → 1 — PASS
- `grep -c '^def test_make_llm_uses_workspace_role_when_present' test_loader.py` → 1 — PASS
- `grep -c '^def test_make_llm_falls_back_to_packaged_when_role_absent_in_workspace' test_loader.py` → 1 — PASS
- `grep -c '^def test_make_llm_falls_back_to_packaged_when_resolve_raises' test_loader.py` → 1 — PASS
- `grep -c '^def test_make_llm_falls_back_when_helper_returns_none' test_loader.py` → 1 — PASS
- Resolve-raises test does not stub the helper via `monkeypatch.setattr` (tighter intent-check) — PASS (literal-grep variant returns 2 due to fixture name + docstring; see "Deviations" §1)
- `uv run --package model-adapter pytest tests/test_loader.py -x` → 21/21 passed — PASS
- `uv run --package model-adapter pytest -x` → 21/21 passed (full model-adapter suite) — PASS
- `uv run --package workspace-io pytest -x` → 78/78 passed — PASS
- `uv run --package eval-harness pytest tests/test_models_toml_sweep_candidates.py -x` → 6/6 passed — PASS
- `grep -rn "set_models_path" packages/model-adapter/` → 0 matches — PASS

## Self-Check: PASSED

## Known Stubs

None. The new helper is a real production path; the autouse stub in `conftest.py` is test-only isolation, not production behavior.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries. The change reads role config from an already-trusted on-disk YAML file under the workspace root that the user owns; the `_GuardedChatBedrockConverse` AccessDenied wrapping is preserved unchanged for both resolution paths.

## Next Phase Readiness

- Plan 03 (deletion sweep of `--config` / `GRAPH_WIKI_CONFIG` / `models_path` from `agents/graph-wiki-agent/`) can now land cleanly: the loader side already has no `set_models_path` to import, so the agent-side cleanup is purely about deleting the now-dangling import statements at `cli.py:42` and `graph_wiki_mcp/server.py:449` plus the surrounding Typer/env-var wiring. NOTE for Plan 03: those two `from model_adapter.loader import set_models_path` lines will `ImportError` at runtime if the `--config` flag or `GRAPH_WIKI_CONFIG` env var is ever exercised between this plan and Plan 03 landing — but the imports are guarded behind those code paths so normal startup is unaffected.
- Plan 04 (live verify SC#4) can use `~/Personal/agent-research/graph-wiki/.graph-wiki.yaml` to override role models per the documented schema.

---
*Phase: 20-workspace-manifest-model-config*
*Completed: 2026-05-20*
