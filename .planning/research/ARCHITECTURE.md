# Architecture Research

**Domain:** Tiered uv monorepo — shared cores + agent packages (deep-agents / code-wiki-agent)
**Researched:** 2026-05-13
**Confidence:** HIGH (monorepo + MCP patterns verified; deepagents subagent API is MEDIUM — library is young, v0.6.1 as of May 2026, internal fan-out API not yet formally documented)

---

## 1. Monorepo Layout

### Concrete Directory Tree

```
deep-agents/                          # workspace root (no deployable code here)
├── pyproject.toml                    # workspace declaration only — no [project] table
├── uv.lock                           # single shared lockfile
├── .python-version                   # pinned Python (3.11+)
├── README.md
├── LICENSE
│
├── cores/                            # shared infrastructure packages
│   ├── model-adapters/               # Bedrock ChatBedrock wrapper, model registry
│   │   ├── pyproject.toml            # name = "deep-agents-models"
│   │   └── src/deep_agents_models/
│   │       ├── __init__.py
│   │       ├── bedrock.py            # ChatBedrock factory, model_id enum
│   │       └── registry.py           # role → model_id mapping, loaded from config
│   │
│   ├── subagent-runtime/             # asyncio fan-out primitives
│   │   ├── pyproject.toml            # name = "deep-agents-runtime"
│   │   └── src/deep_agents_runtime/
│   │       ├── __init__.py
│   │       ├── pool.py               # SubagentPool.fanout(), SubagentPool.map()
│   │       └── result.py             # FanoutResult, aggregation helpers
│   │
│   └── eval-harness/                 # cross-agent eval scaffolding
│       ├── pyproject.toml            # name = "deep-agents-eval"
│       └── src/deep_agents_eval/
│           ├── __init__.py
│           ├── recorder.py           # record baseline outputs from lattice-wiki
│           ├── runner.py             # replay queries, swap models, score results
│           ├── scorer.py             # similarity / rubric scoring
│           └── report.py             # cost-frontier chart generation
│
├── agents/                           # agent packages (one per agent product)
│   └── code-wiki-agent/
│       ├── pyproject.toml            # name = "code-wiki-agent"
│       ├── src/code_wiki_agent/
│       │   ├── __init__.py
│       │   ├── mcp_server.py         # FastMCP entry point (exposes tools over MCP)
│       │   ├── cli.py                # Typer/Click CLI (headless in-process agent loop)
│       │   ├── config.py             # VaultConfig, ModelConfig, loaded from .code-wiki.json
│       │   │
│       │   ├── vault/                # vault IO layer (ported from lattice-wiki-core)
│       │   │   ├── __init__.py
│       │   │   ├── layout_io.py      # read/write layout block (direct port)
│       │   │   ├── frontmatter.py    # parse/emit frontmatter (direct port)
│       │   │   ├── search.py         # BM25 search (direct port of wiki_search.py)
│       │   │   ├── index.py          # index.md read/write, category-first structure
│       │   │   ├── templates.py      # page template rendering (port asset templates)
│       │   │   └── log.py            # append_log port
│       │   │
│       │   ├── commands/             # one module per wiki command
│       │   │   ├── __init__.py
│       │   │   ├── init_.py          # init command (underscore avoids reserved word)
│       │   │   ├── scan.py           # scan command
│       │   │   ├── ingest.py         # ingest command
│       │   │   ├── query.py          # query command (librarian subagent fan-out)
│       │   │   ├── lint_.py          # lint command (linter subagent fan-out)
│       │   │   └── log_.py           # log command
│       │   │
│       │   ├── agents/               # agent role definitions (prompts + tool sets)
│       │   │   ├── __init__.py
│       │   │   ├── librarian.py      # reads pages, synthesizes answers
│       │   │   ├── linter.py         # lint rule groups
│       │   │   ├── scanner.py        # package inventory, diff against vault
│       │   │   └── ingestor.py       # source extraction, page routing
│       │   │
│       │   └── tools/                # LangChain @tool functions exposed to agents
│       │       ├── __init__.py
│       │       ├── vault_tools.py    # read_page, search_pages, list_pages
│       │       ├── write_tools.py    # write_page, update_frontmatter, append_log
│       │       └── repo_tools.py     # list_packages, detect_containers, git_state
│       │
│       └── tests/                    # per-package tests (live here, not at root)
│           ├── conftest.py           # vault fixtures, tmp_path helpers
│           ├── fixtures/
│           │   ├── vaults/           # sample vault directories for IO tests
│           │   └── baselines/        # recorded lattice-wiki outputs for eval replay
│           ├── unit/
│           │   ├── test_layout_io.py
│           │   ├── test_frontmatter.py
│           │   ├── test_search.py
│           │   ├── test_lint_rules.py
│           │   └── test_scan.py
│           └── integration/
│               ├── test_query_flow.py   # end-to-end query against fixture vault
│               └── test_lint_flow.py    # end-to-end lint against fixture vault
│
└── .planning/                        # GSD project management (not deployed)
    └── research/
```

