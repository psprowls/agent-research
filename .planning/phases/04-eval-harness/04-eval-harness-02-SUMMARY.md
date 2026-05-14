---
phase: 04-eval-harness
plan: "02"
subsystem: eval-harness
tags:
  - eval
  - isolation
  - sweep
  - tdd
  - bedrock
dependency_graph:
  requires:
    - "04-01 (pricing.py, structural.py, run_query() model override)"
  provides:
    - eval_harness.isolation (EvalWorktree async context manager)
    - eval_harness.sweep (SweepResult dataclass, run_sweep() function)
    - cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/ (BM25 + SQLite fixture committed to git)
  affects:
    - cores/eval-harness (new modules added)
    - cores/vault-io/tests/fixtures/round-trip-vault (untracked .code-wiki/ committed)
tech_stack:
  added: []
  patterns:
    - "EvalWorktree: shutil.copytree to tmpdir, async context manager, no subprocess/git/oauth"
    - "run_sweep: asyncio.gather(return_exceptions=True) for partial-failure isolation"
    - "re.sub model_id sanitization (T-4-02) applied before any filename use"
    - "JSON schema validation per T-4-01 (skip cases missing query/expected_answer)"
    - "TDD RED/GREEN cycle for both tasks"
key_files:
  created:
    - cores/eval-harness/src/eval_harness/isolation.py
    - cores/eval-harness/src/eval_harness/sweep.py
    - cores/eval-harness/tests/test_isolation.py
    - cores/eval-harness/tests/test_sweep.py
    - cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/ (11 fixture files committed)
  modified: []
decisions:
  - "Committed .code-wiki/ fixture to git (was untracked): worktree branch does not inherit untracked files from main repo, so EvalWorktree.test_evalworktree_includes_code_wiki would fail without this"
  - "seed field: typed int | None = None; documented as non-deterministic (librarian uses temperature != 0); reserved for future Bedrock Converse API seed parameter"
  - "Token extraction from trace JSONL: most-recently-modified .jsonl file in wt.path/.code-wiki/traces — works for mock tests (no traces = None/None) and real sweep runs"
  - "EvalWorktree does NOT port lattice-evals IsolationContext OAuth/git-worktree/plugin-registry logic — simplified per plan spec"
metrics:
  duration: "435s"
  completed: "2026-05-14"
  tasks_completed: 2
  files_changed: 16
---

# Phase 04 Plan 02: Isolation Layer and Model Sweep Runner Summary

**One-liner:** `EvalWorktree` async context manager (shutil.copytree isolation) and `run_sweep()` with `asyncio.gather` partial-failure tolerance, model_id sanitization, JSON schema validation, and SweepResult dataclass with seed field.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for EvalWorktree | 8998b9c | test_isolation.py |
| 1 (GREEN) | Implement EvalWorktree isolation layer | c0c6d7b | isolation.py, .code-wiki/ fixture (11 files) |
| 2 (RED) | Failing tests for sweep runner | 27d278e | test_sweep.py |
| 2 (GREEN) | Implement SweepResult + run_sweep() | 7282071 | sweep.py, isolation.py ruff fix, test files ruff fix |

## What Was Built

### eval_harness.isolation.EvalWorktree

Async context manager that copies a source vault to a fresh `tempfile.mkdtemp()` tmpdir on `__aenter__` and removes it on `__aexit__`. Explicitly does NOT use subprocess, OAuth, or git (contra the lattice-evals `IsolationContext` which this replaces).

- `shutil.copytree(source, path, dirs_exist_ok=False)` — includes `.code-wiki/` (BM25 + SQLite indexes)
- `shutil.rmtree(tmp, ignore_errors=True)` on exit — clean isolation even on error
- Two concurrent EvalWorktrees always get distinct paths (each has its own `mkdtemp` prefix)

### eval_harness.sweep.SweepResult

Dataclass with all EVAL fields:

| Field | Type | Notes |
|-------|------|-------|
| `model_id` | str | Raw Bedrock model ID (used for API calls) |
| `safe_model_id` | str | model_id with `[^a-zA-Z0-9._-]` replaced by `_` (T-4-02) |
| `query` | str | Query text from eval case |
| `answer` | str | Synthesized answer from run_query() |
| `citations` | list[str] | Wikilink targets extracted from answer |
| `pages_drilled` | int | Librarian fan-out success count |
| `tokens_in` | int \| None | Summed from trace JSONL |
| `tokens_out` | int \| None | Summed from trace JSONL |
| `cost_usd` | float \| None | Via cost_for_usage(); None if UnknownModelError |
| `wall_seconds` | float | Wall-clock time for run_query() call |
| `structural` | dict | EVAL-06 keys from check_structural() |
| `status` | str | "ok" or "error" |
| `judge_scores` | dict \| None | Reserved for Plan 03; None |
| `seed` | int \| None | None — librarian is non-deterministic (temperature != 0) |

