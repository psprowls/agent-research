# S01: Core package move and rename

**Goal:** Create a library-only graph-wiki-core workspace package with import namespace graph_wiki_core, move the shared command/prompt/runtime implementation into it, and rewire temporary consumers so core imports and targeted tests prove the new package boundary before CLI and MCP extraction.
**Demo:** `packages/graph-wiki-core` exists as a library-only workspace member, imports use `graph_wiki_core`, and shared command tests prove core still works.

## Must-Haves

- `packages/graph-wiki-core` exists as a uv workspace member named `graph-wiki-core` with no `[project.scripts]`.
- Shared implementation modules live under `packages/graph-wiki-core/src/graph_wiki_core/`: `commands/`, `prompts/`, `graph_tools.py`, `config.py`, and `uri_slug.py`; `__pycache__` files are not copied.
- Moved core source imports use `graph_wiki_core`, not `graph_wiki_agent`.
- The temporary `graph-wiki-agent` presentation package depends on `graph-wiki-core` and its CLI/MCP surfaces import command logic from `graph_wiki_core` without adding backward-compatible command shims.
- `eval-harness` depends on `graph-wiki-core` and active command imports use `graph_wiki_core.commands`.
- Core-facing tests are colocated under `packages/graph-wiki-core/tests` and include boundary assertions for imports and the absence of executable scripts in the core package.
- Targeted workspace verification passes: `uv sync`, core import smoke, core tests, selected eval-harness tests, and temporary presentation help smoke.

## Proof Level

- This slice proves: Contract plus package-integration proof. This slice does not claim the final user-facing `gw` or `graph-wiki-mcp` surfaces; those are owned by later slices. It proves the shared command contract is importable from `graph_wiki_core` and that existing temporary consumers compile against it.

## Integration Closure

Upstream surfaces consumed: existing monolith source under `agents/graph-wiki-agent/src/graph_wiki_agent`, existing graph-wiki-agent tests, root uv workspace, and eval-harness package metadata/imports. New wiring introduced: `graph-wiki-core` package, temporary `graph-wiki-agent` dependency on it, and eval-harness dependency on it. Remaining milestone work: S02 extracts the CLI into `graph-wiki-cli` and exposes `gw`; S03 extracts FastMCP into `graph-wiki-mcp`; S04 rewires docs and plugin shims; S05 removes the obsolete agents layout and runs full integration verification.

## Verification

- No runtime observability is changed. Failure visibility for future agents comes from package-local pytest failures, import-smoke failures, and explicit boundary tests that identify stale `graph_wiki_agent` command imports or accidental core console scripts.

## Tasks

- [x] **T01: Create graph-wiki-core package and migrate shared source** `est:2h`
  Expected executor skills: `uv-package-manager` and `python-testing-patterns`.
  - Files: `packages/graph-wiki-core/pyproject.toml`, `packages/graph-wiki-core/src/graph_wiki_core`, `packages/graph-wiki-core/src/graph_wiki_core/__init__.py`, `packages/graph-wiki-core/src/graph_wiki_core/commands`, `packages/graph-wiki-core/src/graph_wiki_core/prompts`, `packages/graph-wiki-core/src/graph_wiki_core/graph_tools.py`, `packages/graph-wiki-core/src/graph_wiki_core/config.py`, `packages/graph-wiki-core/src/graph_wiki_core/uri_slug.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/commands`, `agents/graph-wiki-agent/src/graph_wiki_agent/prompts`, `agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/config.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py`
  - Verify: uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query"

- [ ] **T02: Rewire temporary graph-wiki-agent presentation consumers** `est:1h 30m`
  Expected executor skills: `uv-package-manager`.
  - Files: `agents/graph-wiki-agent/pyproject.toml`, `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/__init__.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/commands`, `agents/graph-wiki-agent/src/graph_wiki_agent/prompts`
  - Verify: uv run --package graph-wiki-agent graph-wiki-agent --help

