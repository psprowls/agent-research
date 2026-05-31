# S02: CLI package extraction

**Goal:** Extract the Typer CLI surface into a focused packages/graph-wiki-cli workspace package that imports shared command logic from graph_wiki_core, exposes only the gw console script, and has package-local CLI tests proving help, query, and boundary behavior.
**Demo:** `packages/graph-wiki-cli` exposes `gw`, CLI tests import `graph_wiki_cli`, and representative `gw --help` and command help checks pass.

## Must-Haves

- Must-haves:
- packages/graph-wiki-cli is a uv workspace package with distribution name graph-wiki-cli and import namespace graph_wiki_cli.
- The console script owned by the CLI package is exactly gw = graph_wiki_cli.cli:app; no graph-wiki-agent console-script alias is introduced or retained as an active CLI entrypoint.
- CLI implementation imports command logic from graph_wiki_core.commands and direct dependencies are declared honestly, including graph-io if graph_wiki_cli.cli imports graph_io.exit_codes.
- CLI presentation tests live under packages/graph-wiki-cli/tests and import or monkeypatch graph_wiki_cli.cli rather than graph_wiki_agent.cli.
- Representative subprocess checks for gw --help and gw query --help pass through uv run --package graph-wiki-cli.
- Threat Surface (Q3): This slice changes local command packaging and subprocess entrypoints only. There is no new auth surface or network surface. User-controlled CLI arguments still reach existing command implementations, so unresolved-workspace/error-path tests must continue to prove failures return controlled CLI exit codes rather than tracebacks.
- Requirement Impact (Q4): Covers R003 directly and advances R001, R006, and R007. Re-verify CLI launchability, package metadata, query help, import boundary, and package-local tests. Locked decisions D001-D003 remain in force: use graph_wiki_core for shared logic and do not add old import or console aliases; D004 remains in force by not renaming graph-wiki-agent plugin identity.

## Proof Level

- This slice proves: Integration proof at the local packaging boundary: uv must resolve the new workspace package, import graph_wiki_cli.cli, launch the real gw console script, render command help, run CLI package tests, and assert old CLI aliases/namespaces are not active in the new package. Human/UAT is not required.

## Integration Closure

Consumes S01's packages/graph-wiki-core package and graph_wiki_core.commands import contract. Introduces new CLI wiring via packages/graph-wiki-cli/pyproject.toml and the gw console script. Leaves MCP extraction, plugin/runtime shim rewiring, docs updates, obsolete agents layout removal, stale non-CLI test cleanup, and full integration verification to S03-S05.

## Verification

- No runtime observability features are added. Failure visibility is through explicit package-boundary tests, subprocess help checks, import-smoke checks, and controlled CLI error-path tests that expose packaging or launch failures immediately to future agents.

## Tasks

- [x] **T01: Create graph-wiki-cli package and gw entrypoint** `est:1h`
  Why: S02 needs a real CLI package before tests can be relocated or subprocess launchability can be proven. The implementation should be a presentation move over S01's graph_wiki_core.commands surface, not a command-logic fork.
  - Files: `packages/graph-wiki-cli/pyproject.toml`, `packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py`, `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, `agents/graph-wiki-agent/pyproject.toml`
  - Verify: uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"

- [x] **T02: Relocate CLI presentation tests to graph-wiki-cli** `est:1.5h`
  Why: R006 requires tests to live with the package they validate, and S02 must prove the CLI package uses graph_wiki_cli rather than the old graph_wiki_agent presentation namespace.
  - Files: `packages/graph-wiki-cli/tests/conftest.py`, `packages/graph-wiki-cli/tests/unit/test_cli_help.py`, `packages/graph-wiki-cli/tests/unit/test_cli_query.py`, `packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py`, `packages/graph-wiki-cli/tests/unit/test_commands_bootstrap.py`, `packages/graph-wiki-cli/tests/unit/test_commands_graph.py`, `packages/graph-wiki-cli/tests/unit/test_commands_log.py`, `packages/graph-wiki-cli/tests/unit/test_trace_viewer.py`, `agents/graph-wiki-agent/tests/conftest.py`, `agents/graph-wiki-agent/tests/unit/test_cli_help.py`, `agents/graph-wiki-agent/tests/unit/test_cli_query.py`, `agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py`, `agents/graph-wiki-agent/tests/unit/test_commands_bootstrap.py`, `agents/graph-wiki-agent/tests/unit/test_commands_graph.py`, `agents/graph-wiki-agent/tests/unit/test_commands_log.py`, `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py`
  - Verify: uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_help.py packages/graph-wiki-cli/tests/unit/test_cli_query.py

- [x] **T03: Add CLI package boundary and negative-alias tests** `est:45m`
  Why: The package can appear to work while still carrying an old graph-wiki-agent alias or namespace dependency. S02 needs explicit negative tests for decisions D001-D003 and requirement R003.
  - Files: `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`, `packages/graph-wiki-cli/tests/unit/test_cli_query.py`
  - Verify: uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py

- [x] **T04: Sync workspace and prove gw launchability** `est:45m`
  Why: The slice is not done until uv resolves the new workspace package, lockfile state is current, the real gw script launches, and all CLI package tests pass through the package boundary.
  - Files: `uv.lock`, `packages/graph-wiki-cli/pyproject.toml`, `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, `packages/graph-wiki-cli/tests`
  - Verify: uv sync
uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw --help
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw query --help
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py

## Files Likely Touched

- packages/graph-wiki-cli/pyproject.toml
- packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py
- packages/graph-wiki-cli/src/graph_wiki_cli/cli.py
- agents/graph-wiki-agent/pyproject.toml
- packages/graph-wiki-cli/tests/conftest.py
- packages/graph-wiki-cli/tests/unit/test_cli_help.py
- packages/graph-wiki-cli/tests/unit/test_cli_query.py
- packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py
- packages/graph-wiki-cli/tests/unit/test_commands_bootstrap.py
- packages/graph-wiki-cli/tests/unit/test_commands_graph.py
- packages/graph-wiki-cli/tests/unit/test_commands_log.py
- packages/graph-wiki-cli/tests/unit/test_trace_viewer.py
- agents/graph-wiki-agent/tests/conftest.py
- agents/graph-wiki-agent/tests/unit/test_cli_help.py
- agents/graph-wiki-agent/tests/unit/test_cli_query.py
- agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py
- agents/graph-wiki-agent/tests/unit/test_commands_bootstrap.py
- agents/graph-wiki-agent/tests/unit/test_commands_graph.py
- agents/graph-wiki-agent/tests/unit/test_commands_log.py
- agents/graph-wiki-agent/tests/unit/test_trace_viewer.py
- packages/graph-wiki-cli/tests/unit/test_cli_boundary.py
- uv.lock
- packages/graph-wiki-cli/tests
