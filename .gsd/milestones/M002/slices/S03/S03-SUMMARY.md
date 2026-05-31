---
id: S03
parent: M002
milestone: M002
provides:
  - `packages/graph-wiki-mcp` workspace member named `graph-wiki-mcp`.
  - `graph_wiki_mcp.server` as the MCP server import surface.
  - `graph-wiki-mcp` console script owned by the MCP package.
  - Package-local MCP unit and integration verification target for S05.
  - Executable boundary checks proving stale `graph_wiki_agent.mcp` active imports/scripts are absent.
requires:
  - slice: S01
    provides: `graph_wiki_core.commands` shared command functions and result models consumed by MCP tools.
affects:
  - S04
  - S05
key_files:
  - packages/graph-wiki-mcp/pyproject.toml
  - packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py
  - packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
  - packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_schema_forbid_extra.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
  - packages/graph-wiki-mcp/tests/unit/test_mcp_graph_tools.py
  - packages/graph-wiki-mcp/tests/unit/test_wiki_scan_input.py
  - packages/graph-wiki-mcp/tests/unit/test_commands_log.py
  - packages/graph-wiki-mcp/tests/integration/test_mcp_stdio.py
  - packages/graph-wiki-mcp/tests/integration/test_mcp_e2e.py
  - packages/graph-wiki-mcp/tests/integration/test_mcp_cancel.py
  - agents/graph-wiki-agent/pyproject.toml
  - uv.lock
key_decisions:
  - The active MCP runtime namespace is `graph_wiki_mcp`; no `graph_wiki_agent.mcp` compatibility shim is introduced.
  - The focused MCP package owns the `graph-wiki-mcp` console script while shared business logic remains in `graph_wiki_core.commands`.
  - Default-safe stdio verification uses `wiki_ping` so MCP launchability is proven without Bedrock credentials.
patterns_established:
  - Presentation packages own their package-local tests and entrypoints while depending on `graph_wiki_core` for shared command logic.
  - Package extraction slices include executable boundary tests that reject stale imports and obsolete script ownership.
  - MCP stdio tests should exercise the real console script path and assert JSON-RPC framing, not just direct Python function calls.
observability_surfaces:
  - No new runtime observability surface; failure visibility is provided by stdout guard tests, schema tests, package-boundary tests, and stdio subprocess diagnostics.
drill_down_paths:
  - .gsd/milestones/M002/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-31T16:54:47.575Z
blocker_discovered: false
---

# S03: MCP package extraction

**Extracted the MCP surface into `packages/graph-wiki-mcp`, owned by the `graph_wiki_mcp` namespace and `graph-wiki-mcp` console script, with package-local schema, tool, boundary, and stdio tests.**

## What Happened

S03 completed the MCP side of the v1.12 package split. The guarded FastMCP server moved into `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, preserving `FastMCP(name="graph-wiki-mcp")`, the stdout guard behavior needed for JSON-RPC stdio framing, the `wiki_ping` default-safe tool, and the existing tool/schema surface while consuming shared command logic from `graph_wiki_core.commands`. The new workspace member declares the `graph-wiki-mcp` package and owns the `graph-wiki-mcp = graph_wiki_mcp.server:main` console script; the temporary `graph-wiki-agent` package no longer owns this MCP runtime surface. Unit tests for schemas, tool wrappers, graph tools, scan input handling, command logs, and the stdout guard were relocated under `packages/graph-wiki-mcp/tests/unit` and retargeted to import/patch `graph_wiki_mcp.server`. MCP integration tests for stdio, E2E, and cancellation were relocated under `packages/graph-wiki-mcp/tests/integration`; the default-safe stdio test launches the real `uv run --package graph-wiki-mcp graph-wiki-mcp` path and proves `wiki_ping` JSON-RPC framing works without Bedrock. A package-boundary test now rejects stale `graph_wiki_agent.mcp` imports and old MCP script ownership, and the old MCP source owner under `agents/graph-wiki-agent/src/graph_wiki_agent/mcp` has been removed. Operational readiness: the health signal is the default-safe `wiki_ping` stdio test and package-local pytest target; the failure signal is stdout-guard/schema/boundary test failure; recovery is to restore the `graph_wiki_mcp.server` entrypoint and rerun the package tests; monitoring gaps are intentionally limited to test-time diagnostics because no new runtime observability surface was planned for this extraction slice.

## Verification

Closeout verification passed. `gsd_exec` run 189a683f-353e-4b9b-a19f-002a0fcc7e49 executed `uv sync && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests` with exit code 0: 56 passed, 2 gated integration tests skipped by the existing `GRAPH_WIKI_RUN_INTEGRATION=1` guard. `gsd_exec` run a8f3929f-e3ef-4317-8caa-e5396a326caa executed static package-boundary assertions with exit code 0: `graph_wiki_mcp.server` is importable, `packages/graph-wiki-mcp/pyproject.toml` owns `graph-wiki-mcp = "graph_wiki_mcp.server:main"`, `graph_wiki_agent.mcp` is not importable, `agents/graph-wiki-agent/src/graph_wiki_agent/mcp` is absent, and no old `test_mcp*.py` files remain under `agents/graph-wiki-agent/tests`. Task-level verification also passed for T01 stdout guard tests, T02 relocated unit tests, T03 stdio/integration tests, and T04 full package test plus boundary checks.

## Requirements Advanced

- R001 — Completed the MCP package extraction portion of the core/CLI/MCP split.
- R006 — Relocated MCP unit and integration tests into `packages/graph-wiki-mcp/tests`.
- R007 — Added and passed package-local stdio, schema, and boundary tests that S05 can include in full workspace verification.

## Requirements Validated

- R004 — `packages/graph-wiki-mcp` owns `graph_wiki_mcp.server`, the `graph-wiki-mcp` console script, MCP schemas/tools, and package-local tests; closeout verification passed with 56 tests passing and boundary checks proving `graph_wiki_agent.mcp` is absent.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

T03 tightened stdio test failure diagnostics and JSON-RPC frame assertions; this supports the slice goal by making protocol-framing regressions easier to diagnose. No scope deviations.

## Known Limitations

Bedrock-backed MCP E2E/cancel paths remain gated behind `GRAPH_WIKI_RUN_INTEGRATION=1`; S05 still owns full workspace integration. S04 still rewires runtime docs and plugin subprocess references to `gw`, and S05 still removes the obsolete `agents/` layout.

## Follow-ups

S04 should update runtime-facing docs and plugin Bedrock shims to use `gw`. S05 should run full workspace verification, complete stale-reference cleanup, and remove the obsolete `agents/` layout.

## Files Created/Modified

- `packages/graph-wiki-mcp/pyproject.toml` — New MCP workspace package metadata, dependencies, and `graph-wiki-mcp` console script.
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` — Moved guarded FastMCP server into the new namespace.
- `packages/graph-wiki-mcp/tests` — Relocated and retargeted MCP unit/integration tests to the new package.
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp` — Removed stale active MCP source owner.
- `agents/graph-wiki-agent/pyproject.toml` — Stopped temporary agent package ownership of the MCP console script.
- `uv.lock` — Updated workspace lock state for the new package.
