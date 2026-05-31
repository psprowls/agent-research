---
estimated_steps: 11
estimated_files: 6
skills_used: []
---

# T01: Create the graph-wiki-mcp package and move the guarded server

Why: R004 requires MCP hosts to depend on a focused server package rather than the temporary all-in-one agent package, and the stdout guard is the highest-risk invariant during the namespace move.

Do:
1. Create `packages/graph-wiki-mcp/pyproject.toml` as a uv_build workspace package named `graph-wiki-mcp` with dependencies on `graph-wiki-core`, `mcp>=1.27.1`, and `pydantic>=2.0`, plus `[project.scripts] graph-wiki-mcp = "graph_wiki_mcp.server:main"` and a workspace source for `graph-wiki-core`.
2. Create `packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py` with no side-effect imports.
3. Move/copy the current server implementation from `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` to `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` and update only namespace/docstring details needed for the new package.
4. Preserve the guard order exactly in spirit: `from __future__`, `import sys`, `_ORIGINAL_STDOUT`, `_StdoutGuard`, `sys.stdout = _StdoutGuard()`, and only then logging, pathlib, FastMCP, Pydantic, and `graph_wiki_core` imports.
5. Remove the `graph-wiki-mcp` console script from `agents/graph-wiki-agent/pyproject.toml` so there is only one active script owner.
6. Move `agents/graph-wiki-agent/tests/unit/test_stdout_guard.py` to `packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py` and update imports from `graph_wiki_agent.mcp` to `graph_wiki_mcp`.
7. Run `uv sync` so the lockfile knows about the new workspace member.

Done when: `graph_wiki_mcp.server` imports under test control, `server.mcp.name` remains `graph-wiki-mcp`, `wiki_ping` still returns pong, and stdout guard tests pass from the new package. Expected executor skills: `uv-package-manager`, `python-testing-patterns`, `create-mcp-server`.

Threat Surface (Q3): MCP stdio is sensitive to stdout corruption; keep all diagnostics on stderr and do not add print/debug output. Requirement Impact (Q4): Covers R004 and supports R001/R006/R007; decisions D002 and D003 remain in force. Failure Modes (Q5): If `uv sync` cannot resolve the workspace source, fix package metadata before proceeding; if importing the server mutates stdout during tests, restore stdout using the existing test pattern rather than weakening the guard. Negative Tests (Q7): The moved stdout guard test must still prove non-empty writes raise, empty writes are ignored, and `wiki_ping` works after import.

## Inputs

- `agents/graph-wiki-agent/pyproject.toml`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`
- `agents/graph-wiki-agent/tests/unit/test_stdout_guard.py`
- `packages/graph-wiki-core/pyproject.toml`

## Expected Output

- `packages/graph-wiki-mcp/pyproject.toml`
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/__init__.py`
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- `packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py`
- `agents/graph-wiki-agent/pyproject.toml`
- `uv.lock`

## Verification

uv sync && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit/test_stdout_guard.py

## Observability Impact

Preserves the existing stdout guard and stderr logging configuration, which are the runtime diagnostics boundary for MCP stdio framing failures.
