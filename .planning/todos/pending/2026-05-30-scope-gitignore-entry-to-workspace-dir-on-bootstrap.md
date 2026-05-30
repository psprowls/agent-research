---
created: 2026-05-30T18:18:11.237Z
title: Scope gitignore entry to workspace dir on bootstrap
area: tooling
files:
  - packages/workspace-io/src/workspace_io/init.py:72,94-105
---

## Problem

On bootstrap, `_ensure_gitignore_entry(repo_root)` appends `.graph-wiki.local.yaml`
to the **repo root** `.gitignore` (`packages/workspace-io/src/workspace_io/init.py:94-105`).
This mutates a file at the top of the host repo that may be unrelated to the
workspace — noisy, intrusive, and wrong when the workspace lives in a subdirectory.

We'd rather not touch the repo-root `.gitignore` at all.

## Solution

Change bootstrap so that instead of appending to the repo-root `.gitignore`:

- **Workspace contained within the repo** → create/maintain a dedicated
  `.gitignore` inside the workspace (`graph-wiki/`) directory and put the
  `.graph-wiki.local.yaml` entry (and any future ignore needs) there. Keeps the
  ignore rules local to the directory they govern.
- **Workspace outside the source repo** → skip writing a `.gitignore` entirely.
  (Bootstrap already runs `git init` on the standalone workspace in this case —
  decide whether a local `.gitignore` is still warranted there, but default to skip.)
- **Unless necessary for some other reason** — if there's a concrete case where the
  repo-root entry is genuinely required, document it; otherwise drop the repo-root
  mutation.

Notes / open questions to resolve when planning:
- `.graph-wiki.local.yaml` path is relative to the workspace, so an entry in the
  workspace's own `.gitignore` should reference it directly (no path prefix).
- Confirm git treats a nested `.gitignore` inside `graph-wiki/` correctly when the
  workspace is a subdir of the host repo (it does — nested .gitignore is standard).
- Update `_ensure_gitignore_entry` signature/callers; the module docstring
  (lines 1-7) and the comment at `init.py:71-72` reference the old behavior and
  will need updating.
- Update/extend tests in `packages/workspace-io/tests/test_init.py`.