### Workspace Root pyproject.toml

```toml
[tool.uv.workspace]
members = [
    "cores/*",
    "agents/*",
]

[tool.uv]
# No [project] table — root is a workspace-only container
```

### Member pyproject.toml Pattern (code-wiki-agent)

```toml
[project]
name = "code-wiki-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "deep-agents-models",
    "deep-agents-runtime",
    "deepagents>=0.6.1",
    "langchain-aws>=0.2",
    "langchain-mcp-adapters",
    "fastmcp",
    "typer",
    "rank-bm25",          # or keep hand-rolled BM25 — see vault IO section
]

[tool.uv.sources]
deep-agents-models  = { workspace = true }
deep-agents-runtime = { workspace = true }
```

### Where Tests and Fixtures Live

Tests live **per package** (`agents/code-wiki-agent/tests/`), not at the top level. Rationale:

- `uv run pytest` from the workspace root runs all packages; from within a package it runs only that package
- `conftest.py` scoped per package means no cross-package fixture pollution
- Fixture vaults (sample vault directories) live in `tests/fixtures/vaults/` within the package
- Eval baselines live in `tests/fixtures/baselines/` — committed JSON or Markdown files recorded from current lattice-wiki runs

The eval harness (`cores/eval-harness/`) provides the replay engine; the baselines live in the consuming package (`agents/code-wiki-agent/tests/fixtures/baselines/`) so they version together with the commands they test.

---

## 2. `code-wiki-agent` Internal Architecture

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `mcp_server.py` | FastMCP server instance; registers each command as an `@mcp.tool()`; no agent logic here — delegates to `commands/` |
| `cli.py` | Typer app; one subcommand per wiki command; calls same `commands/` functions as MCP tools do |
| `config.py` | Loads `.code-wiki.json` (or `.lattice-wiki.json` for compatibility); resolves vault path, repo root, model assignments per role |
| `vault/` | Pure Python, no LLM calls; read/write vault on disk; shared by all commands and both surfaces |
| `commands/` | Orchestrates one wiki command; constructs the deepagents graph or SubagentPool invocations; returns structured result |
| `agents/` | Role definitions: system prompt, tool list, model_id. A `RoleSpec` dataclass |
| `tools/` | LangChain `@tool` decorated functions; vault operations the LLM agents can call |

### How MCP Server Composes with Agent Loop

The MCP server is a thin dispatch layer. It does not run an agent loop itself — it receives a tool call from the DeepAgents CLI host (which runs the outer conversation loop on Bedrock), translates it into a command invocation, runs the command (which runs the inner agent loop using deepagents or asyncio + ChatBedrock directly), and returns the result.

```
DeepAgents CLI (outer agent, Bedrock)
    │  MCP tool call: wiki_query(question="…")
    ▼
mcp_server.py  →  commands/query.py  →  SubagentPool.fanout(librarian, pages)
                                              │
                                     asyncio.gather(
                                       librarian_agent.ainvoke(page_1),
                                       librarian_agent.ainvoke(page_2),
                                       …
                                     )
                                              │
                                     aggregate → synthesize → return str
```

The headless CLI takes the same path from `cli.py` → `commands/query.py` — the command functions are surface-agnostic.

### Call Graph: `query "X"` (MCP path)

