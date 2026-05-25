# Phase 22: workspace-api-internal-rename - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 22-workspace-api-internal-rename
**Areas discussed:** WIP handling, Test-mock sweep strategy, Plan chunking, repo_path resolution semantics

---

## Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| WIP handling | 5 unstaged files on `main` prototype the rename — adopt, stash, or burndown later? | ✓ |
| Test-mock sweep strategy | ~70 `patch("...resolve_wiki_and_repo")` points across ~20 test files — one mass sweep, per-package, or per-file? | ✓ |
| Plan chunking | How to slice the 6 WSAPI requirements into atomic plans | ✓ |
| repo_path resolution semantics | When `workspace_path` is supplied but `repo_path` is omitted, where to walk from | ✓ |

**User's choice:** All four areas selected.

---

## WIP Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt + fix hack | Stage existing edits as plan foundation, replace the `Path(f"{workspace_path}/wiki")` hack with `wiki_dir(workspace_path)` | ✓ |
| Stash and rebuild clean | git stash the WIP, replan from scratch — each plan commit is born clean | |
| Adopt as-is, fix in burndown later | Keep the f-string hack temporarily; flag for cleanup in a follow-up plan | |

**User's choice:** Adopt + fix hack (Recommended).
**Notes:** The hack contradicts the milestone-level locked decision that wiki path is always derived via `workspace_io.paths.wiki_dir()`. Fix must happen before the plan's gating commit.

---

## Test-Mock Sweep Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Split by package | Three plans (wiki-io / graph-wiki-agent / eval-harness), each gated by `uv run --package <pkg> pytest` | ✓ (later overridden) |
| Single mechanical sweep plan | One plan, one pass across all ~20 test files, gate `uv run pytest` | |
| Per-file plans | One plan per test file (~20 plans). Maximum atomicity, maximum overhead | |

**User's choice initially:** Split by package.
**Notes:** This choice was effectively overridden in the Plan Chunking discussion below — "big-bang single plan" explicitly bundles the test sweep into the same plan as the API rename. The "split by package" intent is preserved as Claude's discretion guidance for executor file-ordering inside the single plan.

---

## Plan Chunking

| Option | Description | Selected |
|--------|-------------|----------|
| One plan per requirement | 6 plans (config+resolve_workspace, resolver sig, command sigs, call-site sweep, + 3 test-mock plans split by package) | |
| Grouped by layer | 3 plans (workspace-io / wiki-io+commands / test sweep split by package = 5 total) | |
| Big-bang single plan | All renames + test sweep in one plan, one commit | ✓ |

**User's choice:** Big-bang single plan.
**Notes:** Trade-off explicitly accepted: one large commit, bisect-hostile, but eliminates ordering risk because intermediate rename states are uncompilable (signatures and call sites must move together with mocks).

---

## repo_path Resolution Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Walk up from workspace (Recommended) | `repo_path = _find_repo_root(workspace_path)`. Matches the current WIP and old `vault_path.parent` behavior | |
| Require explicit repo_path | Raise if workspace_path supplied without repo_path. Forces caller intent; breaks more existing call sites | |
| Default to CWD | If repo_path is None, use Path.cwd() as repo | |
| Other (free-text) | "Walk up from the CWD if nothing explicitly specified" | ✓ |

**User's choice (free-text):** Walk up from CWD if nothing explicitly specified.
**Notes:** Subtle but important — when `repo_path` is omitted, discovery starts from `Path.cwd()`, NOT from `workspace_path`. This overrides the current WIP, which walks up from `workspace_path`. Rationale: callers that know only the workspace shouldn't have a different repo-discovery path than callers that know nothing.

---

## Claude's Discretion

- Test-mock sweep file ordering inside the single plan (executor's call).
- Whether to run `pytest` between file-batches inside the single plan during execution.
- Constant-rename import-site updates for `LATTICE_DIRECTORY_KEY` → `WORKSPACE_DIRECTORY_KEY`.
- Docstring update style on `run_*` functions, as long as `vault_path` terminology is purged.

## Deferred Ideas

(See CONTEXT.md `<deferred>` section for the full Phase 23 / 24 / 25 deferred-ideas catalogue.)
- All external-surface renames → Phase 23.
- All eval-harness internal renames → Phase 24.
- `packages/` misclassification + bootstrap `--interactive` → Phase 25.
- Pending todo `2026-05-20-fix-packages-dir-misclassification.md` reviewed but not folded (Phase 25 owns it).
