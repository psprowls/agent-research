---
estimated_steps: 14
estimated_files: 6
skills_used: []
---

# T05: Run S01 workspace verification and clean missed active references

Expected executor skills: `verify-before-complete`, `uv-package-manager`, and `python-testing-patterns`.

Why: This migration changes package metadata, imports, test ownership, and temporary consumers. The slice is not complete until the workspace resolves and targeted package tests prove the new boundary. This task is intentionally verification-heavy and should only make small follow-up edits for missed active references discovered by the commands.

Do:
1. Run `uv sync` after metadata changes so the lockfile/workspace environment includes `graph-wiki-core`.
2. Run the core import smoke for representative modules: `graph_wiki_core.commands.query`, `graph_wiki_core.commands.scan`, and `graph_wiki_core.prompts.scanner`.
3. Run all package-local core tests.
4. Run selected eval-harness tests that import shared command logic.
5. Run temporary `graph-wiki-agent --help` smoke to confirm the old presentation package still compiles against core until S02/S03.
6. If any command identifies a missed active stale import or metadata omission, make the smallest code/test/pyproject fix and rerun the relevant check.
7. Do not chase historical prose, fixture vault text, docs, plugin identities, final agents-layout removal, or CLI/MCP package extraction; those are downstream slices.

Requirement Impact (Q4): verifies R002 directly and provides supporting proof for R001, R006, and R007. Decisions D001-D004 remain locked: renamed core namespace, separated presentation surfaces, no compatibility shims, plugin identity unchanged.
Failure Modes (Q5): uv sync can fail on missing workspace sources; package tests can fail on incomplete path rewrites; temporary help smoke can fail if presentation imports still target removed modules; eval-harness can fail if dependency metadata and imports disagree.
Negative Tests (Q7): package-boundary tests from T04 must fail on accidental scripts, stale active imports, or copied bytecode; no external Bedrock credentials are required.
Done when: all listed verification commands pass in the current workspace and any active stale references in S01-owned packages are either removed or explicitly deferred because they belong to CLI/MCP/docs slices.

## Inputs

- `pyproject.toml`
- `uv.lock`
- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-core/src/graph_wiki_core`
- `packages/graph-wiki-core/tests`
- `packages/eval-harness/pyproject.toml`
- `packages/eval-harness/src/eval_harness`
- `packages/eval-harness/tests`
- `agents/graph-wiki-agent/pyproject.toml`
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`

## Expected Output

- `uv.lock`

## Verification

uv sync && uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.query" && uv run --package graph-wiki-core python -c "import graph_wiki_core.commands.scan" && uv run --package graph-wiki-core python -c "import graph_wiki_core.prompts.scanner" && uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests && uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py && uv run --package graph-wiki-agent graph-wiki-agent --help

## Observability Impact

Final verification produces current command evidence and narrows any failure to uv metadata, core imports/tests, eval-harness consumer wiring, or temporary presentation smoke.
