---
id: T02
parent: S02
milestone: M002
key_files:
  - packages/graph-wiki-cli/tests/conftest.py
  - packages/graph-wiki-cli/tests/unit/test_cli_help.py
  - packages/graph-wiki-cli/tests/unit/test_cli_query.py
  - packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py
  - packages/graph-wiki-cli/tests/unit/test_commands_bootstrap.py
  - packages/graph-wiki-cli/tests/unit/test_commands_graph.py
  - packages/graph-wiki-cli/tests/unit/test_commands_log.py
  - packages/graph-wiki-cli/tests/unit/test_trace_viewer.py
  - packages/graph-wiki-cli/tests/unit/test_seeded_graph_workspace_smoke.py
  - packages/graph-wiki-cli/tests/unit/__snapshots__/test_commands_graph.ambr
  - packages/graph-wiki-cli/tests/unit/__snapshots__/test_trace_viewer.ambr
  - agents/graph-wiki-agent/tests/conftest.py
  - agents/graph-wiki-agent/tests/unit/test_commands_log.py
  - agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py
key_decisions:
  - CLI presentation tests now live with graph-wiki-cli and target graph_wiki_cli.cli plus graph_wiki_core.commands instead of graph_wiki_agent.cli.
  - The old agent test tree retains MCP/plugin tests only; moved CLI test copies and their stale snapshots were removed.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:33:49.072Z
blocker_discovered: false
---

# T02: Relocated gw CLI presentation tests into packages/graph-wiki-cli and removed obsolete graph_wiki_agent.cli test dependencies.

**Relocated gw CLI presentation tests into packages/graph-wiki-cli and removed obsolete graph_wiki_agent.cli test dependencies.**

## What Happened

Created a package-local graph-wiki-cli pytest tree with a focused conftest containing only the plain-help environment convention and the seeded_graph_workspace fixture needed by graph command CliRunner tests. Moved and rewrote the CLI presentation tests for help, query, bootstrap, graph, log, trace rendering, and the seeded graph workspace smoke checks so they exercise graph_wiki_cli.cli, shared graph_wiki_core.commands modules, and the gw console script through uv run --package graph-wiki-cli gw. Copied the graph and trace snapshot baselines into the CLI package and updated the graph query snapshot to match the current output shape including dev_dependencies. Removed obsolete old CLI test copies from agents/graph-wiki-agent/tests/unit, pruned seeded_graph_workspace from the old agent conftest, retained only agent-owned MCP log tests in the old log test file, and updated the remaining MCP graph tests to patch graph_wiki_core.commands.graph, matching the server's shared-command import boundary.

## Verification

Ran the required relocated help/query subset successfully. Ran the full packages/graph-wiki-cli/tests suite successfully, including snapshots and the moved seeded workspace smoke test. Ran all remaining agents/graph-wiki-agent unit tests successfully to ensure pruning old CLI tests and conftest fixtures did not break agent-owned MCP/core coverage. Ran a boundary check confirming the old moved files are absent and relocated CLI tests contain no graph_wiki_agent, graph-wiki-agent, or graph_wiki_agent.cli references.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_help.py packages/graph-wiki-cli/tests/unit/test_cli_query.py` | 0 | ✅ pass | 5562ms |
| 2 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests` | 0 | ✅ pass | 17424ms |
| 3 | `uv run --package graph-wiki-agent python -m pytest agents/graph-wiki-agent/tests/unit` | 0 | ✅ pass | 8511ms |
| 4 | `boundary check: find old moved test files and rg for graph_wiki_agent/graph-wiki-agent/graph_wiki_agent.cli in relocated tests` | 0 | ✅ pass | 33ms |

## Deviations

Moved the seeded_graph_workspace smoke test into graph-wiki-cli as part of relocating the fixture it validates. Updated agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py to patch graph_wiki_core.commands.graph because the MCP server already imports that shared graph module; this kept remaining agent tests aligned with the new package boundary.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-cli/tests/conftest.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_help.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_graph.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_log.py`
- `packages/graph-wiki-cli/tests/unit/test_trace_viewer.py`
- `packages/graph-wiki-cli/tests/unit/test_seeded_graph_workspace_smoke.py`
- `packages/graph-wiki-cli/tests/unit/__snapshots__/test_commands_graph.ambr`
- `packages/graph-wiki-cli/tests/unit/__snapshots__/test_trace_viewer.ambr`
- `agents/graph-wiki-agent/tests/conftest.py`
- `agents/graph-wiki-agent/tests/unit/test_commands_log.py`
- `agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py`
