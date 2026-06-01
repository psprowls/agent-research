# Quick Task: I want to make some more changes to the `gw` cli in `graph-wiki-cli`.  Currently `graph-io` contains the Typer interface (and the`cg` cli tool.  I would like to move all of the Typer interface into `graph-wiki-cli` and remove it from `graph-io` along withremoving the `cg` tool from `graph-io`.  As part of this I want to update references to `cg` throught the code to reference `gw graph`, etc.  There may also be changes to the docs as part of this, but you will need to verify that.

**Date:** 2026-05-31
**Branch:** main

## What Changed
- Moved the legacy code-graph CLI implementation from `packages/graph-io/src/graph_io/cli` to `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli`.
- Reworked the moved graph command surface into a native Typer subapp mounted as `gw graph ...`; removed the argparse parser/dispatch layer from `graph-wiki-cli`.
- Removed standalone code-graph executables (`cg` and the mistakenly added `gwgraph`); `graph-wiki-cli` exposes only the unified `gw` executable.
- Moved code-graph CLI tests into `packages/graph-wiki-cli/tests/graph_cli`, updated them away from argparse fixtures, and removed stale CLI tests from `graph-io`.
- Updated active code, tests, and docs to refer to `gw graph` instead of `cg`/`gwgraph`, including schema/error guidance.
- Renamed `.cgignore` to `.graphignore` and updated the ignore-loader/tests accordingly.
- Recorded the CLI architecture decision as D005.

## Files Modified
- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/`
- `packages/graph-wiki-cli/tests/graph_cli/`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_graph.py`
- `packages/graph-io/pyproject.toml`
- `packages/graph-io/README.md`
- `packages/graph-io/src/graph_io/`
- `packages/graph-io/tests/`
- `.graphignore`
- `.gsd/DECISIONS.md`

## Verification
- `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit packages/graph-wiki-cli/tests/graph_cli -q` — 196 passed, 1 xfailed.
- `uv run --package graph-io pytest packages/graph-io/tests -q` — 394 passed, 1 skipped.
- `rg 'argparse|gwgraph|gw graphignore|\.gwgraphignore|\bcg\b|graph_io\.cli|graph_cli_main|_SUBCOMMANDS' ...` — no active stale references outside intentional negative boundary assertions.
