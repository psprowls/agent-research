---
phase: 19-phase-16-code-review-burndown
plan: 02
subsystem: core-runtime
tags: [refactor, warning, code-review, burndown]
requires:
  - SubagentPool fan-out behavior (Phase 16-02 G-01 + SUB-04)
  - commands/query.py `Path.is_relative_to` idiom (line 356)
provides:
  - SubagentPool with hoisted signature inspection (WR-05)
  - Ingest `_route_target_path` using `Path.is_relative_to` (WR-06)
affects:
  - packages/subagent-runtime/src/subagent_runtime/pool.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
tech_stack:
  added: []
  patterns:
    - "Hoist signature introspection out of per-item hot path with try/except fallback"
    - "Use `Path.is_relative_to` for vault containment (canonical codebase idiom)"
key_files:
  created:
    - .planning/phases/19-phase-16-code-review-burndown/19-02-SUMMARY.md
  modified:
    - packages/subagent-runtime/src/subagent_runtime/pool.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
decisions:
  - "Compute `inspect.signature(task)` once per fan-out, store boolean arity flag, close over it in `_run_one` (D-05)"
  - "Wrap signature introspection in `try/except (ValueError, TypeError)` and fall back to single-arg form to preserve prior failure tolerance"
  - "Replace string-prefix containment check with `Path.is_relative_to` (D-06) — Python 3.11+ floor per CLAUDE.md, no fallback shim"
metrics:
  duration: ~4m
  completed: 2026-05-20
---

# Phase 19 Plan 02: Code-Review Warning Burndown (D-05, D-06) Summary

Two warning-severity refactors from CONTEXT.md decisions D-05 and D-06: hoist `inspect.signature(task)` out of the `SubagentPool._run_one` per-item hot path, and converge `commands/ingest.py::_route_target_path` on the `Path.is_relative_to` idiom used in `commands/query.py:356`.

## Tasks Completed

### Task 1 — D-05 (WR-05): hoist `inspect.signature(task)` out of `_run_one`

- File: `packages/subagent-runtime/src/subagent_runtime/pool.py`
- Commit: `a4db4e8`
- Behavior: signature inspection now runs once per `run_all()` invocation (per fan-out) instead of once per item. Result is captured as a boolean `_task_arity_2` flag, then closed over by `_run_one`.
- Fallback preserved: wrapped in `try/except (ValueError, TypeError)`; on failure, falls back to single-arg form (matches prior behavior for callables whose signature cannot be introspected — e.g. C-implemented callables).
- `inspect.signature` now appears exactly once in the file (was inside `_run_one`, called N times per N-item fan-out; now outside, called once).
- Verification: `uv run pytest packages/subagent-runtime/tests/ -m "not integration"` — 19 passed, 3 deselected, 0 failed. The two-arg delivery test (`test_recursion_limit_propagated_to_runnableconfig`) still passes — confirms the arity decision and RunnableConfig delivery semantics are intact.

### Task 2 — D-06 (WR-06): switch `_route_target_path` to `Path.is_relative_to`

- File: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py`
- Commit: `3949713`
- Behavior: replaced `str(resolved).startswith(str(wiki_resolved) + "/")` with `resolved.is_relative_to(wiki_resolved)`. Mirrors the canonical idiom at `commands/query.py:356`.
- No backwards-compat shim added (CLAUDE.md: Python 3.11+ floor; `is_relative_to` is 3.9+ stdlib).
- No dead imports removed (the previous implementation used only `str.startswith` — already a builtin, nothing to clean up).
- Semantics preserved on macOS/Linux (project's only supported targets per CLAUDE.md): target paths are always `wiki / subdir / "{slug}.md"`, so they always have a subdir component below `wiki` and can never equal `wiki_resolved`. The minor edge-case difference between the old check (rejects `wiki_resolved` itself, no trailing slash) and the new check (accepts `wiki_resolved` itself) is unreachable by construction.
- Verification: `uv run pytest agents/graph-wiki-agent/tests/ -m "not integration"` — 212 passed, 1 skipped, 5 deselected, 0 failed.

## Per-Commit Gate

Final gate after both tasks:

```
uv run pytest packages/eval-harness/tests/ packages/subagent-runtime/tests/ agents/graph-wiki-agent/tests/ -m "not integration"
389 passed, 23 skipped, 9 deselected in 24.03s
```

Gate passes.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed in the planned files with no out-of-scope changes.

The pre-commit hook updated `graph-wiki/CLAUDE.md` (auto-block removal of `code-wiki-agent` from the plugins list) — left untouched per scope-boundary rule; not related to D-05/D-06.

## Threat Flags

None — both changes are semantics-preserving refactors with no new trust boundaries or external surface introduced.

## Commits

| Task | Commit | Files |
|------|--------|-------|
| 1 (WR-05) | `a4db4e8` | `packages/subagent-runtime/src/subagent_runtime/pool.py` |
| 2 (WR-06) | `3949713` | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` |

Plan 05 will populate the 19-REVIEW-BURNDOWN.md table rows for WR-05 and WR-06 using these SHAs.

## Self-Check: PASSED

- pool.py exists, ingest.py exists, 19-02-SUMMARY.md exists
- Commits `a4db4e8` (Task 1) and `3949713` (Task 2) both present in `git log --all`
- Per-commit gate (389 passed, 23 skipped) verified post-Task-2