```
[DeepAgents CLI host]
  └─ MCP tool call: wiki_query(question="X", vault="/path/to/wiki")
       │
       ▼
  mcp_server.py: @mcp.tool("wiki_query")
       │  deserialize args → QueryRequest
       ▼
  commands/query.py: run_query(request)
       │
       ├─ vault/search.py: bm25_search(question, top_k=10)
       │       returns: [(path, score), ...]
       │
       ├─ SubagentPool.fanout(
       │     role=agents/librarian.py:LibrarianRole,
       │     items=top_k_paths,          # one item per subagent invocation
       │     question=question,
       │  )
       │       └─ asyncio.gather(
       │            ChatBedrock(model_id=librarian_model).ainvoke(
       │              [SystemMessage(librarian_prompt),
       │               HumanMessage(page_content + question)]
       │            ),
       │            … × top_k
       │          )
       │       returns: [PageReading(path, findings, citations), ...]
       │
       ├─ aggregate: collect findings, deduplicate citations
       │
       └─ synthesize: single ChatBedrock call (haiku or sonnet) to stitch answer
              returns: str (wikilink citations + prose answer)
       │
       ▼
  MCP response: text/plain (answer string)
```

### Call Graph: `query "X"` (CLI path)

```
cli.py: code-wiki-agent query "X"
  └─ commands/query.py: run_query(request)
       │  (identical to MCP path from here)
       ▼
       … same flow as above …
       returns: str
  └─ print(answer)
```

The CLI adds no logic — it constructs a `QueryRequest` from argv and calls the same `run_query` function.

### Call Graph: `lint` (MCP path)

```
[DeepAgents CLI host]
  └─ MCP tool call: wiki_lint(vault="/path/to/wiki", repo="/path/to/repo")
       │
       ▼
  mcp_server.py: @mcp.tool("wiki_lint")
       │
       ▼
  commands/lint_.py: run_lint(request)
       │
       ├─ vault/: collect all pages, build link graph, load layout
       │       (pure Python, no LLM — port of lint_wiki.py scan() function)
       │       returns: LintContext(pages, inbound, outbound, layout, disk_packages)
       │
       ├─ mechanical_pass: run lint rule groups in parallel (no LLM)
       │       SubagentPool.fanout(
       │         role=MechanicalLintRole,   # deterministic Python functions, not LLM
       │         items=RULE_GROUPS,         # [orphans, broken_links, stale, code_drift, …]
       │         context=LintContext,
       │       )
       │       returns: [RuleGroupResult, ...]
       │
       ├─ semantic_pass: LLM subagent fan-out over pages flagged by mechanical pass
       │       SubagentPool.fanout(
       │         role=agents/linter.py:SemanticLinterRole,
       │         items=flagged_pages,
       │         question="assess semantic quality and actionability",
       │       )
       │       returns: [SemanticFinding, ...]
       │
       └─ report: merge mechanical + semantic findings → LintReport
              returns: str (markdown report)
       │
       ▼
  MCP response: text/plain (lint report markdown)
```

Note: mechanical lint checks (orphans, broken links, stale dates, code drift, container drift) are pure-Python ports from `lint_wiki.py` — they do NOT call LLMs. Only the semantic pass (quality assessment, actionability scoring) uses LLM subagents. This keeps the mechanical pass fast and deterministic.

---

## 3. Subagent Fan-Out Boundaries

### Where Parallelism Lives

| Command | Fan-Out Point | Unit of Parallelism | Aggregation |
|---------|---------------|---------------------|-------------|
| `query` | After BM25 retrieves top-k pages | One LLM call per page (librarian reads a page, extracts relevant findings) | Collect findings → single synthesis call |
| `lint` (semantic) | After mechanical pass flags pages | One LLM call per flagged page group | Merge findings, rank by severity |
| `scan` | After disk packages listed | One LLM call per package (ingestor assesses diff vs vault) | Collect stub updates |
| `ingest` | After sources listed | One LLM call per source file | Collect routed content |

### The Abstraction: `SubagentPool`

Defined in `cores/subagent-runtime/src/deep_agents_runtime/pool.py`.

