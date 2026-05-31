---
id: T01
parent: S02
milestone: M002
key_files:
  - packages/graph-wiki-cli/pyproject.toml
  - packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py
  - packages/graph-wiki-cli/src/graph_wiki_cli/cli.py
  - packages/graph-wiki-cli/tests/test_cli_package.py
  - agents/graph-wiki-agent/pyproject.toml
key_decisions:
  - graph_wiki_cli.cli remains a presentation package that imports shared command logic from graph_wiki_core.commands rather than routing through graph_wiki_agent.
  - The active CLI script is gw from graph-wiki-cli; graph-wiki-agent retains only graph-wiki-mcp for the planned S03 extraction.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:26:55.889Z
blocker_discovered: false
---

# T01: Created the focused graph-wiki-cli workspace package with the gw Typer entrypoint and removed the old graph-wiki-agent CLI console alias.

**Created the focused graph-wiki-cli workspace package with the gw Typer entrypoint and removed the old graph-wiki-agent CLI console alias.**

## What Happened

Added packages/graph-wiki-cli as a uv workspace member via the existing packages/* glob, with uv_build metadata, pytest importlib mode, honest direct dependencies for graph_wiki_cli.cli imports, and the gw console script pointing at graph_wiki_cli.cli:app. Copied the current Typer CLI implementation into graph_wiki_cli.cli while updating package-facing metadata so the app name is gw, help text describes gw, and version lookup/output use graph-wiki-cli/gw. The CLI continues to import shared command behavior from graph_wiki_core.commands and directly imports graph_io.exit_codes for ingest boundary exit behavior. Removed the graph-wiki-agent console script from agents/graph-wiki-agent while preserving graph-wiki-mcp for the later MCP extraction. Added package-local smoke tests for the new app name and version command.

## Verification

Verified the required import/name command returns gw. Ran the graph-wiki-cli package tests successfully. Smoke-checked the gw console help through uv and confirmed the old graph-wiki-agent console command no longer launches when targeting graph-wiki-agent. Ran a final boundary check confirming new files exist, the old console alias is absent, and graph-wiki-mcp remains present.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"` | 0 | ✅ pass | 1649ms |
| 2 | `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests` | 0 | ✅ pass | 1972ms |
| 3 | `uv run --package graph-wiki-cli gw --help >/tmp/gw-help.txt && uv run --package graph-wiki-agent graph-wiki-agent --help (expected failure)` | 0 | ✅ pass | 1074ms |
| 4 | `python boundary/file existence check plus rg for old graph_wiki_agent.cli or graph-wiki-agent script references in new package` | 0 | ✅ pass | 75ms |

## Deviations

Added a minimal package-local test file in addition to the expected output files to satisfy the execution rule requiring tests for new behavior.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/tests/test_cli_package.py`
- `agents/graph-wiki-agent/pyproject.toml`