- [ ] **T03: Point eval-harness at graph-wiki-core** `est:1h`
  Expected executor skills: `uv-package-manager` and `python-testing-patterns`.
  - Files: `packages/eval-harness/pyproject.toml`, `packages/eval-harness/src/eval_harness/structural.py`, `packages/eval-harness/src/eval_harness/sweep.py`, `packages/eval-harness/src/eval_harness/divergence/synthesizer.py`, `packages/eval-harness/src/eval_harness/divergence/code_reader.py`, `packages/eval-harness/tests/eval_helpers.py`, `packages/eval-harness/tests/test_structural.py`, `packages/eval-harness/tests/test_sweep.py`, `packages/eval-harness/tests/test_role_sweep.py`
  - Verify: uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py

- [ ] **T04: Relocate core-facing tests and add package boundary assertions** `est:2h 30m`
  Expected executor skills: `python-testing-patterns`.
  - Files: `packages/graph-wiki-core/tests`, `packages/graph-wiki-core/pyproject.toml`, `agents/graph-wiki-agent/tests/commands`, `agents/graph-wiki-agent/tests/prompts`, `agents/graph-wiki-agent/tests/conftest.py`, `agents/graph-wiki-agent/tests/test_command_overrides.py`, `agents/graph-wiki-agent/tests/test_ingest_trace_unit.py`, `agents/graph-wiki-agent/tests/test_migrate_vault.py`, `agents/graph-wiki-agent/tests/test_propose_domains.py`, `agents/graph-wiki-agent/tests/test_query_graph_tools.py`, `agents/graph-wiki-agent/tests/test_query_trace_unit.py`, `agents/graph-wiki-agent/tests/unit`
  - Verify: uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests

- [ ] **T05: Run S01 workspace verification and clean missed active references** `est:1h`
  Expected executor skills: `verify-before-complete`, `uv-package-manager`, and `python-testing-patterns`.
  - Files: `uv.lock`, `packages/graph-wiki-core`, `packages/eval-harness`, `agents/graph-wiki-agent/pyproject.toml`, `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`, `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`
  - Verify: uv sync && uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query" && uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.scan" && uv run --package graph-wiki-core python -c "import graph_wiki_core.prompts.scanner" && uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests && uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py && uv run --package graph-wiki-agent graph-wiki-agent --help

## Files Likely Touched

- packages/graph-wiki-core/pyproject.toml
- packages/graph-wiki-core/src/graph_wiki_core
- packages/graph-wiki-core/src/graph_wiki_core/__init__.py
- packages/graph-wiki-core/src/graph_wiki_core/commands
- packages/graph-wiki-core/src/graph_wiki_core/prompts
- packages/graph-wiki-core/src/graph_wiki_core/graph_tools.py
- packages/graph-wiki-core/src/graph_wiki_core/config.py
- packages/graph-wiki-core/src/graph_wiki_core/uri_slug.py
- agents/graph-wiki-agent/src/graph_wiki_agent/commands
- agents/graph-wiki-agent/src/graph_wiki_agent/prompts
- agents/graph-wiki-agent/src/graph_wiki_agent/graph_tools.py
- agents/graph-wiki-agent/src/graph_wiki_agent/config.py
- agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py
- agents/graph-wiki-agent/pyproject.toml
- agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
- agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
- agents/graph-wiki-agent/src/graph_wiki_agent/__init__.py
- packages/eval-harness/pyproject.toml
- packages/eval-harness/src/eval_harness/structural.py
- packages/eval-harness/src/eval_harness/sweep.py
- packages/eval-harness/src/eval_harness/divergence/synthesizer.py
- packages/eval-harness/src/eval_harness/divergence/code_reader.py
- packages/eval-harness/tests/eval_helpers.py
- packages/eval-harness/tests/test_structural.py
- packages/eval-harness/tests/test_sweep.py
- packages/eval-harness/tests/test_role_sweep.py
- packages/graph-wiki-core/tests
- agents/graph-wiki-agent/tests/commands
- agents/graph-wiki-agent/tests/prompts
- agents/graph-wiki-agent/tests/conftest.py
- agents/graph-wiki-agent/tests/test_command_overrides.py
- agents/graph-wiki-agent/tests/test_ingest_trace_unit.py
- agents/graph-wiki-agent/tests/test_migrate_vault.py
- agents/graph-wiki-agent/tests/test_propose_domains.py
- agents/graph-wiki-agent/tests/test_query_graph_tools.py
- agents/graph-wiki-agent/tests/test_query_trace_unit.py
- agents/graph-wiki-agent/tests/unit
- uv.lock
- packages/graph-wiki-core
- packages/eval-harness
