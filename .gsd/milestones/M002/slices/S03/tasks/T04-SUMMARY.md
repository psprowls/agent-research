---
id: T04
parent: S03
milestone: M002
key_files:
  - packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/__init__.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-05-31T16:53:08.168Z
blocker_discovered: false
---

# T04: Added MCP package-boundary tests and removed the stale graph_wiki_agent.mcp source owner.

**Added MCP package-boundary tests and removed the stale graph_wiki_agent.mcp source owner.**

## What Happened

Added `packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py` to assert that the installed `graph-wiki-mcp` console script resolves to `graph_wiki_mcp.server:main` and to scan the MCP package for stale `graph_wiki_agent.mcp` references or old `uv run --package graph-wiki-agent graph-wiki-mcp` subprocess invocations. Removed the inactive `agents/graph-wiki-agent/src/graph_wiki_agent/mcp` source directory and cleaned old MCP pycache-only test artifacts so the temporary agent package no longer exposes or owns the MCP server surface. The package-local scan now enforces decisions D002/D003 without adding a compatibility shim.

## Verification

Ran the required S03 verification chain. `uv sync` completed successfully. `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests` passed with 56 tests passing and 2 integration tests skipped by the existing `GRAPH_WIKI_RUN_INTEGRATION=1` guard. Also verified that `agents/graph-wiki-agent/src/graph_wiki_agent/mcp` does not exist, no non-pycache MCP tests remain under `agents/graph-wiki-agent/tests`, and `importlib.util.find_spec('graph_wiki_agent.mcp')` returns `None` when run in the graph-wiki-agent package environment.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv sync` | 0 | ✅ pass | 147ms |
| 2 | `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests` | 0 | ✅ pass (56 passed, 2 skipped) | 4681ms |
| 3 | `python stale-owner check + uv run --package graph-wiki-agent importlib find_spec('graph_wiki_agent.mcp')` | 0 | ✅ pass | 86ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/__init__.py`
