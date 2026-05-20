<!-- GSD:project-start source:PROJECT.md -->
## Project

**deep-agents**

A Python monorepo (managed with `uv`) of LangChain-primitives-based AI tooling running on AWS Bedrock, with a hand-rolled subagent runtime (`SubagentPool`) instead of a heavier orchestration framework. The first package, **`graph-wiki-agent`**, is a reimplementation of the upstream `lattice-wiki` Claude Code plugin (being ported in this repo as `graph-wiki`) — packaged as both an MCP server (consumed by the DeepAgents CLI) and a headless CLI that runs the full agent loop. It exists primarily so Pat can run the same wiki workflows on AWS Bedrock with within-command subagent fan-out for cost and context savings.

**Core Value:** **Faithfully reproduce the upstream lattice-wiki plugin's wiki-maintenance workflows (now ported as `graph-wiki`) while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.**

If everything else fails, a Bedrock-driven `graph-wiki-agent query "..."` (or the equivalent MCP tool call) must return answers as good as today's upstream lattice-wiki librarian, on cheaper models, faster.

### Constraints

- **Tech stack**: Python 3.11+, `uv` workspace, `langchain-aws` + `langchain-core` + in-house `subagent-runtime` (asyncio.Semaphore-based fan-out). `deepagents`/`langgraph` were evaluated and intentionally not adopted — see §2 stack-departure note
- **Model provider**: AWS Bedrock only in v1 — single-provider focus simplifies adapter layer and eval harness
- **Protocol**: MCP for the primary delivery surface — interoperates with DeepAgents CLI and other MCP hosts
- **Format compatibility**: must read existing upstream lattice-wiki vaults without modification — preserve frontmatter schema, layout block format, wikilink/citation conventions
- **Budget**: personal project; no team; design for one-developer velocity
- **Audience**: Pat (now); open-source-ready hygiene (license, README, no secrets) for later release
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## 1. Monorepo / Packaging — `uv` Workspaces
### Core Tooling
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `uv` | 0.11.14 | Monorepo manager, package installer, lockfile | Replaces pip/poetry/pyenv in one tool; workspace support is first-class and fast; the `uv_build` backend replaces setuptools cleanly |
| Python | 3.11+ | Runtime — floor set by `langchain-core`'s typing usage and the asyncio features `SubagentPool` relies on | uv manages the interpreter automatically via `.python-version` |
### Workspace layout
### Root `pyproject.toml` pattern
### Per-package `pyproject.toml` pattern (e.g., `core-bedrock`)
# No workspace deps here — core-bedrock is a leaf
### Agent package referencing core packages
### Key uv rules
- `[dependency-groups]` (PEP 735) replaces the old `[tool.uv.dev-dependencies]`; use `uv add --group dev <pkg>` for dev-only deps scoped to the workspace root
- All workspace members share a single `uv.lock`; `uv sync` installs everything; `uv sync --package graph-wiki-agent` installs only one member's closure
- Workspace members are always installed as editable; no need to set `editable = true` manually
- Use `uv run --package graph-wiki-agent pytest` to run tests scoped to one member
- `setuptools` or `hatchling` as build backend — `uv_build` is the native backend; it handles the workspace source link correctly
- `poetry` — workspace semantics differ and you lose the lockfile speed advantage
- A flat (single-package) layout — tiered `packages/` + `agents/` is the correct pattern here and matches official uv workspace examples
## 2. Agent Framework — Custom Subagent Runtime over LangChain primitives
### Versions
| Package | Version | Notes |
|---------|---------|-------|
| `langchain-core` | ≥1.4.0 | `@tool` decorator, `HumanMessage`/`SystemMessage`/`ToolMessage`, `RunnableConfig` — the only langchain primitives in use |
| `subagent-runtime` (in-house) | workspace member | `packages/subagent-runtime/` — `SubagentPool` provides asyncio.Semaphore-bounded fan-out; replaces `deepagents.SubAgentMiddleware` |
| `model-adapter` (in-house) | workspace member | `packages/model-adapter/` — `make_llm(role)` returns `_GuardedChatBedrockConverse` (translates `AccessDeniedException` → `BedrockAccessDenied`); models declared in `models.toml` |

**Stack-departure note.** Earlier drafts of this doc proposed `deepagents` + `langgraph` + bare `langchain` as the agent framework. The implementation deliberately diverges: a hand-rolled `SubagentPool` (asyncio + Semaphore) plus a guarded `ChatBedrockConverse` adapter cover this project's needs at a fraction of the surface area. Re-evaluate when (a) checkpoint/resume becomes a real requirement, (b) LangGraph Studio observability becomes worth the dependency, or (c) we need streaming primitives we'd otherwise rebuild.

