---
estimated_steps: 10
estimated_files: 4
skills_used: []
---

# T01: Create graph-wiki-cli package and gw entrypoint

Why: S02 needs a real CLI package before tests can be relocated or subprocess launchability can be proven. The implementation should be a presentation move over S01's graph_wiki_core.commands surface, not a command-logic fork.

Expected executor skills: uv-package-manager, python-testing-patterns.

Do:
1. Create packages/graph-wiki-cli with pyproject.toml using project name graph-wiki-cli, uv_build, pytest importlib mode, and a single project script gw = graph_wiki_cli.cli:app.
2. Declare direct dependencies honestly: graph-wiki-core, graph-io if still imported for exit codes, typer, and any other package directly imported by graph_wiki_cli.cli. Add matching [tool.uv.sources] workspace entries.
3. Create packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py and move or copy the current Typer app from agents/graph-wiki-agent/src/graph_wiki_agent/cli.py to packages/graph-wiki-cli/src/graph_wiki_cli/cli.py.
4. Rename command-facing literals and metadata in the new CLI module: app name/help should say gw, version lookup should use graph-wiki-cli, and version output should identify gw or graph-wiki-cli consistently.
5. Preserve shared implementation imports from graph_wiki_core.commands; do not import command logic through graph_wiki_agent and do not add any graph_wiki_agent compatibility shim.
6. Remove the old graph-wiki-agent console script from agents/graph-wiki-agent/pyproject.toml so the active CLI entrypoint is not retained as an alias. Keep graph-wiki-mcp there for S03 unless S03 has already extracted it.

Done when: uv can target package graph-wiki-cli, import graph_wiki_cli.cli, and the app reports name gw without requiring the old graph_wiki_agent.cli namespace.

## Inputs

- `agents/graph-wiki-agent/pyproject.toml`
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-core/src/graph_wiki_core/commands`
- `packages/graph-io/pyproject.toml`
- `pyproject.toml`

## Expected Output

- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `agents/graph-wiki-agent/pyproject.toml`

## Verification

uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"

## Observability Impact

Adds package/import/script surfaces whose failures are visible via uv package resolution, import errors, and console-script launch failures.
