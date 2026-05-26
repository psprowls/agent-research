---
phase: 260526-d0z-move-graph-wiki-mcp
plan: 01
status: complete
subsystem: mcp
tags: [graph-wiki-agent, mcp, fastmcp, uv, packaging, refactor]

requires: []
provides:
  - graph_wiki_agent.mcp submodule containing the FastMCP server
  - Updated pyproject.toml entry point resolving to graph_wiki_agent.mcp.server:main
  - Zero graph_wiki_mcp references remaining in src/, tests/, or pyproject.toml
affects: [graph-wiki-agent, mcp-integration, wheel-packaging]

tech-stack:
  added: []
  patterns:
    - "MCP server lives as graph_wiki_agent.mcp submodule — single-package wheel discovery works correctly"

key-files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/__init__.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
  modified:
    - agents/graph-wiki-agent/pyproject.toml
    - agents/graph-wiki-agent/tests/unit/test_stdout_guard.py
    - agents/graph-wiki-agent/tests/unit/test_commands_log.py
    - agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py
    - agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py
    - agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py
    - agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py

key-decisions:
  - "Used git mv to preserve file history for server.py and __init__.py during relocation"
  - "entry point console script name (graph-wiki-mcp) and FastMCP name= kwarg unchanged — only module path moved"

patterns-established:
  - "MCP server is a submodule of the agent package it belongs to, not a sibling package"

requirements-completed: [QUICK-D0Z-01]

duration: 8min
completed: 2026-05-26
---

# Quick 260526-d0z: Move graph_wiki_mcp under graph_wiki_agent Summary

**Relocated standalone graph_wiki_mcp sibling package into graph_wiki_agent.mcp submodule, fixed the uv_build wheel-packaging gap and the graph-io implemented_by D-05 warning, with 165/165 unit tests passing.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-26T13:25:00Z
- **Completed:** 2026-05-26T13:33:00Z
- **Tasks:** 3 (2 with commits, 1 verification-only)
- **Files modified:** 9 (1 deleted, 2 renamed/relocated, 1 toml, 6 test files)

## Accomplishments
- `graph_wiki_mcp/` sibling directory removed; files relocated via `git mv` to `graph_wiki_agent/mcp/`
- `pyproject.toml` entry point updated to `graph_wiki_agent.mcp.server:main` (console script name unchanged)
- All six unit test files updated: import paths and `patch()` string targets rewritten from `graph_wiki_mcp.*` to `graph_wiki_agent.mcp.*`
- `uv sync` rebuilt the editable install with the new entry point shim
- 165 unit tests pass; `cg update --full` emits zero implemented_by warnings for graph-wiki-mcp

## Task Commits

1. **Task 1: Relocate graph_wiki_mcp into graph_wiki_agent.mcp and update entry point** - `2b8e18d` (refactor)
2. **Task 2: Update unit-test imports from graph_wiki_mcp to graph_wiki_agent.mcp** - `b729842` (refactor)
3. **Task 3: Resync workspace, run unit tests, re-run cg update --full** - verification only, no file edits

## Files Created/Modified
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/__init__.py` - MCP submodule init (renamed from graph_wiki_mcp/__init__.py)
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` - FastMCP server (renamed from graph_wiki_mcp/server.py)
- `agents/graph-wiki-agent/pyproject.toml` - Entry point updated to graph_wiki_agent.mcp.server:main
- `tests/unit/test_stdout_guard.py` - Import paths updated
- `tests/unit/test_commands_log.py` - Import paths and patch() strings updated
- `tests/unit/test_mcp_schema_forbid_extra.py` - Import paths updated
- `tests/unit/test_wiki_scan_input.py` - Import paths updated
- `tests/unit/test_mcp_query_schema.py` - Import paths and patch() strings updated
- `tests/unit/test_mcp_new_tools.py` - Import paths and patch() strings updated

## Decisions Made
- Used `git mv` for both files to preserve history through the rename
- Did not modify `server.py` contents — outbound imports and FastMCP `name="graph-wiki-mcp"` kwarg were already correct
- Integration tests not touched — they invoke the console script by name, not by import path

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `rmdir` on `graph_wiki_mcp/` failed because a `__pycache__` subdirectory remained after `git mv`. Removed with `rm -rf __pycache__` then `rmdir`. No plan deviation.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The graph-wiki-agent wheel will now include the MCP server in single-package discovery
- `cg update --full` runs clean — the D-05 implemented_by warning is resolved
- No further action needed for this quick fix

---
*Phase: 260526-d0z-move-graph-wiki-mcp*
*Completed: 2026-05-26*
