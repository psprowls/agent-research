# Stack Research

**Domain:** Python LangChain/deepagents MCP-server agents on AWS Bedrock, uv monorepo
**Researched:** 2026-05-13
**Confidence:** HIGH (most picks verified against PyPI, official docs, or Context7 as of this date)

---

## 1. Monorepo / Packaging — `uv` Workspaces

### Core Tooling

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `uv` | 0.11.14 | Monorepo manager, package installer, lockfile | Replaces pip/poetry/pyenv in one tool; workspace support is first-class and fast; the `uv_build` backend replaces setuptools cleanly |
| Python | 3.11+ | Runtime (3.11 is the floor; deepagents requires `>=3.11`) | deepagents hard-requires 3.11; uv manages the interpreter automatically via `.python-version` |

**Confidence:** HIGH — uv 0.11.14 released 2026-05-12; deepagents PyPI page lists `>=3.11` as requirement.

### Workspace layout

```
agent-research/                        ← uv workspace root (no runtime code)
  pyproject.toml                    ← [tool.uv.workspace] + shared dev deps
  uv.lock                           ← single lockfile for whole monorepo
  packages/
    core-bedrock/                   ← shared: Bedrock adapter, multi-model routing
    core-subagent/                  ← shared: deepagents wrapper, fan-out helpers
    core-eval/                      ← shared: eval harness, baseline recorder
  agents/
    graph-wiki-agent/                ← first agent: MCP server + headless CLI
```

### Root `pyproject.toml` pattern

```toml
[project]
name = "agent-research-workspace"
version = "0.1.0"
requires-python = ">=3.11"

[tool.uv.workspace]
members = ["packages/*", "agents/*"]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=1.3",
    "syrupy>=5.1",
    "ruff>=0.9",
    "pyright>=1.1",
]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"
```

### Per-package `pyproject.toml` pattern (e.g., `core-bedrock`)

```toml
[project]
name = "core-bedrock"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "langchain-aws>=1.4.6",
    "boto3>=1.38",
]

[tool.uv.sources]
# No workspace deps here — core-bedrock is a leaf

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"
```

### Agent package referencing core packages

```toml
[project]
name = "graph-wiki-agent"
dependencies = [
    "core-bedrock",
    "core-subagent",
    "langchain-aws>=1.4.6",
    "deepagents>=0.6.1",
    "mcp>=1.27.1",
    "typer>=0.25.1",
    "python-frontmatter>=1.1.0",
    "bm25s>=0.3.8",
]

[tool.uv.sources]
core-bedrock = { workspace = true }
core-subagent = { workspace = true }
```

### Key uv rules

- `[dependency-groups]` (PEP 735) replaces the old `[tool.uv.dev-dependencies]`; use `uv add --group dev <pkg>` for dev-only deps scoped to the workspace root
- All workspace members share a single `uv.lock`; `uv sync` installs everything; `uv sync --package graph-wiki-agent` installs only one member's closure
- Workspace members are always installed as editable; no need to set `editable = true` manually
- Use `uv run --package graph-wiki-agent pytest` to run tests scoped to one member

**What NOT to use:**
- `setuptools` or `hatchling` as build backend — `uv_build` is the native backend; it handles the workspace source link correctly
- `poetry` — workspace semantics differ and you lose the lockfile speed advantage
- A flat (single-package) layout — tiered `packages/` + `agents/` is the correct pattern here and matches official uv workspace examples

---

## 2. Agent Framework — deepagents + LangChain + LangGraph

### Versions

| Package | Version | Notes |
|---------|---------|-------|
| `deepagents` | 0.6.1 | Released 2026-05-12; Python ≥3.11; MIT |
| `langchain` | 1.3.0 | Released 2026-05-12 |
| `langgraph` | 1.2.0 | Released 2026-05-12; deepagents compiles to a LangGraph graph |
| `langchain-core` | 1.4.0 | Required transitively; explicit pin recommended |

**Confidence:** HIGH — all versions verified against PyPI 2026-05-13.

### How deepagents composes with LangChain

