---
phase: quick-260529-ox1
plan: "01"
one_liner: "EvalWorktree now provisions an empty schema-valid graph DB via store.connect(create=True) so ingestor sweep cells stop hard-failing with IngestorGraphNotInitializedError"
subsystem: eval-harness
tags: [eval, isolation, graph-io, worktree, bugfix]
dependency_graph:
  requires: [graph-io, workspace-io]
  provides: [EvalWorktree with valid graph DB]
  affects: [ingestor sweep cells]
tech_stack:
  added: [graph-io workspace dep, workspace-io workspace dep]
  patterns: [store.connect(create=True) for empty schema provisioning]
key_files:
  created: []
  modified:
    - packages/eval-harness/src/eval_harness/isolation.py
    - packages/eval-harness/pyproject.toml
    - packages/eval-harness/tests/test_isolation.py
decisions:
  - Use store.connect(db_path, create=True) + .close() — no real graph build; only schema provisioned
  - Path derived via graph_dir(self.path) helper, not literal .graph/code.db strings
metrics:
  duration: "~10 minutes"
  completed: "2026-05-29"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
---

# Phase quick-260529-ox1 Plan 01: EvalWorktree Graph DB Provisioning Summary

**One-liner:** EvalWorktree now provisions an empty schema-valid graph DB via store.connect(create=True) so ingestor sweep cells stop hard-failing with IngestorGraphNotInitializedError

## What Was Built

A surgical fix to `isolation.py`: after `shutil.copytree` copies the wiki, `EvalWorktree.__aenter__` now calls `store.connect(db_path, create=True)` and immediately closes the connection. This creates `<tmp>/.graph/code.db` with a valid schema before any sweep cell runs.

Two workspace deps (`graph-io`, `workspace-io`) were added to `pyproject.toml` and a new offline test asserts the DB exists and opens via `read_only_connect`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Provision empty graph DB in EvalWorktree + add workspace deps | e42ae87 | isolation.py, pyproject.toml |
| 2 | Add offline test for provisioned graph DB | 09236a2 | tests/test_isolation.py |

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

- New test: `test_evalworktree_provisions_graph_db` — PASSED
- Full `test_isolation.py` suite: 5/5 passed
- Full eval-harness suite: 161 passed, 22 skipped, 3 failed
  - 3 pre-existing failures in `test_models_toml_sweep_candidates.py` and `test_pricing.py` — caused by models.toml update from prior quick task (260529-na9); unrelated to this change, confirmed present before these changes

## Self-Check: PASSED

- `packages/eval-harness/src/eval_harness/isolation.py` — exists, contains `graph_dir(self.path)` and `create=True`
- `packages/eval-harness/pyproject.toml` — contains `graph-io` and `workspace-io` in both deps and sources
- `packages/eval-harness/tests/test_isolation.py` — contains `test_evalworktree_provisions_graph_db` and `read_only_connect`
- Commits e42ae87 and 09236a2 — verified in git log