```python
from dataclasses import dataclass
from typing import TypeVar, Generic, Callable, Awaitable
import asyncio
from langchain_aws import ChatBedrock

T = TypeVar("T")
R = TypeVar("R")

@dataclass
class RoleSpec:
    role_name: str          # "librarian", "linter", etc.
    system_prompt: str
    model_id: str           # resolved from ModelRegistry at call time
    max_tokens: int = 4096

class SubagentPool:
    def __init__(self, model_registry):
        self._registry = model_registry

    async def fanout(
        self,
        role: RoleSpec,
        items: list[T],
        build_messages: Callable[[T], list],   # item → [SystemMessage, HumanMessage]
        max_concurrency: int = 8,
    ) -> list[R]:
        llm = ChatBedrock(
            model_id=role.model_id,
            max_tokens=role.max_tokens,
        )
        sem = asyncio.Semaphore(max_concurrency)
        async def _invoke(item: T) -> R:
            async with sem:
                msgs = build_messages(item)
                return await llm.ainvoke(msgs)
        return await asyncio.gather(*[_invoke(item) for item in items])
```

Key decisions in this design:

- `max_concurrency` semaphore prevents Bedrock rate-limit hammering (Bedrock TPS limits are per-model, per-region)
- Each subagent invocation is a stateless `ainvoke` — no LangGraph state shared between subagents; this is intentional for v1 (within-command fan-out, not nested subagents)
- The parent command function owns aggregation; `SubagentPool` only handles dispatch and concurrency

### Keeping the Parent Context Lean

The parent command function (`commands/query.py`, etc.) never passes full page content into a single growing context. Instead:

1. Parent retrieves page paths from BM25 (small: just paths + scores)
2. Parent fans out: each subagent gets one page's content + the question — context bounded per subagent
3. Subagents return structured results (findings, citations, findings) — small
4. Parent aggregates small results, makes one synthesis call

The parent agent's own context contains: question, page paths, collected findings (structured). It never sees all pages concatenated. This is the core context-isolation benefit of within-command fan-out.

---

## 4. Vault IO Layer: Port vs Rewrite

### Decision: Direct Port with Namespace Change

Port from `lattice-wiki-core` to `code_wiki_agent/vault/`. Do not add an import dependency on lattice-wiki-core.

**Rationale:**

| Module | Port decision | Notes |
|--------|---------------|-------|
| `layout_io.py` | **Port verbatim** | 209 lines, stdlib-only, stable schema, zero dependencies. Critical for read-compatibility. |
| `wiki_search.py` | **Port + thin wrapper** | 196 lines, stdlib BM25. Extract the search function, drop the `__main__` CLI entry, add a `VaultSearch` class. |
| `lint_wiki.py` (mechanical checks) | **Port scan() function** | The scan() function is ~200 lines of pure Python. Port it, strip the `main()` / argparse shell. The semantic pass is new code. |
| `scan_monorepo.py` | **Port `discover_workspaces()`** | The workspace discovery logic is reusable; strip lattice-workspace integration, replace with direct path config from `.code-wiki.json` |
| `detect_containers.py` | **Port** | Container detection is pure heuristics, no LLM |
| `graph_analyzer.py` | **Port** | Graph analysis (wikilink traversal) is pure Python |
| `append_log.py` | **Port** | 50-line file, trivial |
| `update_tokens.py` | **Defer** | Token counting in frontmatter is a lattice-wiki-specific convention; port only if needed for parity |
| `ingest_source.py` / `ingest_work_item.py` | **Rewrite** | The new ingestor uses LLM subagents; old version is LLM-orchestrated from outside |
| `_workspace.py` | **Replace** | No lattice-workspace dependency; vault path comes from `.code-wiki.json` config |
| `_version_check.py` | **Drop** | Not needed |
| assets / page-templates | **Copy verbatim** | Templates are format-compatible; copy to `src/code_wiki_agent/assets/` |

**Why not import lattice-wiki-core directly?**
- Deep-agents is a separate repo; adding a cross-repo path dependency creates a fragile development setup
- lattice-wiki-core has its own `_workspace.py` that resolves paths via `lattice-workspace` — that coupling doesn't belong in deep-agents
- The relevant code is ~800 lines across ~6 files; porting is a one-day task and makes the package self-contained

**Format compatibility commitment:** `layout_io.py` is ported verbatim, same sentinel strings (`<!-- lattice-wiki:layout:start -->`), same YAML schema. Existing vaults are read-compatible on day one.

---

## 5. Eval Harness Architecture

### Location: Separate Core Package

