# Quick Task: I want to make some more changes to the `gw` cli in `graph-wiki-cli`.  Currently `graph-io` contains the Typer interface (and the`cg` cli tool.  I would like to move all of the Typer interface into `graph-wiki-cli` and remove it from `graph-io` along withremoving the `cg` tool from `graph-io`.  As part of this I want to update references to `cg` throught the code to reference `gwgraph`, etc.  There may also be changes to the docs as part of this, but you will need to verify that.

**Date:** 2026-05-31
**Branch:** main

## What Changed
- Moved the `gw` Typer CLI ownership into `graph-wiki-cli` and removed the `cg` console-script from `graph-io`.
- Updated `graph-io` package metadata/docs to describe it as core library code without a CLI surface.
- Added a boundary test to ensure `graph-io` no longer advertises `cg`.

## Files Modified
- `packages/graph-io/pyproject.toml`
- `packages/graph-io/README.md`
- `packages/graph-io/src/graph_io/__init__.py`
- `packages/graph-io/src/graph_io/cli/__init__.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`

## Verification
- Not yet run.
