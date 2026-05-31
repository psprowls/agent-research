# S01 — Research

**Date:** 2026-05-31

## Summary

S01 is a targeted but high-blast-radius package migration. The current implementation is a single workspace member at `agents/graph-wiki-agent` with three kinds of code mixed under `src/graph_wiki_agent`: shared command/prompt/runtime helpers, a Typer CLI (`cli.py`), and a FastMCP stdio server (`mcp/server.py`). The core rename should create `packages/graph-wiki-core` with import namespace `graph_wiki_core` and move the shared library modules there first: `commands/`, `prompts/`, `graph_tools.py`, `config.py`, and `uri_slug.py`.

The safest S01 approach is a mechanical package move/rename plus import rewrite, while leaving CLI/MCP extraction to later slices. During S01, the existing `agents/graph-wiki-agent` package can remain temporarily as the executable presentation package, but it should import shared commands from `graph_wiki_core` and depend on `graph-wiki-core`. That preserves current subprocess/MCP behavior while proving the new core import surface. Do not add `graph_wiki_agent` shims or old aliases; stale imports should be actively rewritten in core-facing tests and dependents.

Active requirements supported: R002 is directly owned by S01 (`graph-wiki-core` is library-only and renamed); R001/R006/R007 are supported by establishing the first real package boundary, moving core tests toward package colocation, and keeping workspace verification runnable for downstream slices.

## Recommendation

Create `packages/graph-wiki-core` as a uv workspace package named `graph-wiki-core`, using `uv_build`, no `[project.scripts]`, and namespace `graph_wiki_core`. Move only the shared implementation into it, excluding `cli.py`, `mcp/`, `__pycache__/`, and presentation-only tests. Rewrite internal imports from `graph_wiki_agent.*` to `graph_wiki_core.*`.

For this slice, keep the old executable package only as a temporary consumer if needed for workspace continuity: add `graph-wiki-core` as a workspace dependency to `agents/graph-wiki-agent`, rewrite `cli.py` and `mcp/server.py` imports to `graph_wiki_core.commands...`, and leave script renames to S02/S03. This avoids making S01 also solve all CLI/MCP ownership. If the planner chooses a hard move that breaks `agents/graph-wiki-agent`, then S02/S03 must immediately follow; the lower-risk path is to let old presentation surfaces compile against the new core until extracted.

Use the installed `uv-package-manager` skill as relevant guidance if execution needs uv-specific decisions; no external skill install is needed. No current library docs lookup was necessary because the work follows existing local uv workspace patterns.

## Implementation Landscape

### Key Files

- `pyproject.toml` — root workspace currently has `members = ["packages/*", "agents/*"]`. S01 can leave this alone if the temporary executable package remains; S05 owns final packages-only removal of `agents/*`.
- `agents/graph-wiki-agent/pyproject.toml` — current monolith package named `graph-wiki-agent`, with dependencies on `wiki-io`, `model-adapter`, `subagent-runtime`, `workspace-io`, `graph-io`, `bm25s`, `mcp`, `langchain-aws`, `typer`, and `pydantic`; scripts are `graph-wiki-agent` and `graph-wiki-mcp`. S01 should not copy these scripts into core.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/` — primary shared command implementation. Move to `packages/graph-wiki-core/src/graph_wiki_core/commands/` and rewrite imports.
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/` — prompt builders/fragments used by command modules. Move to `graph_wiki_core.prompts`; includes `.md` prompt source files that must be preserved as package data by `uv_build`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py` — used by `commands/query.py`; move to core.
- `agents/graph-wiki-agent/src/graph_wiki_agent/config.py` and `uri_slug.py` — helper modules referenced by tests/commands; move to core.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — Typer CLI surface. Do not move into core. In S01, rewrite imports to `graph_wiki_core.commands.*` if this package remains as a temporary consumer.
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` — MCP surface with load-bearing stdout guard before imports. Do not move into core. In S01, only rewrite command imports to `graph_wiki_core.commands.*`; S03 owns namespace/package extraction.
- `packages/eval-harness/pyproject.toml` — currently depends on `graph-wiki-agent`; S01 should update dependency/source to `graph-wiki-core`.
- `packages/eval-harness/src/eval_harness/structural.py`, `sweep.py`, `tests/eval_helpers.py`, `tests/test_*.py` — active imports of `graph_wiki_agent.commands.*`; update to `graph_wiki_core.commands.*` as a core consumer.
- `agents/graph-wiki-agent/tests/` — mixed test tree. Core-facing tests include `tests/commands/`, most `tests/prompts/`, `test_command_overrides.py`, `test_ingest_trace_unit.py`, `test_migrate_vault.py`, `test_propose_domains.py`, `test_query_graph_tools.py`, `test_query_trace_unit.py`, and many `tests/unit/test_commands_*`, `test_config.py`, `test_graph_tools.py`, `test_query_*`, `test_scan_*`, `test_trace_viewer.py`, `test_uri_slug.py`. CLI-only and MCP-only tests should be deferred or left with temporary package until later slices.

### Current Source Dependency Shape

Core command modules currently import these workspace/runtime deps:

