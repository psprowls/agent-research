---
estimated_steps: 10
estimated_files: 16
skills_used: []
---

# T02: Relocate CLI presentation tests to graph-wiki-cli

Why: R006 requires tests to live with the package they validate, and S02 must prove the CLI package uses graph_wiki_cli rather than the old graph_wiki_agent presentation namespace.

Expected executor skills: python-testing-patterns, uv-package-manager.

Do:
1. Create packages/graph-wiki-cli/tests with a package-local conftest containing only fixtures required by moved CLI tests. Reuse the existing seeded_graph_workspace fixture if graph subcommand CliRunner tests need it, but avoid dragging unrelated MCP/core fixtures into the CLI package.
2. Move/update CLI-owned tests from agents/graph-wiki-agent/tests/unit, starting with test_cli_help.py and test_cli_query.py. Also move CLI presentation tests that import graph_wiki_agent.cli, such as test_cli_bootstrap.py, test_commands_bootstrap.py, test_commands_graph.py, test_commands_log.py if their assertions exercise Typer presentation rather than MCP internals, and test_trace_viewer.py.
3. Update subprocess invocations from uv run --package graph-wiki-agent graph-wiki-agent ... to uv run --package graph-wiki-cli gw .... Keep the NO_COLOR, TERM=dumb, and COLUMNS=200 plain-help environment.
4. Update imports and monkeypatch targets from graph_wiki_agent.cli to graph_wiki_cli.cli. Update helper imports such as QueryResult to graph_wiki_core.commands.query.
5. Update assertions and docstrings that describe the command-facing package/script name to gw or graph-wiki-cli. Keep graph-wiki-agent only when a test is intentionally asserting plugin identity or a fixture manifest identity, which should generally remain outside this CLI package until S04/S05.
6. Remove or stop relying on the old copies of moved CLI tests under agents/graph-wiki-agent/tests so the authoritative CLI tests are package-local.

Done when: the relocated CLI test subset passes when run against packages/graph-wiki-cli/tests and no moved test imports graph_wiki_agent.cli.

## Inputs

- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `agents/graph-wiki-agent/tests/conftest.py`
- `agents/graph-wiki-agent/tests/unit/test_cli_help.py`
- `agents/graph-wiki-agent/tests/unit/test_cli_query.py`
- `agents/graph-wiki-agent/tests/unit/test_cli_bootstrap.py`
- `agents/graph-wiki-agent/tests/unit/test_commands_bootstrap.py`
- `agents/graph-wiki-agent/tests/unit/test_commands_graph.py`
- `agents/graph-wiki-agent/tests/unit/test_commands_log.py`
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py`
- `packages/graph-wiki-core/src/graph_wiki_core/commands`

## Expected Output

- `packages/graph-wiki-cli/tests/conftest.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_help.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_bootstrap.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_graph.py`
- `packages/graph-wiki-cli/tests/unit/test_commands_log.py`
- `packages/graph-wiki-cli/tests/unit/test_trace_viewer.py`
- `agents/graph-wiki-agent/tests/conftest.py`

## Verification

uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_help.py packages/graph-wiki-cli/tests/unit/test_cli_query.py

## Observability Impact

Improves diagnostic locality: failures in CLI presentation now point at packages/graph-wiki-cli/tests instead of the obsolete agent test tree.
