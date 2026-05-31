---
estimated_steps: 12
estimated_files: 13
skills_used: []
---

# T01: Create graph-wiki-core package and migrate shared source

Expected executor skills: `uv-package-manager` and `python-testing-patterns`.

Why: R002 requires the shared implementation to become an honest library-only package named `graph-wiki-core` with import namespace `graph_wiki_core`. This task creates the new package boundary and moves the shared source before downstream presentation packages are extracted.

Do:
1. Create `packages/graph-wiki-core/pyproject.toml` using `uv_build`, project name `graph-wiki-core`, Python `>=3.11`, no `[project.scripts]`, and workspace sources for local dependencies (`wiki-io`, `graph-io`, `model-adapter`, `subagent-runtime`, `workspace-io`). Include the current command/runtime dependencies required by moved modules: `bm25s==0.3.8`, `langchain-aws>=1.4.7`, `typer>=0.25.1` if Typer wrappers remain in moved command modules for S01, `pydantic>=2.0` if still imported, and `python-frontmatter>=1.1.0` for vault migration code.
2. Create `packages/graph-wiki-core/src/graph_wiki_core/` and move/copy the shared modules from `agents/graph-wiki-agent/src/graph_wiki_agent`: `commands/`, `prompts/`, `graph_tools.py`, `config.py`, `uri_slug.py`, and package `__init__.py` as appropriate.
3. Preserve prompt source markdown files under `prompts/sources/`, but do not copy any `__pycache__/` directories or `.pyc` files.
4. Rewrite imports inside the moved source from `graph_wiki_agent` to `graph_wiki_core`, including prompt provenance helpers and command references.
5. Keep `cli.py` and `mcp/` out of core; they remain temporary presentation code for later tasks/slices.

Threat Surface (Q3): no new auth or external API surface is introduced; the risk is import/path confusion and accidentally packaging stale bytecode or executable entrypoints.
Failure Modes (Q5): if uv dependency metadata is incomplete, package import fails; if imports are only partially rewritten, moved modules resolve the old namespace; if `__pycache__` is copied, source distributions include stale artifacts.
Negative Tests (Q7): verify core has no console scripts, no copied `__pycache__`, and import smoke resolves `graph_wiki_core` modules.
Done when: the core package can be imported directly and contains the shared source under `graph_wiki_core` without relying on old `graph_wiki_agent` command modules.

## Inputs

- `pyproject.toml`
- `agents/graph-wiki-agent/pyproject.toml`
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands`
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts`
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/config.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py`

## Expected Output

- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-core/src/graph_wiki_core`
- `packages/graph-wiki-core/src/graph_wiki_core/__init__.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands`
- `packages/graph-wiki-core/src/graph_wiki_core/prompts`
- `packages/graph-wiki-core/src/graph_wiki_core/graph_tools.py`
- `packages/graph-wiki-core/src/graph_wiki_core/config.py`
- `packages/graph-wiki-core/src/graph_wiki_core/uri_slug.py`

## Verification

uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query"

## Observability Impact

Import-smoke failures localize missing dependencies or stale namespace rewrites to the new core package.