- `commands/ingest.py` — `graph_io`, `langchain_core`, `model_adapter`, `subagent_runtime`, `wiki_io`, `workspace_io`, prompt/core helpers.
- `commands/query.py` — `bm25s`, `langchain_aws`, `langchain_core`, `model_adapter`, `subagent_runtime`, `graph_io`, `wiki_io`, `workspace_io`, `graph_tools`.
- `commands/scan.py`, `commands/lint.py`, `commands/propose_domains.py` — LLM/subagent/runtime deps plus graph/wiki/workspace IO.
- `commands/migrate_vault.py` — `python-frontmatter` import as `frontmatter` plus `wiki_io`, `workspace_io`.
- `commands/graph.py` and `commands/propose_domains.py` currently import `typer` because they include Typer-facing wrappers/subapps next to printing-free command functions.

This creates a boundary choice for S01: either keep `typer` as a temporary core dependency because those modules still expose `graph_app`/CLI wrappers, or split Typer wrappers from pure command functions now. The clean final architecture wants Typer in `graph-wiki-cli`, but moving all Typer app definitions in S01 may over-expand the slice. If keeping Typer temporarily, document it as technical debt for S02 and verify core is still library-only by absence of scripts, not by zero presentation imports.

### Build Order

1. Create `packages/graph-wiki-core/pyproject.toml` with minimal metadata, no scripts, and workspace sources for local deps. Include current command deps: `wiki-io`, `model-adapter`, `subagent-runtime`, `workspace-io`, `graph-io`, `bm25s==0.3.8`, `langchain-aws>=1.4.7`, `langchain-core` transitively/directly if needed, `pydantic>=2.0` only if moved core code needs it, `python-frontmatter>=1.1.0`; keep `typer>=0.25.1` only if S01 leaves Typer wrappers inside core modules.
2. Copy/move shared source modules into `packages/graph-wiki-core/src/graph_wiki_core/`, excluding `cli.py`, `mcp/`, and all `__pycache__` files. Preserve `prompts/sources/*.md`.
3. Bulk rewrite moved source imports from `graph_wiki_agent` to `graph_wiki_core`. Pay special attention to comments/source anchors in prompt provenance tests; active import/path assertions must change, historical prose can wait if non-executable.
4. Update temporary old presentation package imports (`cli.py`, `mcp/server.py`) to consume `graph_wiki_core.commands` and add `graph-wiki-core` workspace dependency/source to `agents/graph-wiki-agent/pyproject.toml` if that package remains.
5. Update `packages/eval-harness` dependency and active imports from `graph_wiki_agent.commands` to `graph_wiki_core.commands`.
6. Move or copy core-facing tests under `packages/graph-wiki-core/tests/` as far as practical. Defer CLI subprocess tests (`test_cli_*`) and MCP schema/stdio tests (`test_mcp_*`, `test_stdout_guard.py`, integration MCP tests) to S02/S03 unless needed as temporary regression checks against old presentation package.
7. Run package import/test verification before broad stale-reference cleanup, because import failures will identify missed internal rewrites fastest.

### Natural Seams for Planner Tasks

- Package metadata task: create `packages/graph-wiki-core/pyproject.toml`, sources, and package skeleton.
- Source move task: move shared modules and rewrite imports.
- Temporary consumer task: adjust old `graph-wiki-agent` CLI/MCP imports to `graph_wiki_core` so existing executable tests can still run until S02/S03.
- Eval harness task: update workspace dependency/source and imports.
- Core tests task: relocate/update core tests and patch paths/import strings.
- Verification task: run targeted import/test commands and stale active-reference scans.

### Verification

Recommended S01 verification commands after implementation:

```bash
uv sync
uv run --package graph-wiki-core python -c "import graph_wiki_core; import graph_wiki_core.commands.query; import graph_wiki_core.commands.scan; import graph_wiki_core.prompts.scanner"
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests
uv run --package eval-harness pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py
```

If the old executable package is kept as a temporary consumer, also run a smoke check to ensure S01 did not break presentation surfaces before S02/S03:

```bash
uv run --package graph-wiki-agent graph-wiki-agent --help
uv run --package graph-wiki-agent graph-wiki-mcp --help  # or existing MCP stdio smoke if --help is not supported
```

Stale-reference scans useful for S01:

```bash
rg -n "from graph_wiki_agent|import graph_wiki_agent|graph_wiki_agent\.commands" packages/graph-wiki-core packages/eval-harness agents/graph-wiki-agent/src
rg -n "\[project\.scripts\]|graph-wiki-agent =|graph-wiki-mcp" packages/graph-wiki-core/pyproject.toml
```

### Watch-outs

- Do not copy `__pycache__/` files currently present under `agents/graph-wiki-agent/src` and `tests`.
- `mcp/server.py` stdout guard is load-bearing and must remain before imports; do not move or refactor it in S01 beyond changing command import paths.
- Prompt provenance tests contain hardcoded `agents/graph-wiki-agent/src/graph_wiki_agent/...` anchors. Some are executable path assertions and must be updated when prompt sources move; comments/historical rubrics can wait if they are not active assertions.
- `commands/graph.py` and `commands/propose_domains.py` mix pure command functions with Typer wrappers. This is the main architectural seam that may make `typer` leak into core temporarily.
- `eval-harness` has both active imports and historical fixture/wiki references. Update active imports and dependency metadata in S01; do not spend the slice rewriting fixture vault history unless tests assert those exact strings.
- Plugin identity remains `graph-wiki-agent`; do not rewrite `.graph-wiki.yaml`/manifest identity while chasing old names.
