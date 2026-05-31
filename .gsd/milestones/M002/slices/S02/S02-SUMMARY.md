---
id: S02
parent: M002
milestone: M002
provides:
  - A resolved graph-wiki-cli workspace package with honest graph_wiki_cli import namespace.
  - The gw console script for downstream docs and runtime shim rewiring in S04.
  - Package-local CLI test suite and boundary tests for S05 full integration verification.
requires:
  - slice: S01
    provides: Consumed graph-wiki-core package and graph_wiki_core.commands import surface.
affects:
  - S04 consumes the gw command for plugin Bedrock shims and docs.
  - S05 consumes the package boundary and CLI tests for full workspace integration verification.
key_files:
  - packages/graph-wiki-cli/pyproject.toml
  - packages/graph-wiki-cli/src/graph_wiki_cli/__init__.py
  - packages/graph-wiki-cli/src/graph_wiki_cli/cli.py
  - packages/graph-wiki-cli/tests/conftest.py
  - packages/graph-wiki-cli/tests/test_cli_package.py
  - packages/graph-wiki-cli/tests/unit/test_cli_boundary.py
  - packages/graph-wiki-cli/tests/unit/test_cli_help.py
  - packages/graph-wiki-cli/tests/unit/test_cli_query.py
  - packages/graph-wiki-cli/tests/unit/test_cli_bootstrap.py
  - packages/graph-wiki-cli/tests/unit/test_commands_bootstrap.py
  - packages/graph-wiki-cli/tests/unit/test_commands_graph.py
  - packages/graph-wiki-cli/tests/unit/test_commands_log.py
  - packages/graph-wiki-cli/tests/unit/test_trace_viewer.py
  - uv.lock
  - agents/graph-wiki-agent/pyproject.toml
key_decisions:
  - graph_wiki_cli.cli is a presentation package over graph_wiki_core.commands, not a fork or shim through graph_wiki_agent.
  - The only active CLI entrypoint from the CLI package is gw = graph_wiki_cli.cli:app.
  - graph_wiki_agent references in graph-wiki-cli tests are permitted only when they are negative boundary assertions.
patterns_established:
  - Package-local CLI tests live under packages/graph-wiki-cli/tests and import graph_wiki_cli directly.
  - Boundary tests assert both positive package metadata/entrypoint behavior and negative absence of stale CLI aliases.
  - CLI closeout verification uses uv package-scoped subprocess commands to prove the installed console-script boundary.
observability_surfaces:
  - No runtime observability surface was added; failure visibility is provided by import smoke checks, subprocess help checks, package-local tests, boundary tests, and controlled CLI error-path tests.
drill_down_paths:
  - .gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T04-SUMMARY.md
  - .gsd/exec/6c54b54a-96da-43a9-b243-3fe51e57dee7.stdout
duration: ""
verification_result: passed
completed_at: 2026-05-31T16:39:05.703Z
blocker_discovered: false
---

# S02: CLI package extraction

**Extracted the graph-wiki Typer CLI into the new graph-wiki-cli workspace package, exposed the real gw console script, relocated CLI tests, and proved package-boundary launchability.**

## What Happened

S02 consumed S01's graph_wiki_core.commands import contract and created a focused packages/graph-wiki-cli workspace package with import namespace graph_wiki_cli. The CLI presentation layer now imports shared command logic from graph_wiki_core rather than the old graph_wiki_agent namespace, and the active console script is exactly gw = graph_wiki_cli.cli:app. CLI presentation tests were moved under packages/graph-wiki-cli/tests, updated to import and monkeypatch graph_wiki_cli.cli plus graph_wiki_core command modules, and obsolete agent-side CLI tests were removed while leaving MCP/plugin tests in the old agent tree for later S03 extraction. Boundary tests now lock the new package metadata and console entrypoint, reject stale graph-wiki-agent CLI aliases, and keep unresolved-workspace/error-path coverage in the query tests so CLI failures remain controlled instead of traceback-driven. The workspace lockfile was synced and final verification proved uv can resolve graph-wiki-cli, import graph_wiki_cli.cli, launch gw and gw query help through the real console script, and pass the full package-local CLI suite.

## Verification

Fresh closeout verification was run through gsd_exec id 6c54b54a-96da-43a9-b243-3fe51e57dee7. `uv sync` exited 0. `uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"` exited 0 and printed `gw`. `NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw --help` exited 0 and rendered the gw command list. `NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw query --help` exited 0 and rendered query options including workspace, json, no-state-gate, quiet, and top-k. `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests` passed 78 tests with 12 snapshots. `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` passed 3 tests. R003 was updated to validated based on this proof.

## Requirements Advanced

- R001 — Advanced the package split by extracting the CLI surface into graph-wiki-cli while consuming graph-wiki-core for shared command logic.
- R006 — Advanced package-colocated testing by moving CLI presentation tests under packages/graph-wiki-cli/tests.
- R007 — Advanced launchability proof with uv sync, import smoke, gw help, query help, and package-local pytest verification.

## Requirements Validated

- R003 — Validated by graph-wiki-cli exposing gw through graph_wiki_cli.cli:app, successful gw and gw query help subprocess checks, and boundary tests rejecting old graph-wiki-agent CLI aliases.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

T02 also moved the seeded_graph_workspace smoke test with the fixture it validates. T04 added explicit classified stale-reference verification after broad grep found only intended negative boundary-test strings. No source edits were needed during closeout.

## Known Limitations

MCP extraction remains in S03. Runtime-facing graph-wiki workflow shims and docs are not yet rewired to gw; that is S04. Obsolete agents layout removal and full workspace integration verification remain S05 responsibilities.

## Follow-ups

S03 should extract graph-wiki-mcp. S04 should update Bedrock workflow shims and current user-facing docs to invoke gw. S05 should remove stale agents layout, clean remaining references, and run full workspace integration verification.

## Files Created/Modified

- `packages/graph-wiki-cli/pyproject.toml` — Defines graph-wiki-cli package metadata, dependencies, and gw console script.
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` — Contains the Typer CLI presentation layer importing shared command logic from graph_wiki_core.
- `packages/graph-wiki-cli/tests` — Holds relocated CLI presentation tests, package smoke tests, and boundary tests.
- `agents/graph-wiki-agent/pyproject.toml` — Removed old active CLI console alias while leaving remaining agent/MCP configuration for later slices.
- `uv.lock` — Updated workspace lockfile state for the new graph-wiki-cli package.
