---
updated_at: "2026-05-19T00:00:00Z"
---

## Architecture Overview

`deep-agents` is a uv-managed Python 3.11+ monorepo whose first deliverable is **`code-wiki-agent`** — a Bedrock-only port of the upstream lattice-wiki Claude Code plugin (in-tree as `graph-wiki`). The agent exposes both a Typer CLI (`code-wiki-agent`) and a stdio FastMCP server (`code-wiki-mcp`) over the same command functions.

Composition pattern: **in-house fan-out primitives over langchain-core + langchain-aws**. There is no `deepagents`, no `langgraph`, and no top-level `langchain`. Concurrency is implemented directly via `asyncio.Semaphore` inside `SubagentPool`, and Bedrock errors are translated by a `_GuardedChatBedrockConverse` subclass produced by `make_llm(role)`. This is a deliberate departure from CLAUDE.md's stack-recommendation table (documented in CLAUDE.md §2 and §4 as "rejected by design" / "deferred"), motivated by direct control over fan-out semantics and trace shape.

## Key Components

| Component | Path | Responsibility |
|-----------|------|---------------|
| `model-adapter` | `packages/model-adapter/` | `make_llm(role)` returns `_GuardedChatBedrockConverse`; reads `models.toml`; wraps `AccessDeniedException` into `BedrockAccessDenied` with IAM-actionable message. |
| `subagent-runtime` | `packages/subagent-runtime/` | `SubagentPool.run_all()` async fan-out: per-role `asyncio.Semaphore`, `asyncio.gather(return_exceptions=True)` for partial-failure isolation, JSONL trace per invocation via `trace_io.write_trace_record`. |
| `workspace-io` | `packages/workspace-io/` | Workspace bootstrap, `.graph-wiki.yaml` manifest IO, plugin version registry, `GraphWikiConfig.resolve()`. Hatchling-built (no uv_build). |
| `vault-io` | `packages/vault-io/` | Vault page IO, frontmatter handling, layout block parser/writer in CLAUDE.md, monorepo scanner diffing, mechanical lint passes, hand-rolled YAML emitter for layout block. |
| `eval-harness` | `packages/eval-harness/` | `run_sweep` / `run_role_sweep` cost-frontier model sweep, hardcoded Bedrock `PRICES` table, divergence checks, deepeval-backed judge, preflight token estimator. |
| `code-wiki-agent` | `agents/code-wiki-agent/` | Typer CLI (`code-wiki-agent`) + FastMCP stdio server (`code-wiki-mcp`). Command modules under `commands/` (init, scan, ingest, lint, query, log) wrap subagent fan-out. Prompts assembled from `prompts/` and `prompts/_fragments/`. |
| `prompt-sources` | `packages/prompt-sources/` | Exists on disk but **excluded from the uv workspace** (`exclude = ["packages/prompt-sources"]` in root pyproject.toml). |

## Data Flow

CLI (`typer.app`) or MCP host (stdio FastMCP) → command function in `code_wiki_agent.commands.*` (`run_query`, `run_scan`, `run_ingest_*`, `run_lint`, `run_init`, `run_log`)
→ `vault_io._workspace.resolve_wiki_and_repo()` to locate vault + repo roots
→ `model_adapter.loader.make_llm(role)` to construct a guarded `ChatBedrockConverse`
→ `subagent_runtime.SubagentPool.run_all(items, task, role, model_id, max_concurrency)` for parallel role-bound dispatch
→ per-invocation JSONL record via `subagent_runtime.trace_io.write_trace_record` into `<vault>/.code-wiki/traces/`
→ vault writes via `vault_io` (layout block, log append, page IO)
→ result returned as a `dataclass` and rendered (`typer.echo`) or returned as a Pydantic MCP output model.

The MCP server (`code_wiki_mcp.server`) installs an `_StdoutGuard` at import time to ensure no library writes to stdout corrupt JSON-RPC framing — only FastMCP's `sys.stdout.buffer` is allowed through.

`eval-harness.sweep` runs the same `run_query` / `run_scan` / `run_lint` / `run_ingest_source` entry points inside an `EvalWorktree` per `(role, candidate_model_id)` cell, parses the latest JSONL trace, and computes USD via `pricing.cost_for_usage`.

## Conventions

- **Naming**: package directories use kebab-case (`model-adapter`); Python modules use snake_case (`model_adapter`).
- **Workspace deps**: every cross-package dep is declared via `[tool.uv.sources] <pkg> = { workspace = true }` and the bare package name in `dependencies`.
- **Build backends**: `uv_build>=0.11.14,<0.12` everywhere except `workspace-io`, which uses `hatchling`.
- **Test layout**: each package has its own `tests/` directory; `addopts = "--import-mode=importlib"` is set per-package. `asyncio_mode = "auto"` is enabled where async tests exist (root, subagent-runtime, eval-harness, code-wiki-agent).
- **Markers**: `integration` (requires Bedrock or subprocess — skipped by default), `eval` (gated on `CODE_WIKI_RUN_EVAL=1`).
- **Trace records**: JSONL with `schema_version: 1`, fields `role`, `model_id`, `item_id`, `status`, `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `timestamp`. `usage_metadata` is None-guarded; OSError on trace write is logged WARNING and swallowed.
- **Pydantic v2 + Bedrock**: `_GuardedChatBedrockConverse` overrides `invoke` via subclass (not attribute assignment — Pydantic v2 `extra='forbid'` blocks reassignment); per-instance `_model_id_for_errors` is set via `object.__setattr__`.
- **Concurrency**: `asyncio.Semaphore` is created **inside** `run_all()`, never `__init__`, to bind to the running event loop (pytest-asyncio compatibility).
- **MCP stdout**: nothing may print to stdout except FastMCP JSON-RPC frames; `_StdoutGuard` enforces this at import-time.

## Stack Departures (Rejected by Design / Deferred)

- `deepagents` — rejected; `SubagentPool` replaces `SubAgentMiddleware`.
- `langgraph` — rejected; fan-out is plain asyncio + `langchain_core.runnables.RunnableConfig` (used only to inject `recursion_limit`).
- top-level `langchain` — rejected; only `langchain-core` and `langchain-aws` are installed.
- `langchain-mcp-adapters` — deferred; agents do not currently consume external MCP tools.
- `langchain-anthropic` — rejected; Bedrock-only constraint.

These align with CLAUDE.md §2's stack-departure note (rewritten 2026-05-19) and are not drift findings.
