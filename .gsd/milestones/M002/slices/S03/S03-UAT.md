# S03: MCP package extraction — UAT

**Milestone:** M002
**Written:** 2026-05-31T16:54:47.575Z

## UAT Type
Automated package/import/stdio verification; no human UI workflow required.

## Preconditions
- Work from `/Users/pat/Personal/agent-research`.
- Dependencies are synced with `uv sync`.
- Bedrock-backed integration tests may remain gated unless `GRAPH_WIKI_RUN_INTEGRATION=1` is explicitly set; the `wiki_ping` stdio path must run by default without Bedrock credentials.

## Steps
1. Run `uv sync`.
2. Run `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests`.
3. Confirm the package entrypoint by inspecting/importing `graph_wiki_mcp.server` and checking that `packages/graph-wiki-mcp/pyproject.toml` declares `graph-wiki-mcp = "graph_wiki_mcp.server:main"`.
4. Confirm the old active MCP namespace is gone: `importlib.util.find_spec("graph_wiki_agent.mcp")` returns `None`, `agents/graph-wiki-agent/src/graph_wiki_agent/mcp` is absent, and old MCP tests are not present under `agents/graph-wiki-agent/tests`.
5. In the stdio tests, verify the real command path `uv run --package graph-wiki-mcp graph-wiki-mcp` can answer a JSON-RPC `wiki_ping` request with valid framing.

## Expected Outcomes
- The package-local MCP suite passes: 56 tests pass and only Bedrock-gated integration tests are skipped by the existing guard.
- MCP hosts can target the focused `graph-wiki-mcp` package and `graph_wiki_mcp.server` namespace.
- The server still presents `FastMCP(name="graph-wiki-mcp")` and preserves existing tool/schema behavior.
- Stdout pollution is rejected before it can corrupt JSON-RPC framing.
- Stale `graph_wiki_agent.mcp` imports or old MCP script ownership fail fast through package-boundary tests.

## Edge Cases
- Accidental non-whitespace stdout writes during server import should fail stdout guard tests.
- Extra fields in MCP schemas should remain rejected by schema tests.
- Bedrock-dependent E2E paths should stay gated by `GRAPH_WIKI_RUN_INTEGRATION=1` and must not block default-safe verification.
- Reintroducing old `graph_wiki_agent.mcp` shims or old MCP tests under `agents/` should fail boundary verification.