### How subagent_runtime composes with LangChain
- `subagent_runtime.SubagentPool` accepts a bounded concurrency limit and a factory of `_GuardedChatBedrockConverse` instances built by `model_adapter.make_llm(role)`
- Each subagent receives a tool list of `langchain_core.tools.@tool`-decorated callables
- Orchestrator fans out top-k items to the pool; results are gathered concurrently
- No LangGraph state machine — flow control is plain Python `async`/`await`

### Model specification
- Direct construction via `model_adapter.make_llm(role)` — returns `_GuardedChatBedrockConverse`; bypasses `init_chat_model` to keep the Bedrock guard wrapper in scope
- Per-role tiers (orchestrator/librarian/etc.) defined in `models.toml` as packaged fallback; per-workspace overrides live in `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` and are consumed by `make_llm` automatically. Tests pin a workspace via the `GRAPH_WIKI_WORKSPACE` env var.

### What NOT to use
| Avoid | Why |
|-------|-----|
| `langchain-anthropic` | Routes to the direct Anthropic API. Bedrock-only means `langchain-aws` only. Footgun that will silently route outside Bedrock if credentials are wrong |
| `ChatBedrock` (legacy class) | Deprecated in favor of `ChatBedrockConverse`; the Converse API supports all current Bedrock models uniformly |
| Constructing `ChatBedrockConverse` directly outside `model-adapter` | Loses the `AccessDeniedException` → `BedrockAccessDenied` translation; always go through `make_llm(role)` |
## 3. Bedrock Integration — `langchain-aws`
| Package | Version | Notes |
|---------|---------|-------|
| `langchain-aws` | 1.4.6 | Released 2026-05-04; Python ≥3.10; MIT |
| `boto3` | ≥1.38 | AWS SDK; pulled in transitively; pin to ≥1.38 for Converse API stability |
### ChatBedrockConverse is the right class
# Orchestrator (stronger, slower)
# Subagent role (cheap, fast)
### Async / streaming status
### Multi-model routing
# packages/core-bedrock/src/core_bedrock/models.py
### Token counting for pre-flight estimation
- `tiktoken` — OpenAI-specific BPE tokenizer, does not work with Claude or Bedrock models
- `langchain-anthropic` — direct Anthropic API; excluded by Bedrock-only constraint
- `ChatBedrock` (old class) — use `ChatBedrockConverse` only
## 4. MCP Server SDK — `mcp`
| Package | Version | Notes |
|---------|---------|-------|
| `mcp` | 1.27.1 | Released 2026-05-08; official Anthropic/ModelContextProtocol Python SDK |
### Transport selection
| Transport | Use When | Notes |
|-----------|----------|-------|
| **stdio** | DeepAgents CLI host, Claude Code, Cursor | Standard for local MCP servers consumed by a CLI host process; zero infrastructure |
| **Streamable HTTP** | Remote/multi-client scenarios | The new standard as of protocol version 2025-03-26 |
| ~~SSE~~ | Do not use | **Deprecated** as of MCP spec 2025-03-26; replaced by Streamable HTTP |
### Tool registration pattern (FastMCP)
### Embedding long-running agent loops behind MCP tools
### langchain-mcp-adapters (deferred)
Not currently installed. Would be needed only if the agent itself consumes external MCP servers as tools. The current direction is the inverse — `graph-wiki-agent` *exposes* MCP tools to a host (DeepAgents CLI, Claude Code) via FastMCP, and the host handles inbound tool routing. Revisit if/when the agent grows a need to call out to other MCP servers mid-loop.
- SSE transport — deprecated; don't build new server infrastructure on it
- `FastAPI` + `SSEServerTransport` — the old pattern; use FastMCP's built-in transport instead
- Streamable HTTP in v1 — unnecessary for a local CLI-hosted server
## 5. Eval Framework — `deepeval`
| Package | Version | Notes |
|---------|---------|-------|
| `deepeval` | 4.0.0 | Released 2026-05-08; Apache-2.0; pytest-native |
### Why deepeval wins for this project
| Criterion | deepeval | LangSmith | inspect-ai | Custom pytest |
|-----------|----------|-----------|------------|---------------|
| AWS Bedrock support | Native `AmazonBedrockModel` class | Yes but per-trace pricing | Yes, provider-agnostic | Yes |
| pytest integration | First-class (`assert_test`) | Limited | First-class (`Task`) | First-class |
| Baseline comparison | `GEval` / custom metric | Dataset-based | Scorer-based | DIY |
| Cost tracking per model | `cost_per_input_token` param | Per-trace billing | Token limits/reporting | DIY |
| Per-model config in eval | Yes — pass `model=AmazonBedrockModel(...)` to each metric | No direct per-call model swap | Yes | DIY |
| Price | Free (Apache-2.0) | $1,400+/mo at 500K traces | Free (MIT) | Free |
| Agentic tracing (intermediate steps) | LIMITED in 4.0 | Strong | Strong | None |
### Usage pattern for this project
# packages/core-eval/src/core_eval/harness.py
# In pytest:
### Why not the other candidates
| Candidate | Verdict |
|-----------|---------|
| **LangSmith** | Excellent for LangChain observability but per-trace pricing makes it expensive at eval scale; the eval runner is secondary to its tracing story; lock-in to hosted service |
| **inspect-ai** | Excellent for safety benchmarks and capability evals against standardized datasets (200+ pre-built evals). Wrong fit here: the project needs comparison against a *recorded output baseline*, not a standardized benchmark. inspect-ai's primitives (Task → Solver → Scorer) are designed for that different use case. Use it later for capability regression testing, not for cost-frontier analysis. |
| **promptfoo** | Node.js-first; Python support is a wrapper; adds language-boundary friction in a pure Python monorepo |
| **ragas** | RAG-specific (Retrieval-Augmented Generation); the wiki agent is not a RAG pipeline in the classical sense |
| **Custom pytest only** | Valid escape hatch but requires building cost tracking, baseline storage, and scoring from scratch; deepeval gives this for free |
## 6. CLI / Headless Entry Point — Typer
| Package | Version | Notes |
|---------|---------|-------|
| `typer` | 0.25.1 | Released 2026-04-30; MIT; built on Click; type-hint-driven |
### Pattern
# agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
# in graph-wiki-agent pyproject.toml
- `click` directly — Typer wraps Click and adds type-hint ergonomics; no reason to drop down unless you hit a specific limitation
- `argparse` — verbose and has no auto-help/completion
- `textual` / `rich` in v1 — explicitly out of scope; do not pull it in
## 7. Markdown / Frontmatter / Search
| Package | Version | Notes |
|---------|---------|-------|
| `python-frontmatter` | 1.1.0 | Released 2024-01-16; production/stable; parses YAML/TOML/JSON frontmatter |
| `bm25s` | 0.3.8 | Released 2026-04-29; pure Python + NumPy; 5-10x faster than rank-bm25 |
### Why bm25s over rank-bm25
- Is 5-50x faster on typical corpora (sparse matrix precomputation vs on-demand scoring)
- Supports Okapi BM25, BM25L, BM25+, Lucene variants — the same algorithms rank-bm25 has
- Requires only NumPy as a non-stdlib dependency
### Token counting for context budget
### python-frontmatter usage
- `rank-bm25` — abandoned since 2022
- `tiktoken` — OpenAI-specific tokenizer, wrong for Bedrock/Claude
- Hand-rolled YAML parsing — `python-frontmatter` handles the edge cases (nested frontmatter, encoding, round-trip preservation) better than DIY
## 8. Testing — pytest stack
| Package | Version | Notes |
|---------|---------|-------|
| `pytest` | ≥8.3 | Current stable; no need to pin exact micro |
| `pytest-asyncio` | 1.3.0 | Released 2025-11-10; required for `async def` test functions |
| `syrupy` | 5.1.0 | Released 2026-01-25; snapshot testing plugin; zero external deps |
### pytest-asyncio configuration
### Fake Bedrock responses fixture pattern
# conftest.py
### Snapshot testing pattern (syrupy)
- `pytest-recording` / VCR cassettes for LLM responses — cassettes break whenever the prompt or model changes; mock at the LangChain boundary instead
- `pytest-mock` instead of `unittest.mock` — fine to use either, but `unittest.mock` is stdlib and sufficient
- `anyio` mode in pytest-asyncio — `asyncio_mode = "auto"` is simpler; `anyio` adds overhead without benefit for this stack
## Supporting Libraries Summary
| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| `subagent-runtime` (in-house) | workspace | Asyncio Semaphore-bounded subagent fan-out (`SubagentPool`) | HIGH |
| `model-adapter` (in-house) | workspace | `make_llm(role)` + `_GuardedChatBedrockConverse` adapter | HIGH |
| `langchain-aws` | ≥1.4.6 | Bedrock Converse API binding (`ChatBedrockConverse`, `BedrockEmbeddings`) | HIGH |
| `langchain-core` | ≥1.4.0 | `@tool` decorator + message primitives — only langchain piece in use | HIGH |
| `mcp` | 1.27.1 | MCP server SDK (expose tools to DeepAgents CLI) | HIGH |
| `typer` | 0.25.1 | Headless CLI entry points | HIGH |
| `python-frontmatter` | 1.1.0 | Vault frontmatter read/write | HIGH |
| `bm25s` | 0.3.8 | Wiki index search | HIGH |
| `boto3` | ≥1.38 | Bedrock CountTokens + raw AWS calls | HIGH |
| `deepeval` | 4.0.0 | Per-subagent eval harness | HIGH |
| `pytest` | ≥8.3 | Test runner | HIGH |
| `pytest-asyncio` | 1.3.0 | Async test support | HIGH |
| `syrupy` | 5.1.0 | Snapshot testing | HIGH |
## Installation
# Install uv (if not already)
# Bootstrap the workspace root
# Create core packages
# Create first agent
# Add deps to each package
# Add workspace dev dependencies
# Sync everything
## Alternatives Considered
| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| In-house `SubagentPool` | `deepagents` / `langgraph` | Considered and rejected for v1 — bounded asyncio fan-out is ~150 LOC and avoids dragging in LangGraph state-machine surface area we don't need. Revisit when checkpointing or LangGraph Studio becomes a real requirement (§2 stack-departure note) |
| `langchain-aws` (`ChatBedrockConverse`) | `langchain-anthropic` | Routes to direct Anthropic API — excluded by Bedrock-only constraint; would silently incur non-Bedrock costs |
| `bm25s` | `rank-bm25` | rank-bm25 unmaintained since 2022; bm25s is 5-50x faster with active development |
| `deepeval` | `inspect-ai` | inspect-ai is best for capability benchmarks against standardized datasets; wrong primitive set for "recorded output baseline + cost tracking per model swap" |
| `deepeval` | `langsmith` | Per-trace pricing (~$1,400/mo at scale), hosted service dependency, worse for Bedrock-only stack |
| `typer` | `click` | Typer adds type-hint-driven CLI generation on top of Click; no downside for this use case |
| Bedrock CountTokens API | `tiktoken` | tiktoken is OpenAI-specific BPE; does not work for Claude/Bedrock models |
| stdio MCP transport | SSE transport | SSE is deprecated in MCP spec 2025-03-26; streamable HTTP is the successor but unnecessary for local CLI hosting |
## Version Compatibility Notes
| Constraint | Detail |
|------------|--------|
| Python ≥3.11 floor | Set by `langchain-core` typing usage and `SubagentPool`'s asyncio features |
| langchain-aws ≥1.4.6 requires Python ≥3.10 | Compatible with the ≥3.11 floor |
| ChatBedrockConverse async is pseudo-async | `astream()`/`ainvoke()` wrap sync boto3; no aioboto3 dependency available yet |
| `uv_build` 0.11.x is the workspace-compatible build backend | Lock to `>=0.11.14,<0.12` to avoid breaking changes |
| deepeval 4.0.0 Bedrock metrics use `AmazonBedrockModel` | Requires `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` or IAM role in env |
| mcp 1.27.1 dropped SSE as primary transport | Use `transport="stdio"` for CLI hosting; `transport="streamable-http"` for future remote scenarios |
## Sources
- PyPI: `langchain-aws` 1.4.6 — https://pypi.org/project/langchain-aws/ — current version
- PyPI: `langchain-core` 1.4.0 — https://pypi.org/project/langchain-core/ — current version
- PyPI: `mcp` 1.27.1 — https://pypi.org/project/mcp/ — current version, transport status
- PyPI: `deepeval` 4.0.0 — https://pypi.org/project/deepeval/ — current version
- PyPI: `typer` 0.25.1 — https://pypi.org/project/typer/ — current version
- PyPI: `python-frontmatter` 1.1.0 — https://pypi.org/project/python-frontmatter/ — current version
- PyPI: `bm25s` 0.3.8 — https://pypi.org/project/bm25s/ — current version, performance data
- PyPI: `pytest-asyncio` 1.3.0 — https://pypi.org/project/pytest-asyncio/ — current version
- PyPI: `syrupy` 5.1.0 — https://pypi.org/project/syrupy/ — current version
- GitHub: uv 0.11.14 — https://github.com/astral-sh/uv/releases — current version
- Context7 `/langchain-ai/langchain-aws` — ChatBedrockConverse usage, init_chat_model provider string, token usage metadata
- Context7 `/astral-sh/uv` — workspace pyproject.toml patterns, member declaration, dependency-groups
- DeepEval docs: https://deepeval.com/integrations/models/amazon-bedrock — AmazonBedrockModel API, cost tracking fields
- MCP spec: https://modelcontextprotocol.io/docs/develop/build-server — transport deprecation, stdio pattern
- AWS docs: https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html — CountTokens API
- In-house source: `packages/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool` implementation
- In-house source: `packages/model-adapter/src/model_adapter/loader.py` — `make_llm` + `_GuardedChatBedrockConverse`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

## Spike Findings

- **Spike findings for deep-agents** (implementation patterns, constraints, gotchas) → `Skill("spike-findings-deep-agents")`

## Sketch Findings

- **Sketch findings for deep-agents** (design decisions for `/graph-wiki:refresh` — sweep + targeted modes, autonomous run, hybrid diff doc) → `Skill("sketch-findings-deep-agents")`
