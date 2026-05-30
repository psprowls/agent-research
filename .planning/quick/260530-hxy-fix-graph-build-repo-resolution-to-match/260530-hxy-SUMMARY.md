---
phase: quick-260530-hxy
plan: "01"
subsystem: graph-wiki-agent / wiki-io
tags: [bug-fix, repo-resolution, graph-build, workspace-io]
dependency_graph:
  requires: []
  provides: [graph-build-cwd-repo-resolution]
  affects: [wiki-io._workspace, graph-wiki-agent.commands.graph]
tech_stack:
  added: []
  patterns: [resolve_wiki_and_repo delegation, _repo_directory_override pin]
key_files:
  created:
    - packages/wiki-io/tests/test_workspace_resolution.py
  modified:
    - packages/wiki-io/src/wiki_io/_workspace.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
    - agents/graph-wiki-agent/tests/unit/test_commands_graph.py
decisions:
  - "Route _resolve_paths through resolve_wiki_and_repo instead of resolve_config to share the same cwd-based repo discovery path as scan"
  - "Apply _repo_directory_override in the explicit-workspace branch of resolve_wiki_and_repo so the documented pin workaround is consistent across both commands"
metrics:
  duration: ~15 min
  completed: 2026-05-30
  tasks_completed: 2
  files_modified: 4
  commits: 4
---

# Quick Task 260530-hxy: Fix graph build repo resolution to match scan

**One-liner:** Route `_resolve_paths` through `resolve_wiki_and_repo` so `graph build` resolves repo from cwd (not workspace dir), and honor `repo-directory:` pin in the explicit-workspace branch.

## What was done

### Root cause

`graph build` → `_resolve_paths()` → `resolve_config(Path(workspace_arg).resolve())` passed the WORKSPACE dir as `cwd`. The `_find_repo_root` call inside `resolve_config` walked up from the workspace and bound `repo_root` to the workspace's own `.git`. On a repo≠workspace layout (wiki vault is its own git repo, source code lives elsewhere), this caused:

- `repo_root == workspace` (wrong — should be the source repo)  
- `git rev-parse HEAD` fatal on a fresh vault with no commits
- Even with commits: graphs the WRONG tree (wiki vault instead of source code)

`scan` worked correctly because it called `resolve_wiki_and_repo()` → `_find_repo_root(Path.cwd())`, resolving repo from the actual current working directory.

### Fix

**Task 1 (`wiki-io/_workspace.py`):** Modified the explicit-workspace branch of `resolve_wiki_and_repo` to:
1. When `repo_path` is supplied: return it directly (explicit arg wins).
2. Otherwise: discover the cwd repo via `_find_repo_root(Path.cwd())`, then pass through `_repo_directory_override(workspace_path, cwd_repo)` so a `repo-directory:` pin in `<workspace>/.graph-wiki.yaml` takes effect.

Added `_repo_directory_override` to the import from `workspace_io.config`.

**Task 2 (`graph-wiki-agent/commands/graph.py`):** Rewrote `_resolve_paths` to delegate to `resolve_wiki_and_repo`:
- With `workspace_arg`: `resolve_wiki_and_repo(Path(workspace_arg).resolve())`
- Without: `resolve_wiki_and_repo()` (env var / walk-up fallback)
- Returns `(repo, wiki.parent)` where `wiki.parent` is the workspace root
- None-safe: falls back to `Path.cwd()` if no `.git` found
- Removed now-unused `from workspace_io.config import resolve as resolve_config`

### Tests

4 new tests for `resolve_wiki_and_repo` explicit-workspace branch:
1. With `repo-directory:` pin → returns pinned repo
2. Without pin → returns cwd-discovered repo
3. Explicit `repo_path` arg overrides pin
4. `~` expansion in pin honored

3 new tests for `_resolve_paths`:
1. Reproduces the repo≠workspace failure (workspace returned as repo_root — the actual bug)
2. `repo-directory:` pin honored via `_resolve_paths`
3. No-arg fallback path through env var

All tests follow RED→GREEN TDD cycle. Commits: RED test → GREEN impl for each task.

## Deviations from Plan

### Pre-existing Failure (out of scope)

`test_graph_query_output` (syrupy snapshot test) was already failing before this fix due to quick task 260530-gqp adding a `dev_dependencies` attribute to package nodes. Confirmed by running the test against the pre-fix stash. Not caused by this fix; not addressed (scope boundary per deviation rules). Logged to deferred items.

## Commits

| Hash | Message |
|------|---------|
| `1d2215d` | test(quick-260530-hxy-01): add failing tests for resolve_wiki_and_repo repo-directory: pin |
| `bfd2034` | feat(quick-260530-hxy-01): honor repo-directory: pin in resolve_wiki_and_repo explicit-workspace branch |
| `5be9ad9` | test(quick-260530-hxy-01): add failing tests reproducing repo≠workspace _resolve_paths bug |
| `3857235` | feat(quick-260530-hxy-01): route _resolve_paths through resolve_wiki_and_repo (fixes repo≠workspace) |

## Verification Results

```
packages/wiki-io/tests/test_workspace_resolution.py: 4 passed
packages/wiki-io/tests/ (full): 383 passed, 6 skipped, 1 xfailed
packages/workspace-io/tests/test_config.py: 17 passed
agents/graph-wiki-agent/tests/unit/test_commands_graph.py: 44 passed, 1 failed (pre-existing snapshot)
agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py: passes
```

## Known Stubs

None.

## Threat Flags

None — this change affects internal path resolution only, no new network endpoints or auth paths.

## Self-Check: PASSED

- `/packages/wiki-io/src/wiki_io/_workspace.py` — exists, modified
- `/packages/wiki-io/tests/test_workspace_resolution.py` — exists, created
- `/agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` — exists, modified
- `/agents/graph-wiki-agent/tests/unit/test_commands_graph.py` — exists, modified
- Commits `1d2215d`, `bfd2034`, `5be9ad9`, `3857235` — all present in git log
