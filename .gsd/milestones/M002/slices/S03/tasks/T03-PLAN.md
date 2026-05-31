---
estimated_steps: 9
estimated_files: 3
skills_used: []
---

# T03: Move stdio and MCP integration tests to the new package

Why: The slice is not complete until MCP host launchability is proven through the real `graph-wiki-mcp` script owned by the new package. The default-safe `wiki_ping` stdio test is the key integration proof because it exercises JSON-RPC framing without Bedrock.

Do:
1. Move MCP integration tests from `agents/graph-wiki-agent/tests/integration` into `packages/graph-wiki-mcp/tests/integration`: `test_mcp_stdio.py`, `test_mcp_e2e.py`, and `test_mcp_cancel.py`.
2. Update subprocess commands from `uv run --package graph-wiki-agent graph-wiki-mcp` to `uv run --package graph-wiki-mcp graph-wiki-mcp`.
3. Preserve the default-safe `test_mcp_stdio.py` behavior for `initialize`, `notifications/initialized`, and `tools/call wiki_ping` without requiring Bedrock.
4. Preserve existing integration gates such as `GRAPH_WIKI_RUN_INTEGRATION` for heavier tools/list or end-to-end tests that may require real model/backend access.
5. Keep JSON-RPC assertions strict enough to catch stdout contamination, protocol errors, wrong tool names, and schema call-shape regressions.

Done when: the new package's stdio integration test launches the real script and returns a valid `wiki_ping` pong/echo response. Expected executor skills: `create-mcp-server`, `python-testing-patterns`, `uv-package-manager`.

Threat Surface (Q3): The subprocess is an MCP host-facing boundary; any stray stdout byte breaks clients, so tests must inspect protocol JSON and stderr separately. Requirement Impact (Q4): Covers R004 launchability and supports R007 integration verification. Failure Modes (Q5): If `uv` is absent, preserve the existing skip behavior; if the process times out, surface stdout/stderr in pytest failure diagnostics; if JSON is malformed, fail rather than tolerating partial output. Load Profile (Q6): Per-test cost is one local subprocess and no Bedrock for `wiki_ping`; heavier E2E remains gated. Negative Tests (Q7): Retain assertions for missing/invalid response frames, tool errors, and the documented nested `arguments={"input": ...}` shape.

## Inputs

- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py`
- `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py`
- `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py`

## Expected Output

- `packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py`
- `packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py`

## Verification

uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py

## Observability Impact

The stdio test becomes the main operational diagnostic for MCP framing: failures include subprocess return code, stdout frames, and stderr logs.
