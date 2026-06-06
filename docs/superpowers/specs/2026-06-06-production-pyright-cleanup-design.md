# Design: Production Pyright Cleanup

**Date:** 2026-06-06
**Status:** Design approved; waiting for user review before implementation planning
**Branch:** `pyright-fixes`
**Topic:** Add a production-source pyright gate and clean the production diagnostics while excluding tests and fixtures from CLI and VS Code checking.

## Goal

Make pyright useful as a daily production-source signal for the Graph Wiki monorepo.

The first target is not repo-wide static typing. Tests, fixtures, generated workspace artifacts, virtualenvs, and worktree internals should be excluded from pyright so the command-line run and VS Code/Pylance show the same production-focused diagnostics.

## Baseline

The initial full command was:

```bash
pyright packages tests plugins --pythonpath .venv/bin/python --outputjson
```

It reported:

- 455 files analyzed
- 565 errors
- 8 warnings
- 301 diagnostics in tests
- 268 diagnostics in source

The approved production-source command shape was:

```bash
pyright packages/*/src plugins/graph-wiki/skills/graph-wiki/scripts --pythonpath .venv/bin/python --outputjson
```

It reported:

- 190 files analyzed
- 269 errors
- 0 warnings

The production-source diagnostics were concentrated in:

- `graph-wiki-cli`: 148 diagnostics, mostly argparse namespace handlers typed as `object`
- `graph-wiki-core`: 46 diagnostics, mostly guarded Bedrock imports and argument types
- `graph-io`: 42 diagnostics, mostly graph record list/tuple contract mismatches
- `wiki-io`: 23 diagnostics, including frontmatter/path typing and possibly unbound values
- `eval-harness`: 7 diagnostics
- `source-parser`: 1 diagnostic
- `graph-wiki-mcp`: 1 diagnostic
- Graph Wiki plugin scripts: 1 diagnostic

## Locked Decisions

1. **Use a production-source pyright gate first.** Do not make tests and fixtures part of the initial cleanup.
2. **Commit pyright configuration.** Running `pyright` from the repo root should use the production-source target without requiring a long command.
3. **Align VS Code with CLI behavior.** Add editor settings so Pylance/Pyright excludes tests, fixtures, worktrees, virtualenvs, and generated workspace artifacts in the same spirit as the CLI config.
4. **Treat plugin scripts as production-like.** `plugins/graph-wiki/skills/graph-wiki/scripts` remains in scope because these scripts are live standalone plugin surfaces.
5. **Prefer truthful type models over suppressions.** Use `cast()` or `# type: ignore` only for checked third-party stub limitations or unavoidable dynamic seams.
6. **Do not change runtime behavior just to satisfy pyright.** If pyright reveals a real ambiguity, add or adjust tests and fix the behavior deliberately.

## Scope

### In Scope

- Add `pyrightconfig.json` at the repo root.
- Add or update `.vscode/settings.json` so VS Code/Pylance uses the same production-source intent.
- Include package source under `packages/*/src`.
- Include live Graph Wiki plugin scripts under `plugins/graph-wiki/skills/graph-wiki/scripts`.
- Exclude:
  - `**/tests/**`
  - `**/fixtures/**`
  - `.venv/**`
  - `.worktrees/**`
  - `.git/**`
  - `.hypothesis/**`
  - `.claude/**`
  - `.gsd/**`
  - `.agents/**`
  - `graph-wiki/**`
  - build and cache directories
- Fix production-source pyright diagnostics until `pyright` reports zero errors.
- Run package tests for every package whose production code changes.

### Out Of Scope

- Making tests pyright-clean.
- Making sample monorepo fixtures pyright-clean.
- Adding a repo-wide strict typing gate.
- Adding migrations or schema compatibility code.
- Reworking CLI behavior, output shapes, or command names.
- Refactoring unrelated graph/wiki/core behavior outside the diagnostic clusters.

## Fix Order

### 1. Tooling Gate

Add `pyrightconfig.json` first so every subsequent run uses the approved production-source target.

The config should:

- use the worktree `.venv` via `venvPath` and `venv`
- set the Python version to the repo runtime target
- include production source and plugin scripts
- exclude tests, fixtures, generated workspace artifacts, worktrees, virtualenvs, and caches
- start with pyright's standard type checking mode unless a specific stricter rule is needed to preserve the current diagnostic signal

