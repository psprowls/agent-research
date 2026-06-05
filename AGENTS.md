# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A `uv`-workspace monorepo of AWS-Bedrock-focused AI tooling. The flagship product is **Graph Wiki**: it builds a code graph from a source repo and maintains a cross-referenced markdown "vault" (wiki) alongside it, running the wiki-maintenance workflows (scan / ingest / query / lint) on Bedrock with parallel subagents instead of a Claude-Code-hosted plugin. The same workflows also ship as a Claude Code plugin under `plugins/graph-wiki/`.

## Commands

Everything runs through `uv` (0.11.14+). `uv sync` once to install the whole workspace (all members are editable).

```bash
uv sync                                         # install all workspace members
uv run --package graph-wiki-cli gw --help       # the gw CLI entry point
uv run ruff check . && uv run ruff format       # lint + format (line-length 120, py311)
```

Tests are **per-package** (each member sets its own `testpaths`). Run scoped, not from the root:

```bash
uv run --package graph-wiki-core pytest                       # one package
uv run --package graph-wiki-core pytest tests/unit/test_scan_narrate.py::test_name   # one test
uv run --package graph-wiki-cli pytest -m "not integration"   # skip Bedrock/subprocess tests
```

- `integration`-marked tests need real Bedrock or subprocesses; **skipped by default** — pass nothing special to skip, `-m integration` to opt in.
- `eval`-marked tests only run with `GRAPH_WIKI_RUN_EVAL=1`.
- Running `pytest` from the workspace root is guarded (`norecursedirs` excludes `src/`, so `graph_io/test_suites.py` — an emitter module, not a test — isn't collected). Prefer `--package`.

## Architecture

### Package dependency layers (bottom → top)

```
source-parser      tree-sitter → span-bearing SourceTree + graph projection
workspace-io       resolve workspace/repo paths, manifest + config IO (no business logic)
model-adapter      make_llm(role) → _GuardedChatBedrockConverse; roles in models.toml
subagent-runtime   SubagentPool — asyncio.Semaphore-bounded Bedrock fan-out + trace IO
graph-io           SQLite code-graph store, scanning, classification, read-only queries
wiki-io            vault (markdown+frontmatter) read/write primitives
graph-wiki-core    command + prompt + orchestration logic shared by ALL delivery surfaces
  ├── graph-wiki-cli   the `gw` Typer CLI  (project.scripts: gw)
  ├── graph-wiki-mcp   MCP server surface  (project.scripts: graph-wiki-mcp)
  └── eval-harness     deepeval checks, pricing, model sweep runner
```

`graph-wiki-core` is the hub: `commands/` (scan, ingest, query, lint, init, log, propose_domains, ack_drift, graph) hold the real logic; `graph-wiki-cli` and `graph-wiki-mcp` are thin surfaces over it. When changing behavior, change it in core.

### Workspace ≠ repo (critical mental model)

The **repo** is the source code being documented. The **workspace** is a *separate sibling directory* holding the generated artifacts: `<workspace>/wiki/`, `<workspace>/raw/`, and `<workspace>/.graph-wiki/code.db` (the graph DB does **not** live in this repo). For this repo the workspace is pinned in `.graph-wiki.local.yaml` (`workspace-directory:`). Resolution order in `workspace_io.config.resolve()`: `GRAPH_WIKI_WORKSPACE` env var → `.graph-wiki.local.yaml` → discovery. Path accessors live in `workspace_io.paths`.

- `gw scan --workspace <ws>` discovers the repo from cwd.
- `gw graph update --full --repo <repo> --mode test` — `graph build`/`update` resolve the repo *from the workspace*, so always pass `--repo` explicitly or it dies with "ambiguous argument HEAD". Graph updates are incremental; classification-logic changes need `--full`.

### Bedrock-only model access — never bypass the adapter

- Always get models via `model_adapter.make_llm(role)`. It returns `_GuardedChatBedrockConverse`, which translates `AccessDeniedException` → `BedrockAccessDenied`. Constructing `ChatBedrockConverse` directly loses that guard.
- **Never** add `langchain-anthropic` or `ChatBedrock` (legacy) — both route outside the Bedrock Converse path; the only langchain pieces in use are `langchain-aws` + `langchain-core` primitives (`@tool`, message types).
- Per-role model tiers (orchestrator, librarian, code_reader, scanner, synthesizer, preflight, …) live in `model_adapter/models.toml` with `sweep_candidates` for the eval harness. Per-workspace overrides go in `<workspace>/.graph-wiki.yaml`. Tests pin a workspace via `GRAPH_WIKI_WORKSPACE`.

### Subagent fan-out

There is no LangGraph/deepagents state machine — that was evaluated and intentionally rejected. Concurrency is `subagent_runtime.SubagentPool` (bounded `asyncio.Semaphore` fan-out). `scan` uses it for entity-page narration, file-description, and drift-judging; all of that is gated behind `narrate=True` so the Claude-plugin branch (`narrate=False`) runs without the Bedrock stack installed (the imports are guarded — see `commands/scan.py`).

### Entity-page ownership model

The scan pipeline regenerates entity pages every run, but only *some* sections. The ownership split (scanner-owned vs scanner-data vs human-owned vs the `last_updated_commit` provenance key) is load-bearing and documented in `.claude/rules/backward-compatibility.md` (auto-loaded). Read it before touching `write_entities`, narrative refresh, or anything that writes `wiki/entities/*.md`.

## Gotchas

- **Worktrees need their own venv.** A fresh `git worktree`'s `.pth` points at the parent repo's `src`, so bare `python` imports the wrong package source. Run `uv sync` in the worktree and use `<worktree>/.venv/bin/python` for tests.
- **Interrupted scans leave sticky placeholders.** Killing a scan mid-narration leaves entity pages with placeholder `## Narrative`/file-maps that plain re-scans won't refill (re-render is byte-identical → "unchanged"). Recovery: `rm wiki/entities/*.md` then rescan.
- **Brand gate.** `scripts/check-brand.sh` fails the build on stray upstream names (`lattice`, `code-wiki-agent`, etc.) not allow-listed in `.brand-grep-allow`. Run it after renames.
- `pre-commit` is configured (`.pre-commit-config.yaml`) — runs ruff.

## Conventions

- This is a single-developer research project with **no migrations until v2.0** — the user rebuilds the wiki/graph on schema changes (see `.claude/rules/backward-compatibility.md`). Don't write migration code.
- `wiki-io` modules put the module docstring **first**, above `from __future__ import annotations`, or `__doc__` is None.
- `asyncio_mode = "auto"` is set at root and repeated in each async package's `pyproject.toml` (so it applies when pytest's rootdir resolves to that package).