### eval_harness.sweep.run_sweep()

`async def run_sweep(cases_path, vault_path, model_ids) -> list[SweepResult]`

- Loads JSON cases with schema validation (T-4-01): skips entries missing `query` or `expected_answer` with a logged warning
- For each `(model_id, case)` pair: opens EvalWorktree, calls `run_query()` with `librarian_model_override=model_id`
- Uses `asyncio.gather(return_exceptions=True)` — one failing model does not abort the sweep
- Extracts token counts from the most-recently-modified `.jsonl` file in `wt.path/.code-wiki/traces`
- Calls `cost_for_usage()` catching `UnknownModelError` silently (cost_usd = None)
- Calls `check_structural()` to populate structural field on "ok" runs

### Fixture .code-wiki/ committed to git

The `cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/` directory (BM25 index files + SQLite search.db + 10 trace JSONL files) was untracked in the main repo. It is now committed, so the worktree branch has access to it for the isolation tests.

### Integration smoke test (test_run_query_accepts_tmpdir_vault)

Exists in `test_sweep.py`, marked `@pytest.mark.integration`. Validates assumption A1 (RESEARCH.md Pitfall 6): run_query() accepts a tmpdir vault_path before the sweep loop is trusted. Skipped in the unit suite; requires `CODE_WIKI_RUN_EVAL=1` and real Bedrock credentials.

## Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| test_isolation.py | 4 | All PASSED |
| test_sweep.py (unit) | 7 | All PASSED |
| test_sweep.py (integration) | 1 | Skipped (gated) |
| eval-harness total (unit) | 28 | All PASSED |
| code-wiki-agent regression | 55 | All PASSED (no regressions) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added .code-wiki/ fixture to git**
- **Found during:** Task 1 (test_evalworktree_includes_code_wiki fails — .code-wiki/ not in worktree)
- **Issue:** `cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/` was untracked in the main repo. Git worktrees only get tracked files, so the isolation layer test that checks for `.code-wiki/bm25` failed because the directory was missing from the worktree's filesystem.
- **Fix:** Copied `.code-wiki/` from the main repo to the worktree and committed it (11 files: bm25 index NPY/JSON files, search.db, 10 trace JSONL files)
- **Files modified:** `cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/` (21 files created)
- **Commit:** c0c6d7b

**2. [Rule 2 - Code Quality] Fixed ruff import ordering (E402, I001) in new files**
- **Found during:** Task 2 verification (ruff check before commit)
- **Issue:** `from __future__ import annotations` placed before module docstring caused all subsequent imports to be flagged E402 (module level import not at top of file). Also I001 (unsorted imports) and F401 (unused imports: asyncio, pytest).
- **Fix:** Moved module docstring before `from __future__`, removed unused imports (asyncio from test_sweep.py, pytest from test_isolation.py), ran `ruff check --fix` for remaining I001 sort fixes
- **Files modified:** isolation.py, sweep.py, test_isolation.py, test_sweep.py
- **Commit:** 7282071

## Known Stubs

None. All modules implement their full contracts:
- `EvalWorktree` — fully functional (copytree + cleanup)
- `SweepResult` — all fields with correct types; `judge_scores=None` is intentional (Plan 03 populates it)
- `run_sweep()` — fully functional; `seed=None` is correct behavior (non-deterministic librarian)

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced beyond what the plan specified.

- T-4-01 (JSON schema validation): implemented in `_load_and_validate_cases()` — skip invalid cases with warning
- T-4-02 (model_id sanitization): implemented in `_sanitize_model_id()` via `re.sub(r"[^a-zA-Z0-9._-]", "_", model_id)`
- T-4-03 (baseline recorder subprocess): out of scope for this plan (Plan 04)

## Self-Check: PASSED

Files verified to exist:
- `cores/eval-harness/src/eval_harness/isolation.py` — FOUND
- `cores/eval-harness/src/eval_harness/sweep.py` — FOUND
- `cores/eval-harness/tests/test_isolation.py` — FOUND
- `cores/eval-harness/tests/test_sweep.py` — FOUND
- `cores/vault-io/tests/fixtures/round-trip-vault/.code-wiki/bm25/` — FOUND

Commits verified: 8998b9c, c0c6d7b, 27d278e, 7282071 — all present in git log.

TDD Gate Compliance:
- Task 1 RED commit: 8998b9c (`test(04-02): add failing tests for EvalWorktree...`) — PASSED
- Task 1 GREEN commit: c0c6d7b (`feat(04-02): implement EvalWorktree...`) — PASSED
- Task 2 RED commit: 27d278e (`test(04-02): add failing tests for sweep runner...`) — PASSED
- Task 2 GREEN commit: 7282071 (`feat(04-02): implement sweep runner...`) — PASSED
