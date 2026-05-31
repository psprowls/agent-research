# S01: Core package move and rename — UAT

**Milestone:** M002
**Written:** 2026-05-31T16:17:59.402Z

## UAT Type

Contract and package-integration UAT for the S01 library-core boundary.

## Preconditions

- The repository is checked out at the S01 closeout state.
- `uv` is available.
- No AWS credentials are required; this UAT uses import, package metadata, deterministic tests, and help-rendering checks only.

## Steps

1. Run `uv sync` from the workspace root.
2. Smoke-test the core command and prompt imports:
   - `uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query"`
   - `uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.scan"`
   - `uv run --package graph-wiki-core python -c "import graph_wiki_core.prompts.scanner"`
3. Run the package-local core test suite: `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests`.
4. Run the selected eval-harness consumer tests: `uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py`.
5. Run the temporary presentation help smoke: `uv run --package graph-wiki-agent graph-wiki-agent --help`.

## Expected Outcomes

- `packages/graph-wiki-core` is a uv workspace package named `graph-wiki-core`.
- Core imports resolve through `graph_wiki_core`, not `graph_wiki_agent`.
- The core package has no `[project.scripts]` executable surface.
- Core package tests pass and include package-boundary assertions for stale command imports and accidental presentation leakage.
- Eval-harness tests pass while importing command helpers from `graph_wiki_core.commands`.
- The temporary `graph-wiki-agent` help command exits 0, proving the existing presentation surface still compiles while later slices extract CLI/MCP packages.

## Edge Cases Checked

- Bytecode/cache artifacts are not accepted under the core source/test tree by boundary tests and audit checks.
- CLI-only and MCP-only tests are intentionally excluded from the core package; later slices own those presentation contracts.
- Intentional legacy/empty-scope skips remain visible in pytest output but do not mask failures in the core migration contract.
