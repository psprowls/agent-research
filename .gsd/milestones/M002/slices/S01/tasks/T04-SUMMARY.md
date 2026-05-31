---
id: T04
parent: S01
milestone: M002
key_files:
  - packages/graph-wiki-core/tests/conftest.py
  - packages/graph-wiki-core/tests/test_package_boundary.py
  - packages/graph-wiki-core/tests/commands/test_lint_parity.py
  - packages/graph-wiki-core/tests/commands/test_scan_parity.py
  - packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py
  - packages/graph-wiki-core/tests/test_migrate_vault.py
  - packages/graph-wiki-core/tests/unit/test_commands_graph.py
  - packages/graph-wiki-core/tests/unit/__snapshots__/test_commands_graph.ambr
key_decisions:
  - Keep graph-wiki-core tests library-only by adapting command tests to command Typer apps and trimming temporary CLI/MCP presentation assertions.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:14:13.328Z
blocker_discovered: false
---

# T04: Relocated deterministic core-facing graph-wiki tests into graph-wiki-core and added package-boundary assertions for scripts, bytecode, and stale command imports.

**Relocated deterministic core-facing graph-wiki tests into graph-wiki-core and added package-boundary assertions for scripts, bytecode, and stale command imports.**

## What Happened

Created the package-local core test suite under packages/graph-wiki-core/tests by copying the existing command, prompt, top-level, and core unit tests from agents/graph-wiki-agent/tests while excluding CLI-only, MCP-only, stdout guard, live Bedrock, and subprocess presentation checks. Rewrote copied imports and snapshots to use graph_wiki_core, adapted graph command tests to invoke graph_wiki_core.commands.graph.graph_app directly instead of the temporary CLI app, trimmed mixed presentation-only assertions from bootstrap/log/migrate tests, and refreshed the graph query snapshot for the current package attribute shape. Extended the package-boundary test to assert no project scripts, no bytecode artifacts under core source/tests, no stale graph_wiki_agent command imports in graph-wiki-core or eval-harness, and a smoke import of the core query command namespace. Added package-local pytest session cleanup so bytecode boundary checks are deterministic during normal pytest execution.

## Verification

Ran the authoritative package-local verification command `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests`; it passed with 256 tests passed, 7 skipped, and 21 snapshots passed. Ran a post-verification audit confirming no stale graph_wiki_agent, graph_wiki_agent.commands, graph_wiki_core.cli, or graph_wiki_core.mcp references in the copied core test tree and zero bytecode artifacts under packages/graph-wiki-core.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests` | 0 | ✅ pass — 256 passed, 7 skipped, 21 snapshots passed | 10613ms |
| 2 | `python audit via gsd_exec: check packages/graph-wiki-core/tests for stale old namespace/presentation imports and bytecode artifacts` | 0 | ✅ pass — 0 stale old namespace/CLI/MCP references, 38 test files, 0 bytecode artifacts | 52ms |

## Deviations

Trace viewer tests were not relocated because the trace viewer implementation still lives on the temporary graph_wiki_agent CLI presentation surface, and the task explicitly said to leave CLI-only tests for later slices. Mixed CLI/MCP cases embedded in otherwise core command test files were trimmed rather than moved.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-core/tests/conftest.py`
- `packages/graph-wiki-core/tests/test_package_boundary.py`
- `packages/graph-wiki-core/tests/commands/test_lint_parity.py`
- `packages/graph-wiki-core/tests/commands/test_scan_parity.py`
- `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py`
- `packages/graph-wiki-core/tests/test_migrate_vault.py`
- `packages/graph-wiki-core/tests/unit/test_commands_graph.py`
- `packages/graph-wiki-core/tests/unit/__snapshots__/test_commands_graph.ambr`