The eval harness lives in `cores/eval-harness/` as the `deep-agents-eval` package, not in-tree to `code-wiki-agent`. This allows future agents to reuse the same replay + scoring infrastructure.

The `code-wiki-agent` package declares `deep-agents-eval` as a dev dependency.

### Structure

```
cores/eval-harness/src/deep_agents_eval/
├── recorder.py     # drives lattice-wiki (subprocess calls), captures stdout → JSON
├── runner.py       # replay: given a recorded baseline, re-runs the command
│                   # against the same fixture vault with a different model config
├── scorer.py       # similarity scoring (BM25 overlap, ROUGE-L, rubric prompt)
└── report.py       # cost per run from Bedrock API pricing table + quality score
                    # → cost-frontier chart (CSV + matplotlib optional)
```

### How It Discovers Subagent Roles to Test

`runner.py` imports `RoleSpec` from `code_wiki_agent.agents.*`. Each role is a dataclass with `role_name`, `system_prompt`, `model_id`. The runner receives a `model_map: dict[str, str]` override (role_name → model_id) and patches the registry before invoking the command.

```python
# Eval invocation pattern
from deep_agents_eval.runner import EvalRunner
from code_wiki_agent.config import ModelRegistry

runner = EvalRunner(
    baseline_path="tests/fixtures/baselines/query_baseline.json",
    vault_path="tests/fixtures/vaults/sample-repo-wiki",
)
results = await runner.run_sweep(
    command="query",
    question="What does the middleware pipeline do?",
    model_sweeps=[
        {"librarian": "amazon.nova-micro-v1:0"},
        {"librarian": "anthropic.claude-3-haiku-20240307-v1:0"},
        {"librarian": "anthropic.claude-3-5-sonnet-20241022-v2:0"},
    ],
)
report.cost_frontier(results, role="librarian")
```

### How It Holds Prompts Fixed While Varying Models

The `ModelRegistry` is the only thing swapped. `RoleSpec.system_prompt` is read from the role definition and never modified by the eval runner. The runner patches `model_id` in the registry before calling the command — prompts are frozen by construction.

### Baseline Recording

`recorder.py` calls the existing lattice-wiki commands as subprocesses (using the Claude Code SDK via the lattice-wiki plugin, or direct python calls), captures output, and serializes to JSON. These baselines are committed to `tests/fixtures/baselines/` and serve as the gold standard.

---

## 6. Dependency Direction

### Strict Rules

```
cores/model-adapters       ←  no upstream dependencies (leaf)
cores/subagent-runtime     ←  depends on: model-adapters
cores/eval-harness         ←  depends on: model-adapters, subagent-runtime
agents/code-wiki-agent     ←  depends on: model-adapters, subagent-runtime
                           ←  dev depends on: eval-harness
```

**Rules enforced by package declarations (not enforced automatically — discipline required):**

