---
id: T03
parent: S03
milestone: M002
key_files:
  - packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py
  - packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py
  - packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-05-31T16:51:24.020Z
blocker_discovered: false
---

# T03: Moved MCP stdio, E2E, and cancel integration tests into the graph-wiki-mcp package and retargeted them to the new package boundary.

**Moved MCP stdio, E2E, and cancel integration tests into the graph-wiki-mcp package and retargeted them to the new package boundary.**

## What Happened

Moved `test_mcp_stdio.py`, `test_mcp_e2e.py`, and `test_mcp_cancel.py` from `agents/graph-wiki-agent/tests/integration` into `packages/graph-wiki-mcp/tests/integration`. Updated subprocess launches to use `uv run --package graph-wiki-mcp graph-wiki-mcp`, preserving the real console-script launch path. Updated the direct cancel test import and monkeypatch targets from `graph_wiki_agent.commands.query` to `graph_wiki_core.commands.query`, matching the shared command implementation consumed by the MCP package. Tightened the default-safe stdio test diagnostics so timeouts and non-zero subprocess exits include stdout and stderr, and strengthened JSON-RPC frame assertions to require `jsonrpc == "2.0"` plus response/request shape. Existing gates for heavier `tools/list` and full E2E tests remain behind `GRAPH_WIKI_RUN_INTEGRATION`, while `wiki_ping` and the mock-only cancel test run by default without Bedrock.

## Verification

Ran the task-required stdio verification with `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py`; it passed with 2 tests passing and 1 gated integration test skipped. Also ran the full moved integration directory; it passed with 3 tests passing and 2 gated tests skipped. A consistency check confirmed the three MCP integration files are present under the new package, no old `test_mcp_*.py` files remain in the agent integration directory, and the moved tests no longer contain the old graph-wiki-agent launch command or old query monkeypatch namespace.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py` | 0 | ✅ pass — 2 passed, 1 skipped | 2937ms |
| 2 | `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/integration` | 0 | ✅ pass — 3 passed, 2 skipped | 3917ms |
| 3 | `find packages/graph-wiki-mcp/tests/integration -maxdepth 1 -type f -name 'test_mcp_*.py' -print | sort; find agents/graph-wiki-agent/tests/integration -maxdepth 1 -type f -name 'test_mcp_*.py' -print | sort; rg checks for old launch/query refs` | 0 | ✅ pass — files moved and old refs absent | 33ms |

## Deviations

Also tightened stdio test failure diagnostics and JSON-RPC frame assertions, which directly supports the task's failure-mode and negative-test requirements.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py`
