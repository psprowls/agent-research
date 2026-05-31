---
estimated_steps: 9
estimated_files: 6
skills_used: []
---

# T02: Relocate MCP schema and tool unit tests

Why: R006 requires tests to live with the package they validate, and R004 requires the MCP package to own schemas and tool wrappers. Moving only the server without its tests would leave the old namespace as the practical test owner.

Do:
1. Move MCP-owned unit tests from `agents/graph-wiki-agent/tests/unit` into `packages/graph-wiki-mcp/tests/unit`: `test_mcp_query_schema.py`, `test_mcp_schema_forbid_extra.py`, `test_mcp_new_tools.py`, `test_mcp_graph_tools.py`, `test_wiki_scan_input.py`, and `test_commands_log.py`.
2. Update all imports and mocks from `graph_wiki_agent.mcp.server` to `graph_wiki_mcp.server`.
3. Keep tests deterministic and Bedrock-free by preserving existing mocks around `run_query`, `run_scan`, `run_ingest_source`, `run_ingest_work_item`, `run_init`, `run_lint`, and `run_log`.
4. Preserve current Pydantic validation expectations, including `extra='forbid'`, `top_k` bounds, scan mode validation, and nested FastMCP argument shape where already asserted.
5. Add or update package-local pytest configuration only if needed so these tests run from the workspace root with importlib mode.

Done when: the package-local MCP unit suite passes and no moved unit test imports or patches `graph_wiki_agent.mcp`. Expected executor skills: `python-testing-patterns`, `create-mcp-server`.

Requirement Impact (Q4): Covers R004 schema ownership and supports R006 test colocation. Failure Modes (Q5): If imports trigger the stdout guard and break pytest capture, adapt the existing stdout restoration fixture/pattern rather than disabling the guard. Negative Tests (Q7): Retain validation tests for forbidden extras, invalid ranges, wrong scan options, and mocked command error/result boundaries.

## Inputs

- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- `agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py`
- `agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py`
- `agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py`
- `agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py`
- `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py`
- `agents/graph-wiki-agent/tests/unit/test_commands_log.py`

## Expected Output

- `packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py`
- `packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py`
- `packages/graph-wiki-mcp/tests/unit/test_commands_log.py`

## Verification

uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit

## Observability Impact

No runtime observability changes; failures become visible through package-local schema/tool unit tests.