1. `cores/` packages MUST NOT import from `agents/`
2. `cores/model-adapters` MUST NOT import from `cores/subagent-runtime` or `cores/eval-harness`
3. `agents/code-wiki-agent` MAY import from any `cores/` package
4. `agents/code-wiki-agent/vault/` is internal to that package — other packages must not import from it (it's wiki-specific IO, not a shared core)
5. `agents/code-wiki-agent/tools/` exposes LangChain tools that the vault and agents modules use — no reverse dependency
6. Future agents added to `agents/` may import from `cores/` but MUST NOT import from other agents

### Component Communication Boundary Table

| From | To | Via | Notes |
|------|----|-----|-------|
| `mcp_server.py` | `commands/` | Direct function call | MCP tool handler = thin wrapper |
| `cli.py` | `commands/` | Direct function call | CLI = thin wrapper |
| `commands/` | `vault/` | Direct import | Vault IO is synchronous, no LLM |
| `commands/` | `SubagentPool` | `await pool.fanout(...)` | Async |
| `SubagentPool` | `ChatBedrock` | `await llm.ainvoke(msgs)` | Per subagent invocation |
| `commands/` | `agents/` | Import `RoleSpec` dataclass | No circular dependency |
| `commands/` | `tools/` | Construct tool list for agents | Optional — some commands run LLM without tool-calling |
| `eval-harness` | `commands/` | Import and invoke | Test harness only |
| `eval-harness` | `agents/` | Import `RoleSpec` to introspect roles | For sweep configuration |

---

## 7. Build Order and Minimum Vertical Slice

### Dependency Graph

```
[A] Monorepo scaffold (pyproject.toml, uv workspace, CI skeleton)
      ↓
[B] cores/model-adapters  (ChatBedrock factory, ModelRegistry)
      ↓
[C] cores/subagent-runtime  (SubagentPool.fanout)
      ↓
[D] agents/code-wiki-agent/vault/  (layout_io port, frontmatter, BM25)
      ↓
[E] agents/code-wiki-agent/tools/  (vault_tools, repo_tools — LangChain @tool)
      ↓
[F] agents/code-wiki-agent/agents/librarian  (RoleSpec + prompt)
      ↓
[G] agents/code-wiki-agent/commands/query  (fan-out + synthesis)
      ↓
[H] agents/code-wiki-agent/mcp_server.py   (wiki_query tool)
      ↓  (parallel to H)
[H'] agents/code-wiki-agent/cli.py          (code-wiki-agent query …)
      ↓
[I] cores/eval-harness  (can start once G works, before other commands)
      ↓
[J] Remaining commands: lint, scan, ingest, init, log
```

### Suggested Phase Order

**Phase 1 — Scaffold + Model Adapter (A + B)**

Deliverables: uv workspace wires together; `ChatBedrock` factory proven against Bedrock in a throwaway script; `ModelRegistry` reads a config file and returns `model_id` by role name. No agent logic yet.

Gate: `uv run python -c "from deep_agents_models.bedrock import make_llm; print(make_llm('haiku').invoke('ping'))"` works against real Bedrock.

**Phase 2 — SubagentPool + Vault IO (C + D)**

Deliverables: `SubagentPool.fanout()` with semaphore + `asyncio.gather`; unit tested with a mock LLM. Vault IO ported: `layout_io`, `frontmatter`, `BM25 search`, `append_log`. Fixture vaults committed for testing.

Gate: `pytest agents/code-wiki-agent/tests/unit/` fully passes.

**Phase 3 — Minimum Vertical Slice: `query` end-to-end (E + F + G + H + H')**

Deliverables: `tools/vault_tools.py`, `agents/librarian.py`, `commands/query.py`, `mcp_server.py` exposing `wiki_query`, `cli.py` with `query` subcommand. Runs against an existing lattice-wiki vault. Subagent fan-out hits real Bedrock.

Gate: `code-wiki-agent query "What does the middleware pipeline do?"` returns a coherent answer with wikilink citations. MCP server starts and responds to a tool call from the DeepAgents CLI.

This is the minimum vertical slice that proves the architecture end-to-end.

**Phase 4 — Eval Harness (I)**

Deliverables: `recorder.py` captures lattice-wiki baseline for `query`; `runner.py` replays against sweep of Bedrock models; `report.py` outputs cost vs quality table. Baselines committed.

Gate: cost-frontier chart shows at least two models at different quality/cost tradeoffs for the librarian role.

**Phase 5 — Remaining Commands (J)**

Deliverables: `lint`, `scan`, `ingest`, `init`, `log` — in order of complexity. `lint` is the most complex (mechanical pass port + semantic fan-out). `init` and `log` are the simplest.

Suggested sub-order within Phase 5: `log` (trivial port) → `init` (template scaffolding, no LLM fan-out) → `scan` (scanner subagent fan-out) → `ingest` (ingestor subagent) → `lint` (mechanical port + semantic subagent).

Gate per command: parity test against recorded lattice-wiki output for same fixture vault.

---

## System Overview Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     Delivery Surfaces                            │
│   ┌─────────────────────────┐   ┌──────────────────────────┐    │
│   │   MCP Server            │   │   Headless CLI            │    │
│   │   (mcp_server.py)       │   │   (cli.py)                │    │
│   │   FastMCP tool wrappers │   │   Typer subcommands       │    │
│   └────────────┬────────────┘   └────────────┬─────────────┘    │
└────────────────┼────────────────────────────-┼──────────────────┘
                 │ calls                       │ calls
┌────────────────▼─────────────────────────────▼──────────────────┐
│                   commands/ (orchestrators)                      │
│   query.py  |  lint_.py  |  scan.py  |  ingest.py  |  init_.py  │
│   • loads config                                                 │
│   • reads vault (via vault/)                                     │
│   • fans out to SubagentPool                                     │
│   • aggregates results                                           │
└───────────┬──────────────────────────┬───────────────────────────┘
            │                          │
┌───────────▼──────────┐   ┌───────────▼──────────────────────────┐
│   vault/ (pure IO)   │   │   cores/subagent-runtime              │
│   layout_io          │   │   SubagentPool.fanout(role, items)    │
│   frontmatter        │   │   asyncio.gather + semaphore          │
│   BM25 search        │   └───────────┬──────────────────────────┘
│   index IO           │               │ ainvoke per item
│   templates          │   ┌───────────▼──────────────────────────┐
│   append_log         │   │   cores/model-adapters                │
└──────────────────────┘   │   ChatBedrock(model_id=role.model_id) │
                           │   ModelRegistry (role → model_id)     │
                           └──────────────────────────────────────-┘
                                         │
                                    AWS Bedrock
                              (Nova, Claude Haiku/Sonnet,
                               Llama, Mistral per role)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Agent Loop in the MCP Tool Handler

**What people do:** Run a full multi-turn LangGraph agent inside the MCP tool handler, accumulating state across tool calls within a single MCP invocation.

**Why it's wrong:** MCP tools must return quickly and cleanly. The DeepAgents CLI host manages the outer conversation loop. Putting an inner LangGraph loop inside the MCP handler creates nested loops with unclear context boundaries and makes streaming impossible.

**Do this instead:** Each MCP tool handler runs a single command (one BM25 search + one fan-out + one synthesis call). The outer agent loop (hosted by DeepAgents CLI) handles multi-turn conversation across multiple tool calls.

### Anti-Pattern 2: Shared Mutable Vault State Between Subagents

**What people do:** Give multiple concurrent subagents write access to the same vault files.

**Why it's wrong:** Race conditions on file writes. Fan-out subagents in v1 are read-only (librarian, linter semantic pass). Only the parent command writes to the vault, after collecting all subagent results.

**Do this instead:** Fan-out subagents are read-only. The parent command serializes all writes after `asyncio.gather` completes.

### Anti-Pattern 3: Putting Vault IO in `cores/`

**What people do:** Factor the vault IO layer into a shared core so other agents can use it.

**Why it's wrong:** The vault format is specific to code-wiki-agent. A future agent for a different domain would need different IO primitives. Premature abstraction creates coupling before the second use case exists.

**Do this instead:** Keep `vault/` inside `agents/code-wiki-agent/`. Promote to a core only if a second agent needs the same vault format.

### Anti-Pattern 4: Importing lattice-wiki-core as a Runtime Dependency

**What people do:** `pip install lattice-wiki-core` and import from it in code-wiki-agent to avoid porting.

**Why it's wrong:** lattice-wiki-core is coupled to `lattice-workspace` path resolution, which is repo-specific. It's a cross-repo, cross-tool-chain dependency that will break in CI and any environment that doesn't have the lattice monorepo checked out at a known path.

**Do this instead:** Port the 6 relevant modules (~800 lines). Strip the `_workspace.py` coupling, replace with `.code-wiki.json` config. One day of work, zero ongoing coupling.

---

## Sources

- uv workspace documentation: https://docs.astral.sh/uv/concepts/projects/workspaces/
- deepagents PyPI (v0.6.1, May 2026): https://pypi.org/project/deepagents/
- deepagents GitHub: https://github.com/langchain-ai/deepagents
- langchain-mcp-adapters: https://github.com/langchain-ai/langchain-mcp-adapters
- FastMCP Python server pattern: https://medium.com/@anoopninangeorge/building-a-remote-mcp-server-a-mcp-client-with-fastmcp-langchain-langgraph-17cf0e8d043b
- ChatBedrock concurrency (ainvoke + asyncio.gather): https://python.langchain.com/api_reference/aws/chat_models/langchain_aws.chat_models.bedrock.ChatBedrock.html
- lattice-wiki-core source: /Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/ (direct inspection)

---

*Architecture research for: deep-agents Python monorepo (code-wiki-agent)*
*Researched: 2026-05-13*
