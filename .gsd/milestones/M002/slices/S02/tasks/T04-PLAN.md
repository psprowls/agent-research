---
estimated_steps: 10
estimated_files: 4
skills_used: []
---

# T04: Sync workspace and prove gw launchability

Why: The slice is not done until uv resolves the new workspace package, lockfile state is current, the real gw script launches, and all CLI package tests pass through the package boundary.

Expected executor skills: uv-package-manager, verify-before-complete.

Do:
1. Run uv sync so the workspace and uv.lock know about graph-wiki-cli and its script/dependencies.
2. Run an import smoke for graph_wiki_cli.cli and confirm the Typer app name is gw.
3. Run real subprocess help checks for gw --help and gw query --help through uv run --package graph-wiki-cli, using the plain-help environment to avoid ANSI-sensitive false failures.
4. Run the full packages/graph-wiki-cli test suite.
5. Run a final stale-reference check scoped to packages/graph-wiki-cli. If the check finds graph_wiki_agent or graph-wiki-agent, either remove the stale reference or document why it is plugin identity and belongs in a later slice; command-facing help, imports, scripts, and assertions must be current.

Failure Modes (Q5): uv resolution errors mean pyproject dependencies/sources are incomplete; import errors mean namespace or dependency wiring is wrong; help failures mean console-script metadata or Typer importability is wrong; stale-reference failures mean the package split is incomplete.

Done when: all slice verification commands pass and uv.lock reflects the new package resolution.

## Inputs

- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/tests/conftest.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_help.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- `agents/graph-wiki-agent/pyproject.toml`
- `pyproject.toml`

## Expected Output

- `uv.lock`

## Verification

uv sync
uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw --help
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw query --help
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py

## Observability Impact

Provides the closeout evidence future agents need: workspace sync, import smoke, real console-script help, and package-local pytest results.
