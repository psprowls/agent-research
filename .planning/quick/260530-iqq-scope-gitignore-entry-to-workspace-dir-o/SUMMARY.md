---
status: complete
phase: quick-260530-iqq
plan: "01"
subsystem: workspace-io
tags: [gitignore, bootstrap, workspace-scoped, containment-gate]
dependency_graph:
  requires: []
  provides: [workspace-scoped-gitignore-entry]
  affects: [workspace_io.init]
tech_stack:
  added: []
  patterns: [containment-gate via Path.relative_to + .git existence check]
key_files:
  created: []
  modified:
    - packages/workspace-io/src/workspace_io/init.py
    - packages/workspace-io/tests/test_init.py
decisions:
  - "Use repo_root/.git existence + workspace.relative_to(repo_root) + workspace != repo_root for containment gate"
  - "Write entry to <workspace>/.gitignore, not <repo_root>/.gitignore"
  - "Skip entry entirely for standalone/external workspaces (no write anywhere)"
metrics:
  duration: ~5 minutes
  completed: 2026-05-30
---

# Phase quick-260530-iqq Plan 01: Scope gitignore entry to workspace directory

**One-liner:** Scoped `.graph-wiki.local.yaml` ignore entry from the repo-root `.gitignore` to `<workspace>/.gitignore`, gated on workspace containment within the source repo.

## What Was Done

Bootstrap (`workspace_io.init`) previously called `_ensure_gitignore_entry(repo_root)`, writing `.graph-wiki.local.yaml` into the host repo-root `.gitignore` — noisy and wrong when the workspace is a subdirectory of an unrelated host repo.

Changed `_ensure_gitignore_entry` to accept `(workspace, repo_root)` and apply a containment gate:
- Workspace strictly inside source repo (`repo_root/.git` exists AND `workspace.is_relative_to(repo_root)` AND `workspace != repo_root`) — write entry into `<workspace>/.gitignore`
- Workspace outside source repo (standalone/external) — no entry written anywhere

The repo-root `.gitignore` is never touched.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: scope gitignore entry to workspace | fdac537 | packages/workspace-io/src/workspace_io/init.py |
| Task 2: update tests for new behavior | a48a081 | packages/workspace-io/tests/test_init.py |

## Deviations from Plan

None — plan executed exactly as written.

## Test Results

87 passed in 0.59s (full workspace-io suite). New tests cover:
- `test_gitignore_entry_in_workspace_when_contained` — entry in `<workspace>/.gitignore`
- `test_repo_root_gitignore_untouched` — repo-root `.gitignore` not created/modified
- `test_gitignore_entry_idempotent_in_workspace` — single occurrence after two inits
- `test_no_gitignore_entry_when_workspace_outside_repo` — no entry for external workspace

## Known Stubs

None.

## Threat Flags

None — T-iqq-01 (repo-root mutation) mitigated by this change; T-iqq-02 (write outside workspace) accepted and enforced by containment gate.

## Self-Check: PASSED

- `packages/workspace-io/src/workspace_io/init.py` — exists and modified
- `packages/workspace-io/tests/test_init.py` — exists and modified
- Commit fdac537 — present in git log
- Commit a48a081 — present in git log