Add `.vscode/settings.json` with matching analysis settings. Preserve the existing `.vscode/launch.json`.

### 2. CLI Argparse Namespace Typing

Most `graph-wiki-cli` errors come from command handlers shaped like:

```python
def run(args: object) -> int:
    ...
    args.workspace
```

Fix this as a CLI contract problem, not as dozens of local ignores.

Use small `Protocol` types for command namespace shapes. Prefer shared protocols for repeated argument groups such as:

- workspace and format
- workspace, name, depth, and format
- workspace and repo
- describe/list command selectors

The handlers should keep their runtime signature and behavior while making the expected argparse attributes explicit to pyright.

### 3. Graph Record Contract Mismatches

`graph-io` repeatedly builds mutable `list[GraphNode]` and `list[GraphEdge]` collections, then passes them to `GraphRecords`, whose fields currently expect tuples.

Inspect the `GraphRecords` dataclass and its consumers before choosing the fix:

- If `GraphRecords` is meant to be immutable at the boundary, convert lists to tuples at construction sites.
- If consumers only require iteration, consider loosening the field type to `Sequence[GraphNode]` and `Sequence[GraphEdge]`.

Do not silently change upsert behavior or record ordering. Keep graph output stable.

### 4. Guarded Bedrock Imports

`graph-wiki-core` intentionally guards Bedrock-dependent imports so non-narrated/plugin paths can run without the Bedrock stack installed.

Preserve that behavior while making static narrowing explicit. Candidate fixes:

- narrow after `None` checks into local non-optional aliases
- use helper functions that return non-optional `make_llm`, `SubagentPool`, and `TaskResult` symbols after the guard
- use `TYPE_CHECKING` imports for annotations where runtime imports must remain guarded

Do not construct LangChain or Bedrock clients outside `model_adapter.make_llm(role)`.

### 5. Remaining Source Diagnostics

Clean the rest by category:

- real optional `Path` and string values in `eval-harness` and `graph-io`
- `frontmatter.load(Path)` stub mismatches in `wiki-io`
- possibly unbound `log_path` in `wiki_io.append_log`
- typed-dict or dict access issues in graph clustering/rendering helpers
- the single `source-parser`, `graph-wiki-mcp`, and plugin-script issues

These should be small targeted fixes after the high-volume categories are gone.

## Verification

Run `pyright` from the worktree root after each cluster.

Run scoped tests for every touched package:

- CLI changes: `uv run --package graph-wiki-cli pytest -m "not integration"`
- Graph projection changes: `uv run --package graph-io pytest`
- Core scan/Bedrock guard changes: focused `graph-wiki-core` tests first, then `uv run --package graph-wiki-core pytest`
- Wiki IO changes: `uv run --package wiki-io pytest`
- Eval harness changes: `uv run --package eval-harness pytest`
- MCP changes: `uv run --package graph-wiki-mcp pytest`
- Source parser changes: `uv run --package source-parser pytest`

At the end, run:

```bash
pyright
uv run ruff check <changed paths>
```

Then run the package test suites for all packages touched by the cleanup.

## Risks

- **Editor/CLI drift.** Avoid by committing both `pyrightconfig.json` and `.vscode/settings.json`.
- **Hiding real source issues with broad excludes.** Keep excludes focused on tests, fixtures, generated artifacts, environments, and worktree/cache internals.
- **Overusing casts and ignores.** Prefer protocols, sequence contracts, and explicit optional narrowing.
- **Breaking plugin no-Bedrock behavior.** Guarded import fixes must preserve the `narrate=False` and plugin-script paths that run without the Bedrock stack installed.
- **Runtime output drift.** CLI and graph projection type fixes must not alter command output, graph IDs, graph ordering, or JSON/text shapes.

## Suggested Implementation Slices

1. **Production pyright configuration** — add CLI/editor config, confirm source-only diagnostic count remains the expected baseline.
2. **CLI namespace protocols** — remove the `graph-wiki-cli` argparse `object` diagnostics and run CLI tests.
3. **Graph record boundary cleanup** — remove repeated list/tuple errors and run graph-io tests.
4. **Core guarded import narrowing** — fix `scan.py` and `propagate_drift.py` typing while preserving optional Bedrock behavior.
5. **Small package remainder** — clean eval-harness, wiki-io, source-parser, graph-wiki-mcp, and plugin-script diagnostics.
6. **Final verification** — run `pyright`, scoped Ruff, and touched package tests.

