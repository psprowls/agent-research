---
estimated_steps: 10
estimated_files: 2
skills_used: []
---

# T03: Add CLI package boundary and negative-alias tests

Why: The package can appear to work while still carrying an old graph-wiki-agent alias or namespace dependency. S02 needs explicit negative tests for decisions D001-D003 and requirement R003.

Expected executor skills: python-testing-patterns, uv-package-manager.

Do:
1. Add a package-local boundary test file under packages/graph-wiki-cli/tests/unit that asserts the graph-wiki-cli distribution is importable and exposes a gw console script pointing at graph_wiki_cli.cli:app.
2. Assert the graph-wiki-cli distribution does not expose graph-wiki-agent as a console script.
3. Assert graph_wiki_cli.cli imports and has a Typer app named gw.
4. Assert the CLI module source or module object uses graph_wiki_core command imports and does not require graph_wiki_agent.cli.
5. Add a negative command test for an unresolved workspace/query path if not already covered by the relocated tests, preserving the controlled exit-code/error-message behavior instead of traceback leakage.

Negative Tests (Q7): verify no old console alias, no old CLI import dependency, and controlled failure for invalid workspace input.

Done when: the boundary tests fail on stale aliases/shims and pass with the new package-only CLI surface.

## Inputs

- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py`

## Expected Output

- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py`

## Verification

uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py

## Observability Impact

Adds executable diagnostics for stale alias/import regressions, making incomplete package extraction visible through one focused pytest file.
