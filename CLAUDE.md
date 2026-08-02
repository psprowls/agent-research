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

Tests are **per-package** (each member sets its own `testpaths`). `--package` only
selects the uv *environment* — it does not scope pytest's collection. Invoked
bare from the repo root, `uv run --package X pytest` resolves `rootdir` to the
**root** `pyproject.toml` and collects the whole ~4,100-test workspace suite
regardless of which package is named. To actually scope, pass the package's own
test path explicitly — this shifts `rootdir` to the package's own
`pyproject.toml`, which is why per-package `testpaths`/`asyncio_mode`/`addopts`
are duplicated locally rather than inherited from root:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests                       # one package
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_narrate.py::test_name   # one test
uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests -m "not integration"     # skip Bedrock/subprocess tests
```

Verify scoping worked with `--collect-only -q` — the count should match the
package's own suite, not the whole workspace.

- `integration`-marked tests need real Bedrock or subprocesses; pass `-m "not integration"` to skip them, `-m integration` to run only them.
- `eval`-marked tests only run with `GRAPH_WIKI_RUN_EVAL=1`.
- Running `pytest` from the workspace root (no explicit package test path) is guarded (`norecursedirs` excludes `src/`, so `graph_io/test_suites.py` — an emitter module, not a test — isn't collected) but still collects every package's suite; that's the intended behavior for whole-suite runs (e.g. CI), not a per-package scoping mechanism.

## Architecture

### Package dependency layers (bottom → top)

```
source-parser      tree-sitter → span-bearing SourceTree + graph projection (graph-io-private)
workspace-io       resolve workspace/repo paths, manifest + config IO (no business logic)
model-adapter      make_bedrock_llm/make_gateway_llm → _GuardedChatBedrockConverse/_GuardedChatOpenAI; role resolution lives in graph-wiki-core
subagent-runtime   SubagentPool — asyncio.Semaphore-bounded Bedrock fan-out + trace IO; owns the model pricing table (subagent_runtime.pricing)
graph-io           SQLite code-graph store, scanning, classification, read-only queries
wiki-io            vault (markdown+frontmatter) read/write primitives
graph-wiki-core    command + prompt + orchestration logic shared by ALL delivery surfaces
  = base           deps: graph-io / wiki-io / work-io / guidance-io / workspace-io — no Bedrock stack;
                   the Claude plugin's script shims re-exec against this closure (scripts/_uv_reexec.py)
  = [bedrock]      extra adds model-adapter + subagent-runtime (+ langchain-aws / langchain-core / bm25s)
  ├── graph-wiki-cli   the `gw` Typer CLI  (project.scripts: gw) — declares graph-wiki-core[bedrock]
  ├── graph-wiki-mcp   MCP server surface  (project.scripts: graph-wiki-mcp) — declares graph-wiki-core[bedrock]
  └── eval-harness     deepeval checks, model sweep runner — declares graph-wiki-core[bedrock]; pricing comes from subagent-runtime
