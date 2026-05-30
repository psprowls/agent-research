---
phase: quick-260530-iqr
plan: 01
subsystem: graph-wiki-agent/commands
tags: [DRY, path-resolution, bug-fix, propose-domains, graph]
dependency_graph:
  requires: [quick-260530-hxy]
  provides: [shared-_resolve_paths, propose-domains-correct-repo-root]
  affects: [commands/graph.py, commands/propose_domains.py]
tech_stack:
  added: []
  patterns: [shared-helper-module, import-re-export]
key_files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/_paths.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/propose_domains.py
    - agents/graph-wiki-agent/tests/test_propose_domains.py
decisions:
  - Extract verbatim hxy-fixed _resolve_paths body into _paths.py rather than copying it
  - Re-export via import makes graph._resolve_paths still importable for MCP server
metrics:
  duration: ~10min
  completed: 2026-05-30
  tasks_completed: 2
  files_changed: 4
---

# Phase quick-260530-iqr Plan 01: Converge propose_domains _resolve_paths onto shared resolver Summary

Single `commands/_paths.py` module now holds the one correct `_resolve_paths`; graph.py and propose_domains.py both import it, so the repo-not-workspace path-resolution divergence is structurally impossible.

## What Was Built

**Task 1: Extract shared _resolve_paths (feat commit de1cc0b)**

Created `commands/_paths.py` with the corrected `_resolve_paths` body (delegates to `resolve_wiki_and_repo` — the hxy fix). Removed the local definitions and orphaned `resolve_config` imports from both `graph.py` and `propose_domains.py`. The MCP server continues to call `graph_module._resolve_paths(...)` — the import in `graph.py` makes `graph._resolve_paths` importable as an attribute.

**Task 2: Test repo-not-workspace correctness for propose-domains (test commit 5ff6381)**

Added two tests to `test_propose_domains.py` that import `_resolve_paths` via `propose_domains` (structural guard against re-divergence):
- `test_propose_domains_resolves_source_repo_not_vault`: cwd=source-repo, workspace=separate-git-repo; repo_root == source_repo (previously: vault returned as repo_root)
- `test_propose_domains_resolves_honors_repo_directory_pin`: manifest with `repo-directory:` pin; repo_root == pinned path

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 | de1cc0b | _paths.py (new), graph.py, propose_domains.py |
| 2 | 5ff6381 | test_propose_domains.py |

## Deviations from Plan

None — plan executed exactly as written.

**Note on pre-existing test failure:** `test_graph_query_output` in `test_commands_graph.py` fails due to a stale syrupy snapshot (missing `dev_dependencies` key — schema change predates this task). This failure exists on `main` as well and is out of scope per the surgical changes constraint.

## Self-Check: PASSED

- `commands/_paths.py` exists: FOUND
- Exactly one `def _resolve_paths` in src: CONFIRMED (commands/_paths.py only)
- `resolve_config` import removed from graph.py and propose_domains.py: CONFIRMED
- Commits de1cc0b and 5ff6381 exist: CONFIRMED
- 47/48 tests pass; 1 pre-existing snapshot failure unrelated to this task
