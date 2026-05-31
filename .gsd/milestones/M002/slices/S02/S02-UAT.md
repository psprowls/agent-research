# S02: CLI package extraction — UAT

**Milestone:** M002
**Written:** 2026-05-31T16:39:05.703Z

## UAT Type
Automated packaging and CLI launchability UAT; no manual human interaction required.

## Preconditions
- Working directory is the repository root.
- The workspace has S01's graph-wiki-core package available.
- Python and uv are available in the development environment.

## Steps
1. Run `uv sync` from the repository root.
2. Run `uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"`.
3. Run `NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw --help`.
4. Run `NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw query --help`.
5. Run `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests`.
6. Run `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`.

## Expected Outcomes
- Step 1 exits 0 and leaves the lockfile/workspace resolution valid.
- Step 2 exits 0 and prints `gw`.
- Step 3 exits 0 and shows the graph-wiki CLI command surface under the `gw` command.
- Step 4 exits 0 and shows the query command help with the expected CLI options.
- Step 5 exits 0 with all graph-wiki-cli package tests passing.
- Step 6 exits 0 and confirms the package boundary rejects stale graph-wiki-agent CLI aliases/import assumptions.

## Edge Cases Covered
- The CLI import path is `graph_wiki_cli.cli`, not `graph_wiki_agent.cli`.
- The console script is `gw`; no old graph-wiki-agent CLI alias is active in the new package.
- Query help and unresolved-workspace/error-path coverage continue to exercise controlled CLI failure behavior rather than tracebacks.

## Operational Readiness
- Health signal: `gw --help`, `gw query --help`, import smoke, and package-local tests provide fast launchability signals.
- Failure signal: boundary tests and negative query-path tests fail loudly if stale aliases, wrong imports, or uncontrolled CLI errors return.
- Recovery procedure: rerun `uv sync`, then the import smoke and focused `test_cli_boundary.py`; if those pass, rerun the full package-local CLI suite.
- Monitoring gaps: no runtime monitoring was added because this slice only changes local packaging and subprocess entrypoints.
