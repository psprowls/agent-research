# S03: MCP package extraction — Research

**Date:** 2026-05-31

## Summary

S03 owns active requirement R004: the MCP package must own the MCP server entrypoint and schemas. It supports R001/R006/R007 by making the MCP surface a focused package, colocating MCP tests, and preserving stdio/schema launchability. S01 already moved shared command logic to `graph_wiki_core.commands`, and the current server already imports from that namespace, so extraction should be primarily a package/namespace/test relocation rather than a protocol redesign.

The current MCP implementation is `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`. Its most important invariant is the stdout guard: it rebinds `sys.stdout` before importing logging, FastMCP, Pydantic, or graph-wiki command modules. This guard protects newline-delimited JSON-RPC framing on stdout and must remain at the top of the moved `graph_wiki_mcp.server` module. The current `graph-wiki-agent` package also declares the `graph-wiki-mcp` script; S03 should move that script to `graph-wiki-mcp = "graph_wiki_mcp.server:main"` in a new focused package and remove MCP tests' dependency on `graph_wiki_agent.mcp`.

Recommended depth is targeted-to-deep around stdio behavior: FastMCP itself is known locally, but the import-order/stdout-guard invariant is fragile. Memory findings confirm the package split decision, no `graph_wiki_agent` shims, and direct consumption of `graph_wiki_core.commands`. Relevant installed skills are `uv-package-manager`, `python-testing-patterns`, and `create-mcp-server` for MCP schema/stdio thinking; no new skill installation is required for this research.

## Recommendation

Create `packages/graph-wiki-mcp` as a focused MCP server package with namespace `graph_wiki_mcp` and one script:

```toml
[project.scripts]
graph-wiki-mcp = "graph_wiki_mcp.server:main"
```

Move `server.py` to `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` and preserve the top-of-file guard exactly in spirit: `from __future__` and `import sys`, capture `_ORIGINAL_STDOUT`, define `_StdoutGuard`, assign `sys.stdout`, and only then import logging/FastMCP/Pydantic/Path/core command modules. Update tests to import `graph_wiki_mcp.server` and subprocess-spawn `uv run --package graph-wiki-mcp graph-wiki-mcp`. Do not create a `graph_wiki_agent.mcp` compatibility package.

Package dependencies should include direct MCP surface dependencies (`mcp>=1.27.1`, `pydantic>=2.0`) plus `graph-wiki-core` and any directly imported workspace packages not provided through core. The server imports command result models/functions from `graph_wiki_core.commands.*`; keep those imports as direct core imports. S04 owns CLI shim/docs rewiring, and S05 owns deleting `agents/`, so S03 should focus on MCP ownership and package-local tests.

## Implementation Landscape

### Key Files

- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` — current FastMCP server. Move to `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`; update module docstring/import paths only where needed; keep `_StdoutGuard`, `mcp = FastMCP(name="graph-wiki-mcp")`, tool names, Pydantic schemas, and `main()` behavior.
- `agents/graph-wiki-agent/pyproject.toml` — currently declares `graph-wiki-mcp = "graph_wiki_agent.mcp.server:main"` and includes MCP deps. S03 should transfer MCP script ownership to the new package. If the temporary agent package remains until S05, avoid duplicate active ownership or stale tests that call it.
- `packages/graph-wiki-mcp/pyproject.toml` — new package metadata. Direct dependencies should include `graph-wiki-core`, `mcp>=1.27.1`, and `pydantic>=2.0`. Include `uv_build>=0.11.14,<0.12` and `[tool.uv.sources] graph-wiki-core = { workspace = true }`.
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py` — new namespace marker; keep minimal to avoid stdout/import side effects.
- `agents/graph-wiki-agent/tests/unit/test_stdout_guard.py` — move to `packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py`; update imports from `graph_wiki_agent.mcp` to `graph_wiki_mcp`.
- `agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py`, `test_mcp_schema_forbid_extra.py`, `test_mcp_new_tools.py`, `test_mcp_graph_tools.py`, `test_wiki_scan_input.py`, `test_commands_log.py` where it imports server — move/update if they validate MCP schemas/tools rather than core command behavior.
- `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py` — critical subprocess/stdio test. Move to `packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py`; update `_run_server()` command to `uv run --package graph-wiki-mcp graph-wiki-mcp`. Preserve initialize + notifications/initialized + tools/call sequence and JSON-RPC assertions.
- `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` and `test_mcp_cancel.py` — likely MCP-owned integration tests; update package/script/imports if moved during S03.
- `pyproject.toml` — root already includes `packages/*`, so the new MCP package will be discovered. S05 later removes `agents/*`.

