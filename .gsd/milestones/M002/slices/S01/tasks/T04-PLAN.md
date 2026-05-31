---
estimated_steps: 13
estimated_files: 12
skills_used: []
---

# T04: Relocate core-facing tests and add package boundary assertions

Expected executor skills: `python-testing-patterns`.

Why: R006 is finally owned by S05, but S01 should establish the core package verification boundary now. Executors need package-local tests that prove shared commands, prompts, config, graph tools, and URI helpers still work under the new namespace.

Do:
1. Create `packages/graph-wiki-core/tests/` and move or copy core-facing tests from `agents/graph-wiki-agent/tests/` into it. Prioritize: `commands/`, `prompts/`, `test_command_overrides.py`, `test_ingest_trace_unit.py`, `test_migrate_vault.py`, `test_propose_domains.py`, `test_query_graph_tools.py`, `test_query_trace_unit.py`, and unit tests for command modules, `config.py`, `graph_tools.py`, query/search/result behavior, scan behavior, trace viewer, and `uri_slug.py`.
2. Leave CLI-only tests (`test_cli_*`), MCP-only tests (`test_mcp_*`, `test_stdout_guard.py`, MCP integration tests), and Bedrock/subprocess integration tests for later slices unless they are needed as temporary smoke checks.
3. Update imports, monkeypatch paths, snapshot/provenance path assertions, and conftest fixtures to use `graph_wiki_core` and `packages/graph-wiki-core/src/graph_wiki_core` where executable assertions depend on paths.
4. Add a small package-boundary test under `packages/graph-wiki-core/tests/` that asserts core has no `[project.scripts]`, no copied `__pycache__` under core source/tests, and no active `graph_wiki_agent.commands` imports in `packages/graph-wiki-core` or `packages/eval-harness`.
5. Keep tests deterministic and skip/avoid cases that require real Bedrock credentials, live MCP stdio, or integration-only subprocess flows.

Requirement Impact (Q4): directly supports R002 and begins R006 by making core tests colocated. Re-verify command contracts, prompt provenance, import namespace, and package metadata.
Failure Modes (Q5): if tests are copied without fixture path updates they may pass against old files or fail due to missing fixtures; if CLI/MCP tests are moved too early the slice expands into S02/S03; if boundary assertions read ignored planning directories they become noisy. Do not read `.gsd/`, `.planning/`, `.audits/`, or other gitignored planning paths from tests.
Load Profile (Q6): tests should remain package-local and deterministic; 10x test count pressure should hit pytest runtime rather than external services because no Bedrock/network tests are included.
Negative Tests (Q7): boundary assertions cover stale imports, accidental scripts, and copied bytecode; command tests cover malformed/empty inputs already present in the old core test suite.
Done when: `packages/graph-wiki-core/tests` is the authoritative S01 core test target and fails loudly for stale old namespace usage.

## Inputs

- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-core/src/graph_wiki_core`
- `agents/graph-wiki-agent/tests/commands`
- `agents/graph-wiki-agent/tests/prompts`
- `agents/graph-wiki-agent/tests/conftest.py`
- `agents/graph-wiki-agent/tests/test_command_overrides.py`
- `agents/graph-wiki-agent/tests/test_ingest_trace_unit.py`
- `agents/graph-wiki-agent/tests/test_migrate_vault.py`
- `agents/graph-wiki-agent/tests/test_propose_domains.py`
- `agents/graph-wiki-agent/tests/test_query_graph_tools.py`
- `agents/graph-wiki-agent/tests/test_query_trace_unit.py`
- `agents/graph-wiki-agent/tests/unit`

## Expected Output

- `packages/graph-wiki-core/tests`

## Verification

uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests

## Observability Impact

Boundary tests create durable failure signals for stale imports, accidental core scripts, and copied bytecode artifacts.
