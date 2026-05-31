---
id: T02
parent: S01
milestone: M002
key_files:
  - agents/graph-wiki-agent/pyproject.toml
  - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/__init__.py
key_decisions:
  - Kept temporary graph-wiki-agent script identities unchanged while making the package a consumer of graph-wiki-core.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:08:24.003Z
blocker_discovered: false
---

# T02: Rewired the temporary graph-wiki-agent CLI and MCP presentation surfaces to consume graph-wiki-core commands directly.

**Rewired the temporary graph-wiki-agent CLI and MCP presentation surfaces to consume graph-wiki-core commands directly.**

## What Happened

Added graph-wiki-core as a workspace dependency/source for graph-wiki-agent while preserving the existing graph-wiki-agent and graph-wiki-mcp script entry points. Updated CLI command imports and MCP tool command imports from graph_wiki_agent.commands to graph_wiki_core.commands, keeping the MCP stdout guard before all later imports so stdio framing protection remains intact. No graph_wiki_agent.commands compatibility shim was introduced.

## Verification

Ran the temporary CLI help smoke with `uv run --package graph-wiki-agent graph-wiki-agent --help`; it exited 0 and rendered the CLI command list, proving the presentation entry point compiles against graph_wiki_core.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-agent graph-wiki-agent --help` | 0 | ✅ pass | 1483ms |

## Deviations

The parent executor performed the implementation because the requested `subagent` tool was not available in this harness namespace; the task contract and verification were otherwise followed.

## Known Issues

The old source files under `agents/graph-wiki-agent/src/graph_wiki_agent/commands` still exist physically until later cleanup/boundary tasks, but the active CLI/MCP presentation imports no longer rely on them.

## Files Created/Modified

- `agents/graph-wiki-agent/pyproject.toml`
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/__init__.py`
