---
estimated_steps: 12
estimated_files: 6
skills_used: []
---

# T02: Rewire temporary graph-wiki-agent presentation consumers

Expected executor skills: `uv-package-manager`.

Why: S02 and S03 will later extract CLI and MCP surfaces, but S01 must not break the current executable package while core is moved. The temporary `graph-wiki-agent` package should become a presentation consumer of `graph-wiki-core`, not a backward-compatible core shim.

Do:
1. Add `graph-wiki-core` as a workspace dependency/source in `agents/graph-wiki-agent/pyproject.toml` while keeping existing `graph-wiki-agent` and `graph-wiki-mcp` scripts unchanged for this slice only.
2. Rewrite `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` imports so CLI commands call `graph_wiki_core.commands.*` and related core helpers.
3. Rewrite command imports in `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` to `graph_wiki_core.commands.*` without moving or refactoring the load-bearing stdout guard that must remain before imports.
4. Remove or stop relying on old shared implementation modules under `agents/graph-wiki-agent/src/graph_wiki_agent` after presentation imports are rewired; do not add `graph_wiki_agent.commands` compatibility shims.
5. Leave plugin identity files and vault manifests alone; D004 says plugin identity remains `graph-wiki-agent` for now.

Threat Surface (Q3): no new user input surface is added; the main risk is accidentally preserving old import shims that hide incomplete migration.
Failure Modes (Q5): if CLI/MCP imports move above the stdout guard, MCP stdio behavior can regress; if the old command namespace remains importable via shims, stale references will not fail as intended.
Negative Tests (Q7): run help smoke for temporary scripts and later boundary tests that reject `graph_wiki_agent.commands` active imports.
Done when: current CLI/MCP entry modules compile against `graph_wiki_core` and the old package is only a temporary presentation owner, not a duplicate core implementation.

## Inputs

- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-core/src/graph_wiki_core/commands`
- `agents/graph-wiki-agent/pyproject.toml`
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`

## Expected Output

- `agents/graph-wiki-agent/pyproject.toml`
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/__init__.py`

## Verification

uv run --package graph-wiki-agent graph-wiki-agent --help

## Observability Impact

Temporary help-smoke failures show whether presentation modules still import stale core paths or broke the MCP stdout-guard ordering.
