---
id: T01
parent: S03
milestone: M002
key_files:
  - packages/graph-wiki-mcp/pyproject.toml
  - packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py
  - packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
  - packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py
  - agents/graph-wiki-agent/pyproject.toml
  - uv.lock
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-05-31T16:47:15.629Z
blocker_discovered: false
---

# T01: Created the focused `graph-wiki-mcp` workspace package and moved the guarded FastMCP server plus stdout guard tests into the new `graph_wiki_mcp` namespace.

**Created the focused `graph-wiki-mcp` workspace package and moved the guarded FastMCP server plus stdout guard tests into the new `graph_wiki_mcp` namespace.**

## What Happened

Created `packages/graph-wiki-mcp` as a uv_build workspace member with the `graph-wiki-mcp` console script pointing at `graph_wiki_mcp.server:main` and a workspace source dependency on `graph-wiki-core`. Copied the existing guarded FastMCP server into `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` while preserving the stdout guard ordering before logging, FastMCP, Pydantic, and graph-wiki-core imports. Added a side-effect-free `graph_wiki_mcp.__init__`, moved the stdout guard unit test into the new package, updated imports to `graph_wiki_mcp`, removed the old moved test from `agents/graph-wiki-agent`, and removed the `graph-wiki-mcp` script entry from the agent package so the new package is the sole script owner. Ran `uv sync` to update workspace installation and lock state for the new member.

## Verification

Ran `uv sync`, then ran the focused package test command `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py`. The test suite passed all 5 tests, covering non-empty stdout writes raising, whitespace writes being ignored, flush no-op behavior, server module wiring and MCP name, and `wiki_ping` returning pong. Also ran a static reference check confirming the old stdout guard test path is gone and new tests import `graph_wiki_mcp`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv sync` | 0 | ✅ pass | 943ms |
| 2 | `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py` | 0 | ✅ pass — 5 passed | 1976ms |
| 3 | `rg/static check for graph-wiki-mcp script owner, moved test path, and graph_wiki_mcp test imports` | 0 | ✅ pass | 54ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-mcp/pyproject.toml`
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py`
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- `packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py`
- `agents/graph-wiki-agent/pyproject.toml`
- `uv.lock`
