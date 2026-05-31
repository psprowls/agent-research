---
id: T02
parent: S03
milestone: M002
key_files:
  - packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py
  - packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py
  - packages/graph-wiki-mcp/tests/unit/test_commands_log.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-05-31T16:48:33.555Z
blocker_discovered: false
---

# T02: Relocated MCP schema and tool unit tests into the graph-wiki-mcp package and retargeted them to the new graph_wiki_mcp namespace.

**Relocated MCP schema and tool unit tests into the graph-wiki-mcp package and retargeted them to the new graph_wiki_mcp namespace.**

## What Happened

Moved the six MCP-owned unit tests from `agents/graph-wiki-agent/tests/unit` into `packages/graph-wiki-mcp/tests/unit`: query schema, extra-field rejection, new wiki tools, graph tools, scan input, and log tool tests. Updated imports and patch targets from `graph_wiki_agent.mcp.server` to `graph_wiki_mcp.server`, and changed command result imports from `graph_wiki_agent.commands.*` to the shared `graph_wiki_core.commands.*` modules consumed by the extracted MCP server. Preserved the existing deterministic mocks around `run_query`, `run_scan`, `run_ingest_source`, `run_ingest_work_item`, `run_init`, `run_lint`, and `run_log`, along with Pydantic validation coverage for forbidden extras, top_k bounds, scan defaults, and tool dispatch behavior. Removed the old test files from the agent package so the MCP package is the test owner.

## Verification

Ran the required package-local unit suite with `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit`; all 51 tests passed. Also ran a static verification script confirming the six expected moved tests all exist under `packages/graph-wiki-mcp/tests/unit`, none remain under `agents/graph-wiki-agent/tests/unit`, and none import or patch `graph_wiki_agent.mcp`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit` | 0 | ✅ pass — 51 passed | 1909ms |
| 2 | `python3 static check for moved MCP test targets, removed source files, and no graph_wiki_agent.mcp refs` | 0 | ✅ pass | 37ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py`
- `packages/graph-wiki-mcp/tests/unit/test_commands_log.py`
