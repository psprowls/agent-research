# Quick Task: I want to make some more changes to the `gw` cli in `graph-wiki-cli`.  Currently `graph-io` contains the Typer interface (and the`cg` cli tool.  I would like to move all of the Typer interface into `graph-wiki-cli` and remove it from `graph-io` along withremoving the `cg` tool from `graph-io`.  As part of this I want to update references to `cg` throught the code to reference `gwgraph`, etc.  There may also be changes to the docs as part of this, but you will need to verify that.

**Date:** 2026-05-31
**Branch:** main

## What Changed
- Moved the legacy code-graph argparse CLI implementation from `packages/graph-io/src/graph_io/cli` to `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli`.
- Added the `gwgraph` console script to `graph-wiki-cli` and removed the `cg` console script and CLI package from `graph-io`.
- Moved code-graph CLI tests into `packages/graph-wiki-cli/tests/graph_cli` and removed stale CLI tests from `graph-io`.
- Updated active code, tests, and docs to refer to `gwgraph` instead of `cg`, including schema/error guidance and ignore-file naming.
- Renamed `.cgignore` to `.gwgraphignore` and updated the ignore-loader/tests accordingly.

## Files Modified
- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/`
- `packages/graph-wiki-cli/tests/graph_cli/`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_graph.py`
- `packages/graph-io/pyproject.toml`
- `packages/graph-io/README.md`
- `packages/graph-io/src/graph_io/`
- `packages/graph-io/tests/`
- `.gwgraphignore`

## Verification
- `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/graph_cli -q` — 131 passed, 1 xfailed.
- `uv run --package graph-io pytest packages/graph-io/tests -q` — 394 passed, 1 skipped.
- `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit packages/graph-wiki-cli/tests/graph_cli -q` — 217 passed, 1 xfailed.
- `rg 'graph_io\.cli|\bcg\b|cgignore|\.cgignore|cg update|cg CLI' ...` — no active stale references outside the intentional negative boundary assertion.
