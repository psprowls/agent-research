# S03: MCP package extraction

**Goal:** Extract the graph-wiki MCP surface into a focused packages/graph-wiki-mcp workspace member that owns the graph-wiki-mcp console script, graph_wiki_mcp import namespace, FastMCP schemas/tools, and stdio launchability tests while consuming shared command logic from graph_wiki_core.
**Demo:** `packages/graph-wiki-mcp` exposes `graph-wiki-mcp`, MCP tests import `graph_wiki_mcp`, and stdio/schema tests prove the server still works.

## Must-Haves

- `packages/graph-wiki-mcp` exists as a uv workspace package named `graph-wiki-mcp` with import namespace `graph_wiki_mcp`.
- The `graph-wiki-mcp` console script is declared by the new MCP package and points at `graph_wiki_mcp.server:main`; the temporary `graph-wiki-agent` package no longer owns that script.
- The moved server preserves `FastMCP(name="graph-wiki-mcp")`, all existing tool schemas/tool names, and the load-bearing stdout guard import order.
- MCP unit and integration tests live under `packages/graph-wiki-mcp/tests` and import/patch `graph_wiki_mcp.server`, not `graph_wiki_agent.mcp.server`.
- At least one default-safe stdio subprocess test launches `uv run --package graph-wiki-mcp graph-wiki-mcp` and proves `wiki_ping` JSON-RPC framing works without Bedrock.
- A package-boundary test or equivalent executable assertion rejects stale active MCP imports/scripts under `graph_wiki_agent`.

## Proof Level

- This slice proves: Integration proof. The slice must prove both package/import contracts and the real stdio console entrypoint path. Human/UAT is not required; Bedrock-backed integration paths may remain gated, but `wiki_ping` stdio launchability must run by default.

## Integration Closure

Consumes S01's `graph_wiki_core.commands` package boundary and S02's package-only presentation pattern. Introduces the final MCP runtime wiring for this milestone. S04 still rewires docs/plugin subprocess references to `gw`, and S05 still removes the obsolete `agents/` layout and runs full workspace verification.

## Verification

- No new runtime observability surfaces are planned. Failure visibility comes from preserving the stdout guard, stderr logging configuration, package-boundary tests, schema tests, and stdio subprocess tests that expose protocol-framing regressions immediately.

## Tasks

- [x] **T01: Create the graph-wiki-mcp package and move the guarded server** `est:1h 30m`
  Why: R004 requires MCP hosts to depend on a focused server package rather than the temporary all-in-one agent package, and the stdout guard is the highest-risk invariant during the namespace move.
  - Files: `packages/graph-wiki-mcp/pyproject.toml`, `packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py`, `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, `packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py`, `agents/graph-wiki-agent/pyproject.toml`, `uv.lock`
  - Verify: uv sync && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py

- [x] **T02: Relocate MCP schema and tool unit tests** `est:2h`
  Why: R006 requires tests to live with the package they validate, and R004 requires the MCP package to own schemas and tool wrappers. Moving only the server without its tests would leave the old namespace as the practical test owner.
  - Files: `packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py`, `packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py`, `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`, `packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py`, `packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py`, `packages/graph-wiki-mcp/tests/unit/test_commands_log.py`
  - Verify: uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit

- [x] **T03: Move stdio and MCP integration tests to the new package** `est:1h 30m`
  Why: The slice is not complete until MCP host launchability is proven through the real `graph-wiki-mcp` script owned by the new package. The default-safe `wiki_ping` stdio test is the key integration proof because it exercises JSON-RPC framing without Bedrock.
  - Files: `packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py`, `packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py`, `packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py`
  - Verify: uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py

- [x] **T04: Enforce the MCP package boundary and close targeted verification** `est:1h 30m`
  Why: After relocation, the repo needs an executable boundary check so stale `graph_wiki_agent.mcp` imports or old script ownership fail fast instead of hiding an incomplete split. This also gives S05 a clean package-local verification target.
  - Files: `packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/__init__.py`, `agents/graph-wiki-agent/tests/unit/test_stdout_guard.py`, `agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py`, `agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py`, `agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py`, `agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py`, `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py`, `agents/graph-wiki-agent/tests/unit/test_commands_log.py`, `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py`, `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py`, `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py`
  - Verify: uv sync && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests

## Files Likely Touched

- packages/graph-wiki-mcp/pyproject.toml
- packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py
- packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
- packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py
- agents/graph-wiki-agent/pyproject.toml
- uv.lock
- packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py
- packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py
- packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
- packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py
- packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py
- packages/graph-wiki-mcp/tests/unit/test_commands_log.py
- packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py
- packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py
- packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py
- packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py
- agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
- agents/graph-wiki-agent/src/graph_wiki_agent/mcp/__init__.py
- agents/graph-wiki-agent/tests/unit/test_stdout_guard.py
- agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py
- agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py
- agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py
- agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py
- agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py
- agents/graph-wiki-agent/tests/unit/test_commands_log.py
- agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py
- agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py
- agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py