```

The bottom→top listing is a layering order, not a single dependency chain: model-adapter/subagent-runtime and graph-io/wiki-io are independent chains that first join in graph-wiki-core — via the `[bedrock]` extra for the Bedrock chain (`= base` / `= [bedrock]` are packaging variants of core, not sub-packages). Layering is enforced by `tests/test_layering.py` (declared deps + AST imports vs. the layer policy, with a sanctioned-exception allowlist) and `tests/integration/test_base_closure_import.py` (every non-gated core module must import against the base closure).

`graph-wiki-core` is the hub: `commands/` (scan, ingest, query, lint, init, log, propose_domains, graph) hold the real logic; `graph-wiki-cli` and `graph-wiki-mcp` are thin surfaces over it. When changing behavior, change it in core.

### Workspace ≠ repo (critical mental model)

The **repo** is the source code being documented. The **workspace** is a *separate sibling directory* holding the generated artifacts: `<workspace>/wiki/`, `<workspace>/raw/`, and `<workspace>/.graph-wiki/code.db` (the graph DB does **not** live in this repo). **`GRAPH_WIKI_WORKSPACE` is how you point at a workspace** — set it and nothing needs a `--workspace` flag. It is injected via the `env` block of `.claude/settings.local.json`, and it must live in **whichever directory the session runs from** — the repo *and* the workspace each need their own copy if you open Claude Code in both, since a session started in the workspace never reads the repo's settings. Resolution order in `workspace_io.config.resolve()`: `GRAPH_WIKI_WORKSPACE` env var → discovery. Discovery does **not** search for a `.graph-wiki.yaml`: it walks up from cwd for `.git` and assumes `<repo>/graph-wiki`, so a workspace anywhere else is invisible to it and you get `No .graph-wiki.yaml found in <repo>/graph-wiki`. (The repo-side `.graph-wiki.local.yaml` pointer is dead; `resolve()` warns if it finds one. The *workspace*-side `.graph-wiki.local.yaml` `repo-directory:` pin is live and is what supplies the repo path once the env var has located the workspace.) Path accessors live in `workspace_io.paths`.

- `gw scan --workspace <ws>` discovers the repo from cwd.
- `gw graph update --full --repo <repo> --mode test` — `graph build`/`update` resolve the repo *from the workspace*, so always pass `--repo` explicitly or it dies with "ambiguous argument HEAD". Graph updates are incremental; classification-logic changes need `--full`.

### Model access — never bypass the adapter

- Always get models via `model_adapter.make_bedrock_llm(model_id, ...)` or `model_adapter.make_gateway_llm(model_id, ...)` — never construct `ChatBedrockConverse` or `ChatOpenAI` directly, which loses the guard. Bedrock is the **default** backend (`_GuardedChatBedrockConverse`, translating `AccessDeniedException` → `BedrockAccessDenied`). The **Vercel AI Gateway** path returns a `_GuardedChatOpenAI` (a `langchain-openai` `ChatOpenAI` subclass, translating gateway 401s → `GatewayAccessDenied`); credentials come from `AI_GATEWAY_API_KEY` / `AI_GATEWAY_BASE_URL` (env only). Role resolution (mapping a role name like `scanner` to a model id/backend via `models.toml`) lives in `graph-wiki-core`, not in model-adapter.
- **Never** add `langchain-anthropic` or `ChatBedrock` (legacy) — both route outside the Bedrock Converse path. The langchain pieces in use are `langchain-aws` (Bedrock), `langchain-openai` (gateway, adapter-internal only), and `langchain-core` primitives (`@tool`, message types).
- Per-role model tiers (orchestrator, librarian, code_reader, scanner, synthesizer, preflight, …) live in `graph_wiki_core/models.toml` (resolved via `graph_wiki_core/roles.py`) with `sweep_candidates` for the eval harness. Per-workspace overrides go in `<workspace>/.graph-wiki.yaml`. Tests pin a workspace via `GRAPH_WIKI_WORKSPACE`.

### Subagent fan-out

There is no LangGraph/deepagents state machine — that was evaluated and intentionally rejected. Concurrency is `subagent_runtime.SubagentPool` (bounded `asyncio.Semaphore` fan-out). `scan` uses it for entity-page narration, file-description, and drift-judging; all of that is gated behind `narrate=True` so the Claude-plugin branch (`narrate=False`) runs without the Bedrock stack installed (the imports are guarded — see `commands/scan.py`).

### Entity-page ownership model

The scan pipeline regenerates entity pages every run, but only *some* sections. The ownership split (scanner-owned vs scanner-data vs human-owned vs the `last_updated_commit` provenance key) is load-bearing and documented in `.claude/rules/backward-compatibility.md` (auto-loaded). Read it before touching `write_entities`, narrative refresh, or anything that writes `wiki/entities/*.md`.

## Gotchas

- **Worktrees need their own venv.** A fresh `git worktree`'s `.pth` points at the parent repo's `src`, so bare `python` imports the wrong package source. Run `uv sync` in the worktree and use `<worktree>/.venv/bin/python` for tests.
- **Interrupted scans leave sticky placeholders.** Killing a scan mid-narration leaves entity pages with placeholder `## Narrative`/file-maps that plain re-scans won't refill (re-render is byte-identical → "unchanged"). Recovery: `rm wiki/entities/*.md` then rescan.
- `pre-commit` is configured (`.pre-commit-config.yaml`) — runs ruff.

## Conventions

- This is a single-developer research project with **no migrations until v2.0** — the user rebuilds the wiki/graph on schema changes (see `.claude/rules/backward-compatibility.md`). Don't write migration code.
- `wiki-io` modules put the module docstring **first**, above `from __future__ import annotations`, or `__doc__` is None.
- `asyncio_mode = "auto"` is set at root and repeated in each async package's `pyproject.toml` (so it applies when pytest's rootdir resolves to that package).