### Build Order

1. Create `packages/graph-wiki-mcp` pyproject and source skeleton. Add direct dependencies and workspace source for `graph-wiki-core`.
2. Move server module and update namespace to `graph_wiki_mcp.server`. Do a minimal import smoke first; be careful because importing the server intentionally mutates `sys.stdout`, so tests should use monkeypatch/capture patterns like the existing stdout guard tests.
3. Update/move unit schema/tool tests to the MCP package. Start with `test_stdout_guard.py` and `test_mcp_query_schema.py`/schema-forbid tests because they prove import namespace and Pydantic schema ownership without real Bedrock.
4. Update/move stdio subprocess tests. This is the highest-value launchability proof and should run before broader integration tests.
5. Run `uv sync`, targeted import, package-local pytest, and stale-reference checks.

### Natural Seams

- Package metadata + script entrypoint can be implemented independently of schema-test relocation.
- Server namespace move is one seam; tool schemas should not change semantically.
- Stdout guard tests and stdio subprocess tests are separate seams; guard tests catch import-order mistakes, subprocess tests catch actual JSON-RPC framing mistakes.
- MCP integration tests that call Bedrock or expensive command paths can remain gated by existing `GRAPH_WIKI_RUN_INTEGRATION` behavior; do not silently remove the gates.

### Constraints and Watch-outs

- Stdout guard import order is load-bearing. Do not run formatters or import-sorting changes that move `logging`, `Path`, `FastMCP`, `pydantic`, or `graph_wiki_core` imports above `sys.stdout = _StdoutGuard()`.
- `from __future__ import annotations` may appear before imports, but the guard must execute before all imports with stdout side effects.
- FastMCP tool argument shape in tests is nested: `arguments={"input": {"message": "hello"}}`. The current test documents that the flat form does not validate for a Pydantic-typed parameter.
- `wiki_ping` is intentionally not integration-gated because it proves stdio without Bedrock. Keep it fast/default.
- `tools/list` tests may be marked integration due to heavier imports; preserve existing gating unless the implementation makes them reliably default-safe.
- Do not introduce `graph_wiki_agent.mcp` shims or tests that still import the old namespace.
- Preserve `FastMCP(name="graph-wiki-mcp")`; tests assert the MCP server identity.

### Verification

Recommended targeted verification for S03:

```bash
uv sync
uv run --package graph-wiki-mcp python - <<'PY'
import sys
orig = sys.stdout
try:
    import graph_wiki_mcp.server as server
    assert server.mcp.name == "graph-wiki-mcp"
    assert hasattr(server, "main")
finally:
    sys.stdout = orig
print("mcp import ok")
PY
uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py
uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py
rg -n "graph_wiki_agent\.mcp|uv run --package graph-wiki-agent graph-wiki-mcp|graph_wiki_agent" packages/graph-wiki-mcp
```

The import-smoke restores `sys.stdout` after importing because the server module intentionally guards stdout. The stale-reference check should be clean for the MCP package; references to plugin identity `graph-wiki-agent` elsewhere are not S03's concern unless they are executable MCP imports/scripts.

## Skill Discovery

- Installed and directly relevant: `create-mcp-server` (MCP server/tool/stdio evaluation concerns), `uv-package-manager` (workspace package/scripts), and `python-testing-patterns` (pytest relocation and integration gates).
- FastMCP/mcp is already used locally and the existing server/tests are the primary source of truth; no additional external skill search or library documentation lookup was needed for this slice.
