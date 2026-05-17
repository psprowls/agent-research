<!-- GSD:project-start source:PROJECT.md -->
## Project

**deep-agents**

A Python monorepo (managed with `uv`) of LangChain/deepagents-based AI tooling. The first package, **`code-wiki-agent`**, is a reimplementation of the existing `lattice-wiki` Claude Code plugin — packaged as both an MCP server (consumed by the DeepAgents CLI) and a headless CLI that runs the full agent loop. It exists primarily so Pat can run the same wiki workflows on AWS Bedrock with within-command subagent fan-out for cost and context savings.

**Core Value:** **Faithfully reproduce lattice-wiki's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.**

If everything else fails, a Bedrock-driven `code-wiki-agent query "..."` (or the equivalent MCP tool call) must return answers as good as today's lattice-wiki librarian, on cheaper models, faster.

### Constraints

- **Tech stack**: Python 3.11+, `uv` workspace, `langchain` + `langchain-aws` + `deepagents` — chosen to match Pat's stack and to leverage deepagents' subagent primitives without rebuilding them
- **Model provider**: AWS Bedrock only in v1 — single-provider focus simplifies adapter layer and eval harness
- **Protocol**: MCP for the primary delivery surface — interoperates with DeepAgents CLI and other MCP hosts
- **Format compatibility**: must read existing lattice-wiki vaults without modification — preserve frontmatter schema, layout block format, wikilink/citation conventions
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
| Python | 3.11+ | Runtime (3.11 is the floor; deepagents requires `>=3.11`) | deepagents hard-requires 3.11; uv manages the interpreter automatically via `.python-version` |
### Workspace layout
### Root `pyproject.toml` pattern
### Per-package `pyproject.toml` pattern (e.g., `core-bedrock`)
# No workspace deps here — core-bedrock is a leaf
### Agent package referencing core packages
### Key uv rules
- `[dependency-groups]` (PEP 735) replaces the old `[tool.uv.dev-dependencies]`; use `uv add --group dev <pkg>` for dev-only deps scoped to the workspace root
- All workspace members share a single `uv.lock`; `uv sync` installs everything; `uv sync --package code-wiki-agent` installs only one member's closure
- Workspace members are always installed as editable; no need to set `editable = true` manually
- Use `uv run --package code-wiki-agent pytest` to run tests scoped to one member
- `setuptools` or `hatchling` as build backend — `uv_build` is the native backend; it handles the workspace source link correctly
- `poetry` — workspace semantics differ and you lose the lockfile speed advantage
- A flat (single-package) layout — tiered `cores/` + `agents/` is the correct pattern here and matches official uv workspace examples
## 2. Agent Framework — deepagents + LangChain + LangGraph
### Versions
| Package | Version | Notes |
|---------|---------|-------|
| `deepagents` | 0.6.1 | Released 2026-05-12; Python ≥3.11; MIT |
| `langchain` | 1.3.0 | Released 2026-05-12 |
| `langgraph` | 1.2.0 | Released 2026-05-12; deepagents compiles to a LangGraph graph |
| `langchain-core` | 1.4.0 | Required transitively; explicit pin recommended |
### How deepagents composes with LangChain
- Full LangGraph streaming (`astream_events` with `version="v3"`)
- Checkpointers, human-in-the-loop, LangGraph Studio all work unchanged
- Any `langchain_core` `@tool`-decorated function is a valid tool
- The agent works with any LangChain chat model that supports tool calling
### Model specification format
# Direct ChatBedrockConverse (recommended — gives you full regional control)
# OR via init_chat_model (shorter, supports provider string)
### Subagent fan-out / parallelism
### What NOT to use
| Avoid | Why |
|-------|-----|
| LangGraph directly (without deepagents) | You'd rebuild deepagents' built-in tools (filesystem, planning, subagent middleware) from scratch |
| `langchain-anthropic` | This routes to the direct Anthropic API. Bedrock-only means `langchain-aws` only. Adding `langchain-anthropic` is a footgun that will silently route outside Bedrock if credentials are wrong |
| Async subagents (LangGraph Platform) in v1 | Adds infrastructure complexity (remote deployment, thread management) for no gain in a single-developer local setup |
| `ChatBedrock` (legacy class) | Deprecated in favor of `ChatBedrockConverse`; the Converse API supports all current Bedrock models uniformly |
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
# cores/core-bedrock/src/core_bedrock/models.py
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
### langchain-mcp-adapters (for consuming MCP tools inside agents)
| Package | Version | Notes |
|---------|---------|-------|
| `langchain-mcp-adapters` | 0.2.2 | Released 2026-03-16; converts MCP tools to LangChain tools |
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
# cores/core-eval/src/core_eval/harness.py
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
# agents/code-wiki-agent/src/code_wiki_agent/cli.py
# in code-wiki-agent pyproject.toml
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
| `deepagents` | 0.6.1 | Agent framework, subagent fan-out | HIGH |
| `langchain` | 1.3.0 | LLM composition, tool calling | HIGH |
| `langchain-aws` | 1.4.6 | Bedrock Converse API binding | HIGH |
| `langgraph` | 1.2.0 | Durable execution runtime (deepagents dependency) | HIGH |
| `langchain-mcp-adapters` | 0.2.2 | Consume MCP tools inside agents | HIGH |
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
| `deepagents` | LangGraph ReAct directly | Would require reimplementing built-in tools (filesystem, planning, SubAgentMiddleware); deepagents IS LangGraph with batteries |
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
| deepagents ≥0.6.1 requires Python ≥3.11 | Sets the floor for the whole monorepo |
| langchain-aws 1.4.6 requires Python ≥3.10 | Compatible with the ≥3.11 floor |
| ChatBedrockConverse async is pseudo-async | `astream()`/`ainvoke()` wrap sync boto3; no aioboto3 dependency available yet |
| `uv_build` 0.11.x is the workspace-compatible build backend | Lock to `>=0.11.14,<0.12` to avoid breaking changes |
| deepeval 4.0.0 Bedrock metrics use `AmazonBedrockModel` | Requires `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` or IAM role in env |
| mcp 1.27.1 dropped SSE as primary transport | Use `transport="stdio"` for CLI hosting; `transport="streamable-http"` for future remote scenarios |
## Sources
- PyPI: `deepagents` 0.6.1 — https://pypi.org/project/deepagents/ — current version, Python req
- PyPI: `langchain-aws` 1.4.6 — https://pypi.org/project/langchain-aws/ — current version
- PyPI: `langchain` 1.3.0 — https://pypi.org/project/langchain/ — current version
- PyPI: `langgraph` 1.2.0 — https://pypi.org/project/langgraph/ — current version
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
- GitHub deepwiki: SubAgentMiddleware — https://deepwiki.com/langchain-ai/deepagents/8.4-sub-agent-workflows — sync vs async subagents, per-role model config
- DeepEval docs: https://deepeval.com/integrations/models/amazon-bedrock — AmazonBedrockModel API, cost tracking fields
- MCP spec: https://modelcontextprotocol.io/docs/develop/build-server — transport deprecation, stdio pattern
- AWS docs: https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html — CountTokens API
- deepagents docs: https://docs.langchain.com/oss/python/deepagents/overview — model format, primitives
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
