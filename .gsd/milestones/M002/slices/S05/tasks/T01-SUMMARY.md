---
id: T01
parent: S05
milestone: M002
key_files:
  - pyproject.toml
  - uv.lock
  - tests/test_package_split_workspace.py
  - agents/
key_decisions:
  - The package-split boundary test checks only active workspace/package metadata and stale runtime/package traces, leaving allowed plugin identity strings to later stale-guidance cleanup tasks.
duration: 
verification_result: passed
completed_at: 2026-05-31T17:16:01.522Z
blocker_discovered: false
---

# T01: Cut the root uv workspace over to packages-only and added an executable package-split boundary test.

**Cut the root uv workspace over to packages-only and added an executable package-split boundary test.**

## What Happened

Added `tests/test_package_split_workspace.py` to enforce the final package-split boundary: root workspace members must be exactly `packages/*`, `agents/` must be absent, `uv.lock` must not reference the obsolete `graph-wiki-agent` package or path, `graph_wiki_agent` must not be importable, and active script metadata must remain owned by `graph-wiki-cli` (`gw`) and `graph-wiki-mcp` (`graph-wiki-mcp`). Updated the root `pyproject.toml` workspace members to `['packages/*']`, removed the obsolete `agents/` tree, and refreshed workspace resolution with `uv sync` so the lockfile no longer carries the old editable agent package.

## Verification

`uv sync` completed successfully, the new focused boundary test passed, and the task's exact verification command `uv sync && uv run python -m pytest tests/test_package_split_workspace.py -q` passed with 5 tests. A final diagnostic confirmed `workspace_members=['packages/*']`, `agents_exists=False`, no obsolete lockfile references, and the boundary test file present. Pytest emitted the pre-existing Hypothesis warning about explicit `norecursedirs` replacing default ignores; it did not fail verification.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv sync` | 0 | ✅ pass | 468ms |
| 2 | `uv run python -m pytest tests/test_package_split_workspace.py -q` | 0 | ✅ pass: 5 passed, 1 warning | 1410ms |
| 3 | `uv sync && uv run python -m pytest tests/test_package_split_workspace.py -q` | 0 | ✅ pass: 5 passed, 1 warning | 1314ms |
| 4 | `final package split state summary` | 0 | ✅ pass: packages-only workspace, agents absent, stale lock refs absent | 77ms |

## Deviations

None.

## Known Issues

Pytest reports a warning from Hypothesis because the root pytest config sets `norecursedirs`, replacing default ignores for `.hypothesis`; this warning was observed but is outside this task's scope.

## Files Created/Modified

- `pyproject.toml`
- `uv.lock`
- `tests/test_package_split_workspace.py`
- `agents/`