`create_deep_agent(model, tools, system_prompt)` returns a **compiled LangGraph graph**. This means:
- Full LangGraph streaming (`astream_events` with `version="v3"`)
- Checkpointers, human-in-the-loop, LangGraph Studio all work unchanged
- Any `langchain_core` `@tool`-decorated function is a valid tool
- The agent works with any LangChain chat model that supports tool calling

### Model specification format

deepagents uses `init_chat_model` under the hood. For Bedrock, the format is:

```python
# Direct ChatBedrockConverse (recommended — gives you full regional control)
from langchain_aws import ChatBedrockConverse

model = ChatBedrockConverse(
    model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name="us-west-2",
)

# OR via init_chat_model (shorter, supports provider string)
from langchain.chat_models import init_chat_model

model = init_chat_model(
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    model_provider="bedrock_converse",
    region_name="us-west-2",
)
```

The `provider:model-name` shorthand used in deepagents' own docs (e.g., `"openai:gpt-4o"`) does **not** work for Bedrock — Bedrock requires `model_provider="bedrock_converse"` and a full model ID. Instantiate `ChatBedrockConverse` directly and pass it as the `model` arg to `create_deep_agent`.

### Subagent fan-out / parallelism

deepagents provides the `task` tool via `SubAgentMiddleware`. Two patterns:

**Synchronous (in-process, blocking per task but parallel via LLM multi-tool-call):**
```python
from deepagents import create_deep_agent
from deepagents.middleware import SubAgentMiddleware

scanner_agent = {
    "name": "package_scanner",
    "model": ChatBedrockConverse(model="us.anthropic.claude-haiku-4-5-...", ...),
    "description": "Scans one package directory and returns a stub report",
    "system_prompt": "...",
}

middleware = SubAgentMiddleware(
    backend=backend,
    subagents=[scanner_agent],
)

parent = create_deep_agent(
    model=ChatBedrockConverse(model="us.anthropic.claude-sonnet-4-5-...", ...),
    tools=[...],
    middleware=[middleware],
)
```

When the parent LLM issues **multiple `task` tool calls in a single step**, deepagents launches those subagents concurrently (LangGraph superstep). This is the mechanism for within-command fan-out: scanner calling `task("package_scanner", pkg_a)` and `task("package_scanner", pkg_b)` in a single tool-call batch runs both in parallel.

**Async (remote, non-blocking):** Uses `start_async_task` + `check_async_task`. Requires LangGraph Platform (remote deployment). Not needed for v1 — stay with sync subagents running in-process.

**Per-role model assignment:** Each entry in `subagents` takes its own `model` field. This is the primary mechanism for routing cheap models (Haiku) to fast subagents and stronger models (Sonnet) to the parent orchestrator.

### What NOT to use

| Avoid | Why |
|-------|-----|
| LangGraph directly (without deepagents) | You'd rebuild deepagents' built-in tools (filesystem, planning, subagent middleware) from scratch |
| `langchain-anthropic` | This routes to the direct Anthropic API. Bedrock-only means `langchain-aws` only. Adding `langchain-anthropic` is a footgun that will silently route outside Bedrock if credentials are wrong |
| Async subagents (LangGraph Platform) in v1 | Adds infrastructure complexity (remote deployment, thread management) for no gain in a single-developer local setup |
| `ChatBedrock` (legacy class) | Deprecated in favor of `ChatBedrockConverse`; the Converse API supports all current Bedrock models uniformly |

---

## 3. Bedrock Integration — `langchain-aws`

| Package | Version | Notes |
|---------|---------|-------|
| `langchain-aws` | 1.4.6 | Released 2026-05-04; Python ≥3.10; MIT |
| `boto3` | ≥1.38 | AWS SDK; pulled in transitively; pin to ≥1.38 for Converse API stability |

**Confidence:** HIGH — version verified against PyPI 2026-05-13.

### ChatBedrockConverse is the right class

`ChatBedrockConverse` wraps the Bedrock **Converse API**, which provides a unified interface across all Bedrock models (Claude, Nova, Llama, Mistral, Titan). Use it for all model calls — it handles tool calling, streaming, structured output, and token usage metadata consistently.

```python
from langchain_aws import ChatBedrockConverse

# Orchestrator (stronger, slower)
orchestrator = ChatBedrockConverse(
    model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name="us-west-2",
    temperature=0,
    max_tokens=4096,
)

# Subagent role (cheap, fast)
scanner = ChatBedrockConverse(
    model="us.anthropic.claude-haiku-4-5-20251201-v1:0",
    region_name="us-west-2",
    temperature=0,
)
```

### Async / streaming status

`ChatBedrockConverse.astream()` and `ainvoke()` exist but **wrap synchronous boto3** — they are not truly async (no aioboto3). An open enhancement request (langchain-aws#663, filed Sep 2025) asks for native aioboto3 support. For v1, this is acceptable: the deepagents event loop is CPU-bound enough that true async IO isn't the bottleneck.

Token usage is returned in `response.usage_metadata` after every `.invoke()` / `.stream()` call. No extra library needed for cost accounting — just accumulate `usage_metadata.input_tokens` and `usage_metadata.output_tokens` per model call.

### Multi-model routing

Instantiate one `ChatBedrockConverse` per subagent role and assign them at construction time. The `core-bedrock` package should export a factory:

```python
# packages/core-bedrock/src/core_bedrock/models.py
from langchain_aws import ChatBedrockConverse

def make_model(model_id: str, region: str = "us-west-2", **kwargs) -> ChatBedrockConverse:
    return ChatBedrockConverse(model=model_id, region_name=region, temperature=0, **kwargs)

HAIKU = "us.anthropic.claude-haiku-4-5-20251201-v1:0"
SONNET = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
NOVA_MICRO = "us.amazon.nova-micro-v1:0"
NOVA_LITE = "us.amazon.nova-lite-v1:0"
```

### Token counting for pre-flight estimation

Use the Bedrock native `count_tokens` API (zero-cost call) via boto3 directly — no third-party library needed:

```python
import boto3

client = boto3.client("bedrock-runtime", region_name="us-west-2")
response = client.count_tokens(
    modelId="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    messages=[{"role": "user", "content": [{"text": "..."}]}],
)
token_count = response["tokenCount"]
```

**What NOT to use:**
- `tiktoken` — OpenAI-specific BPE tokenizer, does not work with Claude or Bedrock models
- `langchain-anthropic` — direct Anthropic API; excluded by Bedrock-only constraint
- `ChatBedrock` (old class) — use `ChatBedrockConverse` only

---

## 4. MCP Server SDK — `mcp`

| Package | Version | Notes |
|---------|---------|-------|
| `mcp` | 1.27.1 | Released 2026-05-08; official Anthropic/ModelContextProtocol Python SDK |

**Confidence:** HIGH — version verified against PyPI 2026-05-13.

### Transport selection

| Transport | Use When | Notes |
|-----------|----------|-------|
| **stdio** | DeepAgents CLI host, Claude Code, Cursor | Standard for local MCP servers consumed by a CLI host process; zero infrastructure |
| **Streamable HTTP** | Remote/multi-client scenarios | The new standard as of protocol version 2025-03-26 |
| ~~SSE~~ | Do not use | **Deprecated** as of MCP spec 2025-03-26; replaced by Streamable HTTP |

For `graph-wiki-agent`, **stdio is correct for v1**. The DeepAgents CLI spawns the MCP server as a subprocess over stdin/stdout. No network server needed.

### Tool registration pattern (FastMCP)

```python
from mcp.server.fastmcp import FastMCP
import asyncio

mcp = FastMCP("graph-wiki-agent")

@mcp.tool()
async def query(question: str, vault_path: str) -> str:
    """Search the wiki vault and synthesize an answer."""
    # Run the full agent loop here — this is a long-running operation
    result = await run_query_agent(question, vault_path)
    return result

@mcp.tool()
async def scan(repo_path: str, vault_path: str) -> str:
    """Scan repo packages and update wiki stubs."""
    result = await run_scan_agent(repo_path, vault_path)
    return result

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Embedding long-running agent loops behind MCP tools

The `@mcp.tool()` function simply awaits the agent graph. The MCP SDK holds the connection open for the duration. For stdio transport, the host process (DeepAgents CLI) will wait for the tool to return — there is no timeout imposed by the SDK itself. This is the correct pattern; no special streaming-to-MCP bridge is needed for v1.

For future streaming progress updates to the MCP host, use `mcp.server.fastmcp.Context` to send progress notifications while the agent runs. This is optional in v1.

### langchain-mcp-adapters (for consuming MCP tools inside agents)

| Package | Version | Notes |
|---------|---------|-------|
| `langchain-mcp-adapters` | 0.2.2 | Released 2026-03-16; converts MCP tools to LangChain tools |

Use this when `graph-wiki-agent` itself needs to call *other* MCP servers as tools (e.g., a future filesystem MCP server). Not needed for the server-side MCP exposure.

**What NOT to use:**
- SSE transport — deprecated; don't build new server infrastructure on it
- `FastAPI` + `SSEServerTransport` — the old pattern; use FastMCP's built-in transport instead
- Streamable HTTP in v1 — unnecessary for a local CLI-hosted server

---

## 5. Eval Framework — `deepeval`

**Recommendation: `deepeval` 4.0.0 + pytest**

| Package | Version | Notes |
|---------|---------|-------|
| `deepeval` | 4.0.0 | Released 2026-05-08; Apache-2.0; pytest-native |

**Confidence:** HIGH — version verified against PyPI 2026-05-13.

### Why deepeval wins for this project

The selection criterion is: "swap model, replay query, score against baseline output, produce cost-vs-quality chart."

| Criterion | deepeval | LangSmith | inspect-ai | Custom pytest |
|-----------|----------|-----------|------------|---------------|
| AWS Bedrock support | Native `AmazonBedrockModel` class | Yes but per-trace pricing | Yes, provider-agnostic | Yes |
| pytest integration | First-class (`assert_test`) | Limited | First-class (`Task`) | First-class |
| Baseline comparison | `GEval` / custom metric | Dataset-based | Scorer-based | DIY |
| Cost tracking per model | `cost_per_input_token` param | Per-trace billing | Token limits/reporting | DIY |
| Per-model config in eval | Yes — pass `model=AmazonBedrockModel(...)` to each metric | No direct per-call model swap | Yes | DIY |
| Price | Free (Apache-2.0) | $1,400+/mo at 500K traces | Free (MIT) | Free |
| Agentic tracing (intermediate steps) | LIMITED in 4.0 | Strong | Strong | None |

deepeval is the only option that has native Bedrock support, per-metric model configuration, cost tracking fields, AND pytest integration out of the box. It runs entirely locally — no hosted service required.

### Usage pattern for this project

```python
# packages/core-eval/src/core_eval/harness.py
from deepeval.models import AmazonBedrockModel
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase

def make_bedrock_judge(model_id: str) -> AmazonBedrockModel:
    return AmazonBedrockModel(
        model=model_id,
        region="us-west-2",
        cost_per_input_token=0.000003,   # fill in per-model pricing
        cost_per_output_token=0.000015,
    )

# In pytest:
def test_query_sonnet_vs_baseline(baseline_corpus):
    for example in baseline_corpus:
        actual = run_query_agent(example.question, model=SONNET)
        test_case = LLMTestCase(
            input=example.question,
            actual_output=actual,
            expected_output=example.baseline_answer,
        )
        metric = GEval(
            name="Answer Quality",
            criteria="Does the actual answer cover all key facts from the expected answer?",
            model=make_bedrock_judge("us.anthropic.claude-haiku-4-5-..."),
        )
        assert_test(test_case, [metric])
```

### Why not the other candidates

| Candidate | Verdict |
|-----------|---------|
| **LangSmith** | Excellent for LangChain observability but per-trace pricing makes it expensive at eval scale; the eval runner is secondary to its tracing story; lock-in to hosted service |
| **inspect-ai** | Excellent for safety benchmarks and capability evals against standardized datasets (200+ pre-built evals). Wrong fit here: the project needs comparison against a *recorded output baseline*, not a standardized benchmark. inspect-ai's primitives (Task → Solver → Scorer) are designed for that different use case. Use it later for capability regression testing, not for cost-frontier analysis. |
| **promptfoo** | Node.js-first; Python support is a wrapper; adds language-boundary friction in a pure Python monorepo |
| **ragas** | RAG-specific (Retrieval-Augmented Generation); the wiki agent is not a RAG pipeline in the classical sense |
| **Custom pytest only** | Valid escape hatch but requires building cost tracking, baseline storage, and scoring from scratch; deepeval gives this for free |

---

## 6. CLI / Headless Entry Point — Typer

| Package | Version | Notes |
|---------|---------|-------|
| `typer` | 0.25.1 | Released 2026-04-30; MIT; built on Click; type-hint-driven |

**Confidence:** HIGH — version verified against PyPI 2026-05-13.

### Pattern

```python
# agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
import typer
import asyncio

app = typer.Typer()

@app.command()
def query(
    question: str = typer.Argument(...),
    vault: str = typer.Option("./wiki", help="Path to wiki vault"),
    model: str = typer.Option("sonnet", help="Model role: haiku|sonnet|nova-lite"),
):
    """Search the wiki and return an answer."""
    result = asyncio.run(run_query_agent(question, vault, model))
    typer.echo(result)

if __name__ == "__main__":
    app()
```

The MCP server entrypoint is a separate script:

```toml
# in graph-wiki-agent pyproject.toml
[project.scripts]
graph-wiki-agent = "graph_wiki_agent.cli:app"
graph-wiki-agent-mcp = "graph_wiki_agent.mcp_server:main"
```

**What NOT to use:**
- `click` directly — Typer wraps Click and adds type-hint ergonomics; no reason to drop down unless you hit a specific limitation
- `argparse` — verbose and has no auto-help/completion
- `textual` / `rich` in v1 — explicitly out of scope; do not pull it in

---

## 7. Markdown / Frontmatter / Search

| Package | Version | Notes |
|---------|---------|-------|
| `python-frontmatter` | 1.1.0 | Released 2024-01-16; production/stable; parses YAML/TOML/JSON frontmatter |
| `bm25s` | 0.3.8 | Released 2026-04-29; pure Python + NumPy; 5-10x faster than rank-bm25 |

**Confidence:** HIGH for python-frontmatter (stable, widely used); HIGH for bm25s (active, verified on PyPI).

### Why bm25s over rank-bm25

`rank-bm25` 0.2.2 was last released 2022-02-16 and is effectively unmaintained. `bm25s` is an actively developed drop-in replacement that:
- Is 5-50x faster on typical corpora (sparse matrix precomputation vs on-demand scoring)
- Supports Okapi BM25, BM25L, BM25+, Lucene variants — the same algorithms rank-bm25 has
- Requires only NumPy as a non-stdlib dependency

The existing `lattice-wiki-core` BM25 implementation is hand-rolled stdlib. For the rewrite, `bm25s` is the right pick: fast, correct, drop-in, maintained.

### Token counting for context budget

Do not use `tiktoken` (OpenAI-specific). Use the Bedrock `count_tokens` API (boto3) as described in section 3. For approximate in-process counting without an API call, the `anthropic` Python SDK has a `count_tokens` utility — but that requires the direct Anthropic API key, which is excluded by the Bedrock-only constraint. Use the Bedrock CountTokens API; it is zero-cost.

### python-frontmatter usage

```python
import frontmatter

post = frontmatter.load("packages/my-package.md")
print(post.metadata["category"])  # YAML frontmatter
print(post.content)               # body text
```

The lattice-wiki frontmatter schema (category, tags, layout block) is fully compatible — `python-frontmatter` preserves key order and round-trips YAML faithfully.

**What NOT to use:**
- `rank-bm25` — abandoned since 2022
- `tiktoken` — OpenAI-specific tokenizer, wrong for Bedrock/Claude
- Hand-rolled YAML parsing — `python-frontmatter` handles the edge cases (nested frontmatter, encoding, round-trip preservation) better than DIY

---

## 8. Testing — pytest stack

| Package | Version | Notes |
|---------|---------|-------|
| `pytest` | ≥8.3 | Current stable; no need to pin exact micro |
| `pytest-asyncio` | 1.3.0 | Released 2025-11-10; required for `async def` test functions |
| `syrupy` | 5.1.0 | Released 2026-01-25; snapshot testing plugin; zero external deps |

**Confidence:** HIGH — all versions verified.

### pytest-asyncio configuration

In the workspace root `pyproject.toml` (applies to all members):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"           # marks all async test functions automatically
testpaths = ["packages", "agents"]
```

### Fake Bedrock responses fixture pattern

Do not mock boto3 at the network layer — mock `ChatBedrockConverse` at the LangChain boundary:

```python
# conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

@pytest.fixture
def fake_bedrock_model():
    model = MagicMock()
    model.invoke = MagicMock(return_value=AIMessage(
        content="mocked response",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    ))
    model.ainvoke = AsyncMock(return_value=AIMessage(
        content="mocked async response",
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    ))
    return model
```

This is cheaper and more stable than VCR/cassette-based HTTP mocking for LLM responses.

### Snapshot testing pattern (syrupy)

Use syrupy for vault output regression tests — e.g., assert that `scan` produces the expected stub file content:

```python
def test_scan_creates_stub(snapshot, tmp_vault, fake_bedrock_model):
    run_scan(tmp_vault, model=fake_bedrock_model)
    stub = (tmp_vault / "packages/my-pkg.md").read_text()
    assert stub == snapshot
```

Snapshots stored as `.ambr` files alongside tests; committed to git; updated with `pytest --snapshot-update`.

**What NOT to use:**
- `pytest-recording` / VCR cassettes for LLM responses — cassettes break whenever the prompt or model changes; mock at the LangChain boundary instead
- `pytest-mock` instead of `unittest.mock` — fine to use either, but `unittest.mock` is stdlib and sufficient
- `anyio` mode in pytest-asyncio — `asyncio_mode = "auto"` is simpler; `anyio` adds overhead without benefit for this stack

---

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

---

## Installation

```bash
# Install uv (if not already)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Bootstrap the workspace root
uv init --bare agent-research
cd agent-research

# Create core packages
uv init --package packages/core-bedrock
uv init --package packages/core-subagent
uv init --package packages/core-eval

# Create first agent
uv init --package agents/graph-wiki-agent

# Add deps to each package
uv add --package core-bedrock "langchain-aws>=1.4.6" "boto3>=1.38"
uv add --package core-subagent "deepagents>=0.6.1" "langgraph>=1.2.0" "langchain>=1.3.0"
uv add --package core-eval "deepeval>=4.0.0"
uv add --package graph-wiki-agent \
    "mcp>=1.27.1" "typer>=0.25.1" \
    "python-frontmatter>=1.1.0" "bm25s>=0.3.8" \
    "langchain-mcp-adapters>=0.2.2"

# Add workspace dev dependencies
uv add --group dev "pytest>=8.3" "pytest-asyncio>=1.3" "syrupy>=5.1" "ruff>=0.9" "pyright>=1.1"

# Sync everything
uv sync
```

---

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

---

## Version Compatibility Notes

| Constraint | Detail |
|------------|--------|
| deepagents ≥0.6.1 requires Python ≥3.11 | Sets the floor for the whole monorepo |
| langchain-aws 1.4.6 requires Python ≥3.10 | Compatible with the ≥3.11 floor |
| ChatBedrockConverse async is pseudo-async | `astream()`/`ainvoke()` wrap sync boto3; no aioboto3 dependency available yet |
| `uv_build` 0.11.x is the workspace-compatible build backend | Lock to `>=0.11.14,<0.12` to avoid breaking changes |
| deepeval 4.0.0 Bedrock metrics use `AmazonBedrockModel` | Requires `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` or IAM role in env |
| mcp 1.27.1 dropped SSE as primary transport | Use `transport="stdio"` for CLI hosting; `transport="streamable-http"` for future remote scenarios |

---

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

---
*Stack research for: Python LangChain/deepagents MCP-server agents on AWS Bedrock, uv monorepo*
*Researched: 2026-05-13*
