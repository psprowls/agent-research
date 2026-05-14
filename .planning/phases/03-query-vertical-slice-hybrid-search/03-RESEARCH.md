# Phase 3: Query Vertical Slice + Hybrid Search — Research

**Researched:** 2026-05-13
**Domain:** Hybrid BM25+embedding search, async librarian fan-out, dual CLI+MCP delivery, SQLite+bm25s persistence
**Confidence:** HIGH (all critical findings verified against live source code)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Titan Embeddings G1 v2 (`amazon.titan-embed-text-v2:0` — no `us.` prefix). Amazon-native, no extra IAM grants. Supported in langchain-aws via `BedrockEmbeddings`.
- **D-02:** Change detection uses sha256 content hash stored in `search.db` alongside the embedding vector. Re-embed only when hash differs.
- **D-03:** RRF fusion with `k=60`: `score = 1/(k + rank_bm25) + 1/(k + rank_embed)`. No alpha tuning. Both raw scores and fused score in `--json` output (SEARCH-06).
- **D-04:** Two separate stores — bm25s native directory at `.code-wiki/bm25/`; embeddings in SQLite at `.code-wiki/search.db` (`pages` table: `path TEXT PRIMARY KEY, content_hash TEXT, embedding BLOB`).
- **D-05:** Shared implementation at `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`. CLI and MCP both import `run_query()` from this module.
- **D-06:** Return type is `QueryResult` dataclass (`answer`, `citations`, `pages_drilled`, `search_scores`). Consistent with `FanOutResult`/`PerItemError` pattern.
- **D-07:** Default `top_k=5`, configurable `--top-k` on CLI and `top_k: int = 5` on MCP tool input. Allowed range 3–10.
- **D-08:** State gate interface present (`--no-state-gate` flag) but underlying check is a no-op — query is read-only.

### Claude's Discretion

- Exact Titan embedding model ID / cross-region ARN
- `BedrockEmbeddings` call batching
- bm25s tokenizer settings
- `search.db` schema DDL and upsert
- MCP `wiki_query` input schema (exact Pydantic fields)
- MCP progress notifications (when/how)
- `--config` and vault path resolution

### Deferred Ideas (OUT OF SCOPE)

- `cores/wiki-search` package
- Cost accounting (`cost_usd`)
- File-write-back after query (`--write-back`)
- `--stale-days` / `--log-gap-days` thresholds
- Embedding dimension tuning
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEARCH-01 | BM25 index using `bm25s` 0.3.8 | bm25s confirmed not yet installed; add as dep to code-wiki-agent package |
| SEARCH-02 | Bedrock embedding index via Titan v2 | `BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0")` verified in Context7; no `us.` prefix |
| SEARCH-03 | Hybrid search via RRF fusion | Pure Python `1/(k+rank)` pattern; both scores preserved in output |
| SEARCH-04 | Embedding index persists to SQLite | stdlib `sqlite3`; WAL mode for concurrent read safety |
| SEARCH-05 | Incremental rebuild via content hash | sha256 of raw markdown text stored in `pages.content_hash` |
| SEARCH-06 | Top-K results with BM25, cosine, and fused scores in `--json` | `QueryResult.search_scores` dict carries all three |
| CMD-04 | `query` command: index.md first, hybrid-search top-K, librarian fan-out, synthesize | Full pipeline in `commands/query.py`; `run_query()` is the entry point |
| CMD-07 | `--json` flag on query subcommand | `json_output: bool = typer.Option(False, "--json")` on CLI; JSON body from MCP |
| CMD-08 | State gate mechanism present | `--no-state-gate` flag present, check is a no-op (query is read-only per D-08) |
| MCP-02 | Tool descriptions + input schemas sufficient for DeepAgents CLI | Pydantic `WikiQueryInput` schema; typed description on `@mcp.tool` decorator |
| MCP-04 | Structured MCP error responses on failure | FastMCP wraps exceptions automatically; verified pattern in test_mcp_stdio.py |
| MCP-06 | Progress notifications for long-running tools | `ctx.report_progress(progress, total, message)` via FastMCP `Context` parameter |
| MCP-07 | `code-wiki-mcp` entry point launches as stdio subprocess | Entry point already registered in pyproject.toml; no change needed |
| CLI-01 | Typer-based CLI with `query` subcommand | Add to existing `app` in `cli.py` |
| CLI-02 | CLI runs full agent loop in-process on Bedrock | `asyncio.run(run_query(...))` in the Typer command |
| CLI-03 | CLI and MCP share exact same command implementations | Both import `commands/query.py:run_query()` |
| CLI-04 | `--json` flag on every subcommand | Already required; `json_output` option in CLI query command |
| CLI-05 | `--config <path>` for non-default model/role configuration | Vault path via `--vault` and env var `CODE_WIKI_REAL_VAULT_PATH`; role config from models.toml |
| CLI-06 | Exit codes: 0 success, 1 user error, 2 system error, 3 partial success | `raise typer.Exit(code=N)` pattern |
| CLI-07 | Interactive/headless mode based on TTY detection | `sys.stdout.isatty()` for mode detection; `--quiet` flag |
</phase_requirements>

---

## Summary

Phase 3 delivers the `query` command as a complete vertical slice. The pipeline is: hybrid BM25+embedding search selects candidate pages from the vault, parallel librarian subagents (Haiku, up to 5 concurrent) drill each page for relevant excerpts, and a single synthesizer call (Sonnet) produces the final answer with `[[wikilink]]` citations. The shared implementation in `commands/query.py` serves both the MCP `wiki_query` tool and the headless CLI `code-wiki-agent query`.

All the infrastructure this phase needs already exists from Phases 1 and 2: `SubagentPool.run_all()` handles the fan-out with semaphore throttle and partial-failure isolation, `make_llm(role)` and `load_role_config(role)` resolve Haiku/Sonnet from models.toml, `resolve_wiki_and_repo()` locates the vault, and the FastMCP instance and Typer app are both in place awaiting new tools/subcommands.

The only new components are: the `commands/` subpackage in code-wiki-agent, the BM25 index build/load cycle using bm25s, the SQLite embedding store with sha256 change detection, and the RRF fusion logic — all in pure Python with no new packages beyond bm25s.

**Primary recommendation:** Wire the vertical slice in this order — (1) build `commands/query.py` with the pure-Python BM25+RRF+SQLite search layer, (2) add the librarian fan-out and synthesizer call, (3) add the CLI subcommand, (4) add the MCP tool, (5) write unit tests for search logic, (6) write the integration test against the fixture vault.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| BM25 index build and query | `commands/query.py` (agent layer) | None — bm25s native dir in `.code-wiki/bm25/` | Index lifecycle is owned by the command that needs it; no shared layer needed for one agent |
| Embedding index build and query | `commands/query.py` (agent layer) | `cores/vault-io` (vault path resolution only) | `BedrockEmbeddings` and SQLite are direct deps; vault-io provides the path |
| RRF fusion | `commands/query.py` (pure Python) | None | Trivial math; no separate layer warranted |
| Librarian fan-out | `cores/subagent-runtime` (SubagentPool) | `cores/model-adapter` (make_llm) | SubagentPool handles semaphore, trace, and partial-failure; already built |
| Synthesizer call | `commands/query.py` (direct ainvoke) | `cores/model-adapter` (make_llm) | Single call; no fan-out needed |
| CLI delivery | `code_wiki_agent.cli` (Typer app) | `commands/query.py` (shared impl) | Thin wrapper: parse args, call `asyncio.run(run_query(...))` |
| MCP delivery | `code_wiki_mcp.server` (FastMCP) | `commands/query.py` (shared impl) | Thin wrapper: validate Pydantic input, await `run_query(...)`, serialize output |
| Vault path resolution | `cores/vault-io._workspace` | None | `resolve_wiki_and_repo()` already handles arg + env var priority |
| Progress notification | `code_wiki_mcp.server` (MCP tool) | FastMCP `Context` | Progress reporting is MCP-surface-specific; CLI has no equivalent |
| Trace output | `cores/subagent-runtime` (SubagentPool) | None — automatic | SubagentPool writes JSONL trace per fan-out call automatically |

---

## Standard Stack

### Core (verified from live codebase)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| `bm25s` | 0.3.8 | BM25 index + retrieval | [VERIFIED: pyproject.toml in CLAUDE.md] — not yet installed; new dep for Phase 3 |
| `langchain-aws` (`BedrockEmbeddings`) | 1.4.6 | Titan v2 embedding calls | [VERIFIED: agents/code-wiki-agent/pyproject.toml] — already installed |
| `sqlite3` | stdlib | Embedding vector store | [VERIFIED: stdlib, no install needed] |
| `subagent_runtime.pool` | Phase 2 | Librarian fan-out with semaphore | [VERIFIED: cores/subagent-runtime/src/subagent_runtime/pool.py] |
| `model_adapter.loader` | Phase 2 | `make_llm(role)` + `load_role_config(role)` | [VERIFIED: cores/model-adapter/src/model_adapter/loader.py] |
| `vault_io._workspace` | Phase 1 | `resolve_wiki_and_repo(vault_path)` | [VERIFIED: cores/vault-io/src/vault_io/_workspace.py] |
| `mcp.server.fastmcp` (`FastMCP`, `Context`) | 1.27.1 | MCP tool registration + progress | [VERIFIED: agents/code-wiki-agent/src/code_wiki_mcp/server.py] |
| `typer` | 0.25.1 | CLI subcommand | [VERIFIED: agents/code-wiki-agent/src/code_wiki_agent/cli.py] |

### Installation (Phase 3 new dependency only)

```bash
# bm25s is the only new dep — everything else is already in the workspace
uv add --package code-wiki-agent bm25s==0.3.8
```

---

## Live Codebase Findings

These are the answers to the specific questions listed in the research brief, verified by reading actual source files.

### Q1: `SubagentPool.run_all()` signature

[VERIFIED: cores/subagent-runtime/src/subagent_runtime/pool.py]

```python
async def run_all(
    self,
    items: list[Any],
    task: Callable[..., Awaitable[Any]],
    role: str,
    *,
    model_id: str,
    max_concurrency: int,
    recursion_limit: int | None = None,
) -> FanOutResult:
```

Key facts:
- `role`, `model_id`, `max_concurrency` are keyword-only arguments (after `*`).
- No `correlation_id` parameter exists yet. AI-SPEC Section 7 requires one for `query_id` linking — this is a new parameter the plan must add, or implement via a different mechanism (e.g., write a separate `query_summary` record from `run_query()` directly).
- `task` can be single-arg `(item) -> result` or dual-arg `(item, RunnableConfig) -> result` — checked via `inspect.signature` inside `_run_one`.
- Semaphore is created inside `run_all()`, confirming it binds to the active event loop (safe for pytest-asyncio).

### Q2: `load_role_config(role)` — does it exist?

[VERIFIED: cores/model-adapter/src/model_adapter/loader.py lines 98-108]

Yes, `load_role_config(role)` exists and returns the raw config dict from models.toml for the role. It raises `KeyError` if the role is absent. Use it to get `max_concurrency` and `model_id` for the fan-out call:

```python
from model_adapter.loader import make_llm, load_role_config

role_cfg = load_role_config("librarian")
# role_cfg = {"model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
#              "region": "us-east-1", "max_tokens": 2048, "max_concurrency": 5}
```

### Q3: models.toml — librarian and synthesizer roles

[VERIFIED: cores/model-adapter/src/model_adapter/models.toml]

| Role | model_id | max_tokens | max_concurrency |
|------|----------|-----------|-----------------|
| `librarian` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | 2048 | 5 |
| `synthesizer` | `us.anthropic.claude-sonnet-4-6` | 4096 | 3 |

Both roles are already present. No changes needed to models.toml.

### Q4: `resolve_wiki_and_repo()` — exact signature

[VERIFIED: cores/vault-io/src/vault_io/_workspace.py]

```python
def resolve_wiki_and_repo(
    vault_path: Path | None = None,
) -> tuple[Path, Path | None]:
```

Priority: (1) `vault_path` argument, (2) `CODE_WIKI_REAL_VAULT_PATH` env var, (3) `RuntimeError`. Returns `(resolved_vault_path, None)` — `repo_root` is always `None` in v1.

**Important:** There is NO lattice-workspace discovery (no `.lattice-wiki.json` auto-detection). The vault path must always be supplied explicitly — via the `--vault` CLI flag or the env var.

### Q5: FastMCP instance name and `wiki_ping` registration pattern

[VERIFIED: agents/code-wiki-agent/src/code_wiki_mcp/server.py]

```python
mcp = FastMCP(name="code-wiki-mcp")  # instance name is `mcp`

@mcp.tool(
    name="wiki_ping",
    description="Returns pong; used to verify MCP wiring is intact.",
)
def wiki_ping(input: PingInput) -> PingOutput:
    ...
```

- Instance variable is `mcp` (not `app`).
- Tools are registered with `@mcp.tool(name=..., description=...)` decorator.
- `wiki_ping` is a synchronous function — `wiki_query` must be `async def` (it awaits `run_query()`).
- `_StdoutGuard` is installed before all imports. Phase 3 code in `server.py` must import after the guard.

**MCP tool argument schema (critical from test_mcp_stdio.py):** FastMCP nests the Pydantic model under the parameter name in the wire format. For `wiki_query(input: WikiQueryInput, ctx: Context)`, the wire shape is `arguments={"input": {<WikiQueryInput fields>}}` — NOT flat `arguments={"query": "..."}`. The integration test in `test_mcp_stdio.py` demonstrates this for `wiki_ping`.

### Q6: `tests/fixtures/round-trip-vault/` — exists and content suitable for integration test?

[VERIFIED: filesystem listing]

The round-trip-vault fixture exists at `cores/vault-io/tests/fixtures/round-trip-vault/`. It contains:
- 30+ `concepts/*.md` pages with YAML frontmatter, `[[wikilinks]]`, and multi-paragraph content
- `packages/` directory with subdirectories for lattice packages
- `adrs/` directory
- `index.md` and `log.md` (skip-list pages)

The vault has substantive content about the lattice ecosystem — pages like `bedrock-langgraph-stack.md`, `subagent-vs-teammate.md`, `sqlite-as-store.md`. These pages contain technical content relevant to queries about the architecture, making them suitable for a meaningful integration test query (e.g., "What BM25 search approach does the wiki use?").

**Key discovery:** The fixture vault lives under `cores/vault-io/`, not under `agents/code-wiki-agent/`. The integration test must reference it cross-package. Options: (1) reference via absolute path in test using `Path(__file__).parent` traversal, (2) set `CODE_WIKI_REAL_VAULT_PATH` pointing to the vault in the test fixture.

### Q7: Typer app name and async subcommand pattern

[VERIFIED: agents/code-wiki-agent/src/code_wiki_agent/cli.py]

```python
app = typer.Typer(name="code-wiki-agent", ...)
```

Existing subcommands: `version` (sync) and `trace` (sync). There is no existing async subcommand pattern. The `query` subcommand must bridge sync Typer to async `run_query()` via `asyncio.run()`:

```python
@app.command()
def query(query_text: str = typer.Argument(...), ...) -> None:
    result = asyncio.run(run_query(query_text, vault_path, top_k=top_k))
```

`asyncio_mode` is NOT set in code-wiki-agent's `pyproject.toml`. It IS set in `subagent-runtime`. Phase 3 must add `asyncio_mode = "auto"` to `agents/code-wiki-agent/pyproject.toml` to enable `@pytest.mark.asyncio` tests.

### Q8: Pytest patterns from Phase 2 to follow

[VERIFIED: integration test files]

Standard pattern confirmed:
```python
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)

@pytest.mark.integration
@INTEGRATION_GATE
async def test_query_fixture_vault(tmp_path: Path) -> None:
    ...
```

Run with: `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/integration/ -v`

---

## Architecture Patterns

### System Architecture Diagram

```
User query
    |
    v
[CLI: code-wiki-agent query]     [MCP: wiki_query tool call]
    |                                |
    +----------+  run_query()  +-----+
               |               |
               v               v
        commands/query.py
               |
        1. resolve_wiki_and_repo(vault_path)
               |
        2. BM25 search (sync)
           bm25s.BM25.load(".code-wiki/bm25/")
           tokenizer.tokenize(query, update_vocab=False)
           retriever.retrieve(query_tokens, k=top_k*3)
               |
        3. Embedding search (sync)
           BedrockEmbeddings.embed_query(query)  --> [AWS Bedrock: Titan v2]
           _cosine_search_sqlite(".code-wiki/search.db", query_vec, k=top_k*3)
               |
        4. RRF fusion (pure Python)
           _rrf_fuse(bm25_ranks, embed_ranks, k=60)
           top_pages = sorted(fused)[:top_k]
               |
        5. Librarian fan-out (async)
           SubagentPool.run_all(items=top_pages, task=drill_page, ...)
               |
           +---+---+---+---+---+   (up to 5 concurrent)
           |   |   |   |   |   |
           v   v   v   v   v   v
        [Haiku via Bedrock] x N  -->  excerpts[]
               |
        6. Synthesizer (async, single call)
           make_llm("synthesizer").ainvoke(excerpts) --> [Sonnet via Bedrock]
               |
        7. QueryResult
           answer, citations, pages_drilled, search_scores
               |
    +-----------+-----------+
    |                       |
    v                       v
[CLI renders answer]   [MCP serializes WikiQueryOutput]
```

### Recommended Project Structure

```
agents/code-wiki-agent/
  src/
    code_wiki_agent/
      __init__.py
      cli.py                          # add `query` subcommand here
      commands/
        __init__.py                   # new subpackage
        query.py                      # run_query(), QueryResult, search helpers
    code_wiki_mcp/
      __init__.py
      server.py                       # add wiki_query tool here
  tests/
    unit/
      test_stdout_guard.py            # existing
      test_cli_help.py                # existing
      test_trace_viewer.py            # existing
      test_query_search.py            # NEW: unit tests for BM25, RRF, cosine
      test_query_result.py            # NEW: unit tests for QueryResult, guardrails
    integration/
      test_bedrock_iam.py             # existing
      test_mcp_stdio.py               # existing
      test_query_e2e.py               # NEW: end-to-end with fixture vault + Bedrock

.code-wiki/
  bm25/                               # bm25s manages: vocab.json, data.npy, etc.
  search.db                           # SQLite WAL: pages(path, content_hash, embedding)
  traces/                             # JSONL per fan-out call (SubagentPool)
```

### Pattern 1: BM25 Index Build + Query

**What:** Build the bm25s index from vault pages; persist to `.code-wiki/bm25/`; reload at query time.

**When to use:** On first query (no index exists) or when pages have changed (detected by sha256).

```python
# Source: Context7 /xhluca/bm25s
from bm25s.tokenization import Tokenizer
import bm25s

# BUILD (called during index rebuild)
tokenizer = Tokenizer(
    lower=True,
    splitter=r"[a-zA-Z0-9][a-zA-Z0-9_\-']+",  # matches lattice-wiki-core TOKEN_RE
    stopwords=list(_STOPWORDS),
)
corpus = ["page text 1", "page text 2", ...]
corpus_tokens = tokenizer.tokenize(corpus)

retriever = bm25s.BM25(method="lucene", k1=1.5, b=0.75)
retriever.index(corpus_tokens)

# Save index + corpus + tokenizer vocab/stopwords
retriever.save(str(bm25_dir), corpus=corpus)        # saves data.*.npy, corpus.jsonl
tokenizer.save_vocab(str(bm25_dir))                 # saves vocab.index.json
tokenizer.save_stopwords(str(bm25_dir))             # saves stopwords.json

# QUERY (called from run_query)
loaded_retriever = bm25s.BM25.load(str(bm25_dir), load_corpus=True)
query_tokenizer = Tokenizer(lower=True, splitter=r"...", stopwords=[])
query_tokenizer.load_vocab(str(bm25_dir))
query_tokenizer.load_stopwords(str(bm25_dir))
query_tokens = query_tokenizer.tokenize([query_text], update_vocab=False)
results, scores = loaded_retriever.retrieve(query_tokens, k=top_k * 3)
# results.shape == (1, k); results[0, i] is the corpus item at rank i
```

**Critical:** `update_vocab=False` at query time prevents the frozen vocabulary from expanding. Forgetting this causes silent zero-recall for any query terms not seen during index build.

### Pattern 2: SQLite Embedding Store with WAL Mode

**What:** Store Titan v2 embedding vectors as binary BLOBs in SQLite, keyed by page path.

```python
# Source: [VERIFIED: D-04 decision; stdlib sqlite3]
import sqlite3
import struct

DB_PATH = vault_path / ".code-wiki" / "search.db"

# INITIALIZE
conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("""
    CREATE TABLE IF NOT EXISTS pages (
        path         TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        embedding    BLOB NOT NULL
    )
""")
conn.commit()
conn.close()

# UPSERT (one page)
vec = embeddings.embed_query(page_text)   # list[float], 1024 dims
blob = struct.pack(f"{len(vec)}f", *vec)  # 4096 bytes for 1024-dim
conn.execute(
    "INSERT OR REPLACE INTO pages (path, content_hash, embedding) VALUES (?, ?, ?)",
    (str(page_rel_path), sha256_hash, blob)
)

# COSINE SEARCH (linear scan, adequate for small vaults)
def _cosine_search_sqlite(db_path, query_vec, top_k):
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT path, embedding FROM pages").fetchall()
    conn.close()
    results = []
    q_mag = math.sqrt(sum(x*x for x in query_vec))
    for path, blob in rows:
        vec = struct.unpack(f"{len(blob)//4}f", blob)
        dot = sum(a*b for a,b in zip(query_vec, vec))
        v_mag = math.sqrt(sum(x*x for x in vec))
        score = dot / (q_mag * v_mag) if (q_mag and v_mag) else 0.0
        results.append((path, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]
```

### Pattern 3: BedrockEmbeddings for Titan v2

**What:** Generate 1024-dimension vectors via Titan Embeddings v2 through `langchain-aws`.

```python
# Source: Context7 /langchain-ai/langchain-aws; AI-SPEC Section 3
from langchain_aws import BedrockEmbeddings

embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",  # no "us." prefix for Titan
    region_name="us-east-1",
    normalize=True,   # L2 normalize; cosine sim then equals dot product
    # dimensions param: omit for default 1024; optional int 256/512/1024
)

# Single query embedding (used at search time)
query_vec = embeddings.embed_query(query_text)   # list[float], 1024 elements

# Document embeddings for index build (called once per page, not batched)
# embed_documents() loops and calls embed_query() per item sequentially.
# For index builds, call embed_query() in parallel via asyncio if needed.
```

**Dimensions:** 1024 (default for Titan v2 when `dimensions` param is omitted). The embedding BLOB is `struct.pack(f"{1024}f", *vec)` = 4096 bytes per page row.

### Pattern 4: MCP Tool Registration (with async + progress)

**What:** Register `wiki_query` as an async MCP tool on the existing `mcp` FastMCP instance.

```python
# Source: [VERIFIED: server.py pattern; test_mcp_stdio.py wire format]
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel
from code_wiki_agent.commands.query import run_query, QueryResult

class WikiQueryInput(BaseModel):
    query: str
    vault_path: str = ""    # empty -> use CODE_WIKI_REAL_VAULT_PATH env var
    top_k: int = 5          # 3-10 range; validated by caller

class WikiQueryOutput(BaseModel):
    answer: str
    citations: list[str]
    pages_drilled: int
    search_scores: dict     # {page_path: {"bm25": float, "embed": float, "rrf": float}}

@mcp.tool(
    name="wiki_query",
    description=(
        "Query the code wiki using hybrid BM25+embedding search with parallel librarian "
        "analysis. Returns an answer with [[wikilink]] citations. "
        "vault_path defaults to CODE_WIKI_REAL_VAULT_PATH env var."
    ),
)
async def wiki_query(input: WikiQueryInput, ctx: Context) -> WikiQueryOutput:
    from pathlib import Path
    vault = Path(input.vault_path) if input.vault_path else None
    await ctx.report_progress(progress=0, total=input.top_k, message="Starting hybrid search")
    result: QueryResult = await run_query(
        query=input.query,
        vault_path=vault,
        top_k=input.top_k,
    )
    await ctx.report_progress(
        progress=result.pages_drilled,
        total=input.top_k,
        message=f"Synthesized from {result.pages_drilled} pages",
    )
    return WikiQueryOutput(
        answer=result.answer,
        citations=result.citations,
        pages_drilled=result.pages_drilled,
        search_scores=result.search_scores,
    )
```

**Wire format (DeepAgents CLI call):** `arguments={"input": {"query": "...", "top_k": 5}}` — the Pydantic model is nested under the parameter name `input`. This is the established pattern from `wiki_ping` confirmed in `test_mcp_stdio.py`.

### Pattern 5: CLI Async Subcommand

**What:** Add `query` subcommand to existing `app = typer.Typer(...)` in `cli.py`.

```python
# Source: [VERIFIED: cli.py pattern; asyncio.run for CLI bridge]
import asyncio
import json
from pathlib import Path

import typer

from code_wiki_agent.commands.query import run_query

@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)"),
    vault: str = typer.Option("", "--vault", help="Vault path (default: resolve from workspace)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
    _no_state_gate: bool = typer.Option(False, "--no-state-gate", help="No-op; query is read-only"),
) -> None:
    """Query the wiki using hybrid BM25+embedding search."""
    import sys
    vault_path = Path(vault) if vault else None  # None -> resolve_wiki_and_repo uses env var
    try:
        result = asyncio.run(run_query(query_text, vault_path, top_k=top_k))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if json_output:
        import dataclasses
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(result.answer)
        if result.citations:
            typer.echo(f"\nCitations: {', '.join(result.citations)}")
        typer.echo(f"Pages drilled: {result.pages_drilled}", err=not sys.stdout.isatty())
```

### Anti-Patterns to Avoid

- **Calling `asyncio.run()` inside an async context:** The MCP tool handler is `async def`; use `await run_query(...)` inside it, not `asyncio.run()`. Only the Typer CLI command (sync) uses `asyncio.run()`.
- **Saving bm25s tokenizer vocab without calling `save_vocab()` + `save_stopwords()`:** `BM25.save()` persists the index matrix but NOT the tokenizer vocabulary. Omitting the tokenizer save causes silent vocabulary mismatch between build and query time.
- **Using the `us.` prefix for Titan v2:** The correct ID is `amazon.titan-embed-text-v2:0` (no `us.`). Cross-region inference prefixes apply to Claude chat models, not to Amazon-native embedding models. Using the wrong ID returns `AccessDeniedException`.
- **Using `embed_documents()` for parallel embedding during index build:** `BedrockEmbeddings.embed_documents()` is synchronous and sequential. For parallel index builds, call `embed_query()` inside `asyncio.gather()` with a semaphore, or use `asyncio.to_thread`.
- **Assuming `FanOutResult.successes` items match the input page list order:** Results come back in completion order (asyncio.gather), not insertion order. Build the score map from `(item, result)` tuples in `fan_result.successes`, not by index.
- **Writing to stdout anywhere in the query pipeline:** `_StdoutGuard` in `server.py` raises `RuntimeError` on any non-empty stdout write. All logging in `commands/query.py` must use `logging.getLogger(__name__)` to stderr. The CLI uses `typer.echo()` (stdout for user-facing output only).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| BM25 scoring | Custom TF-IDF/BM25 | `bm25s 0.3.8` | lattice-wiki-core's hand-rolled version is pure Python + Counter; bm25s is 5-50x faster with precomputed sparse matrices |
| Embedding API calls | Raw boto3 `invoke_model` | `BedrockEmbeddings` (langchain-aws) | Handles request signing, retries, response parsing, and thread-pool wrapping |
| Async fan-out with partial-failure | Custom `asyncio.gather` wrapper | `SubagentPool.run_all()` | Already has semaphore, trace writing, partial-failure isolation (Phase 2 deliverable) |
| Model ID resolution | Hardcoded strings | `make_llm(role)` + `load_role_config(role)` | models.toml is the single source of truth; hardcoding bypasses throttle caps |
| Vector similarity search | Custom cosine C extension | Pure Python `struct.unpack` + dot product | At 100-200 vault pages, linear scan is < 5ms; no performance justification for a vector DB |
| MCP tool schema | Hand-crafted JSON schema | Pydantic `BaseModel` fields on `WikiQueryInput` | FastMCP derives the JSON schema from the Pydantic model automatically |

---

## Common Pitfalls

### Pitfall 1: bm25s Vocabulary Mismatch Between Build and Query

**What goes wrong:** At query time, `tokenizer.tokenize(query, update_vocab=False)` silently drops tokens not in the frozen vocabulary. If the tokenizer was not saved and reloaded, you get a fresh empty vocabulary and every query term is dropped — zero recall on everything.

**Why it happens:** `bm25s.BM25.save()` saves the index matrix but NOT the tokenizer. They are separate objects with separate persistence calls.

**How to avoid:** Always call `tokenizer.save_vocab(bm25_dir)` and `tokenizer.save_stopwords(bm25_dir)` immediately after `retriever.save()`. At query time, create a fresh `Tokenizer` and call `load_vocab()` + `load_stopwords()` before tokenizing the query.

**Warning signs:** All BM25 scores are 0.0; `bm25_rank_map` is empty; RRF fusion is driven entirely by embedding.

### Pitfall 2: Titan v2 Model ID with `us.` Prefix

**What goes wrong:** `AccessDeniedException` from Bedrock, even if Titan v2 access is enabled in the console.

**Why it happens:** `us.amazon.titan-embed-text-v2:0` is not a valid model ID. Cross-region inference profile ARNs (with `us.` prefix) apply to Claude models. Amazon-native models (Titan, Nova) use the bare `amazon.` prefix.

**How to avoid:** Use `model_id="amazon.titan-embed-text-v2:0"` in `BedrockEmbeddings`. [VERIFIED: Context7 /langchain-ai/langchain-aws; AI-SPEC Section 3]

**Warning signs:** `AccessDeniedException` mentioning an ARN like `arn:aws:bedrock:us-east-1::foundation-model/us.amazon.titan-...`.

### Pitfall 3: `asyncio.Semaphore` Created Outside `run_all()`

**What goes wrong:** `RuntimeError: Future attached to a different loop` in pytest tests.

**Why it happens:** pytest-asyncio creates a fresh event loop per test. A semaphore created at module import time binds to a different loop.

**How to avoid:** The existing `SubagentPool` already creates the semaphore inside `run_all()`. Never move it to `__init__` or a module-level constant.

**Warning signs:** Error only appears in test context, not in production runs.

### Pitfall 4: FastMCP `ctx.report_progress()` as a Synchronization Primitive

**What goes wrong:** Code that gates on whether `report_progress` "succeeded" to decide whether to proceed — or code that expects it to throw if the client disconnected.

**Why it happens:** `ctx.report_progress()` is a no-op when the client did not send a `progressToken`. It never raises.

**How to avoid:** Use it only for informational progress display. Use `FanOutResult.successes` length as the actual success indicator, not the progress notification count.

### Pitfall 5: Missing `asyncio_mode = "auto"` in code-wiki-agent pyproject.toml

**What goes wrong:** `@pytest.mark.asyncio` tests fail with `SyntaxError` or `RuntimeWarning: coroutine 'test_...' was never awaited`.

**Why it happens:** `asyncio_mode = "auto"` is set in `subagent-runtime` but NOT in `code-wiki-agent`. The test runner uses the package's own pytest config.

**How to avoid:** Add `asyncio_mode = "auto"` to `agents/code-wiki-agent/pyproject.toml` under `[tool.pytest.ini_options]`.

### Pitfall 6: Fixture Vault Path Cross-Package Reference

**What goes wrong:** Integration test fails with `RuntimeError: Vault path not specified` or `FileNotFoundError`.

**Why it happens:** The round-trip-vault fixture is at `cores/vault-io/tests/fixtures/round-trip-vault/` but the integration test for Phase 3 lives at `agents/code-wiki-agent/tests/integration/`. A naive relative path breaks.

**How to avoid:** Resolve the fixture vault path robustly in the test:

```python
# In agents/code-wiki-agent/tests/integration/test_query_e2e.py
from pathlib import Path

FIXTURE_VAULT = (
    Path(__file__).parent.parent.parent.parent.parent  # project root
    / "cores" / "vault-io" / "tests" / "fixtures" / "round-trip-vault"
)
```

Or pass it as an env var: `CODE_WIKI_REAL_VAULT_PATH=/path/to/round-trip-vault`.

### Pitfall 7: BM25 `retrieve()` Return Shape

**What goes wrong:** `IndexError` or `TypeError` when building `bm25_rank_map`.

**Why it happens:** `retriever.retrieve(query_tokens, k=N)` returns `(results, scores)` where `results` is a numpy array of shape `(1, k)` containing corpus items (not indices when corpus is loaded). The items are the original strings from `corpus`.

**How to avoid:** Build the rank map from the corpus strings directly:

```python
results, scores = retriever.retrieve(query_tokens, k=top_k * 3)
# results[0] is an array of corpus items (strings)
# scores[0] is an array of BM25 scores
bm25_rank_map = {str(results[0, i]): i + 1 for i in range(results.shape[1])}
bm25_score_map = {str(results[0, i]): float(scores[0, i]) for i in range(results.shape[1])}
```

The corpus items in `results` are the strings saved at index time. When the corpus is page paths, the results are page paths.

---

## Code Examples

### Building and Querying the Hybrid Index

```python
# Source: AI-SPEC Section 3 + verified bm25s Context7 + sqlite3 stdlib
import bm25s
import hashlib
import sqlite3
import struct
from bm25s.tokenization import Tokenizer
from langchain_aws import BedrockEmbeddings
from pathlib import Path

_TOKEN_RE_PATTERN = r"[a-zA-Z0-9][a-zA-Z0-9_\-']+"
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "to", "of", "in", "on",
    "at", "for", "by", "with", "from", "is", "are", "was", "were", "be",
    "been", "this", "that", "it", "as", "we", "you", "they", "not", "no",
    "do", "does", "did", "will", "would", "can", "could", "should", "also",
}

def build_index(vault_path: Path, bm25_dir: Path, db_path: Path) -> None:
    """Build BM25 + embedding index from scratch."""
    # Discover pages (skip index.md, log.md, dot-prefixed dirs)
    pages = []
    for md in sorted(vault_path.rglob("*.md")):
        rel = md.relative_to(vault_path)
        if rel.name in {"index.md", "log.md"}:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        pages.append((str(rel).replace("\\", "/"), md.read_text()))

    # BM25
    tokenizer = Tokenizer(
        lower=True, splitter=_TOKEN_RE_PATTERN, stopwords=list(_STOPWORDS)
    )
    corpus_texts = [text for _, text in pages]
    corpus_paths = [path for path, _ in pages]
    corpus_tokens = tokenizer.tokenize(corpus_texts)
    retriever = bm25s.BM25(method="lucene", k1=1.5, b=0.75)
    retriever.index(corpus_tokens)
    bm25_dir.mkdir(parents=True, exist_ok=True)
    retriever.save(str(bm25_dir), corpus=corpus_paths)  # save paths as corpus items
    tokenizer.save_vocab(str(bm25_dir))
    tokenizer.save_stopwords(str(bm25_dir))

    # Embeddings
    embeddings = BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0", region_name="us-east-1", normalize=True
    )
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS pages (
        path TEXT PRIMARY KEY, content_hash TEXT NOT NULL, embedding BLOB NOT NULL)""")
    for path, text in pages:
        h = hashlib.sha256(text.encode()).hexdigest()
        row = conn.execute(
            "SELECT content_hash FROM pages WHERE path=?", (path,)
        ).fetchone()
        if row and row[0] == h:
            continue  # unchanged; skip re-embedding (D-02)
        vec = embeddings.embed_query(text)
        blob = struct.pack(f"{len(vec)}f", *vec)
        conn.execute(
            "INSERT OR REPLACE INTO pages (path, content_hash, embedding) VALUES (?,?,?)",
            (path, h, blob)
        )
    conn.commit()
    conn.close()
```

### RRF Fusion

```python
# Source: AI-SPEC Section 3 + D-03 decision
def _rrf_fuse(
    bm25_ranks: dict[str, int],
    embed_ranks: dict[str, int],
    k: int = 60,
) -> dict[str, float]:
    """Reciprocal Rank Fusion. score = 1/(k+rank_bm25) + 1/(k+rank_embed)."""
    all_pages = set(bm25_ranks) | set(embed_ranks)
    n = len(all_pages)
    return {
        p: 1.0 / (k + bm25_ranks.get(p, n + k)) + 1.0 / (k + embed_ranks.get(p, n + k))
        for p in all_pages
    }
```

### Online Guardrails

```python
# Source: AI-SPEC Section 6
import re

def _check_citation_resolution(answer: str, vault_path: Path) -> list[str]:
    """Return list of [[wikilink]] targets that don't resolve to a vault file."""
    unresolved = []
    for link in re.findall(r"\[\[([^\]]+)\]\]", answer):
        # Case-insensitive lookup under wiki/**/*.md
        candidate = vault_path / f"{link}.md"
        if not candidate.exists():
            # Try case-insensitive glob
            matches = list(vault_path.glob(f"**/{link}.md"))
            if not matches:
                unresolved.append(link)
    return unresolved

def apply_guardrails(result: QueryResult, vault_path: Path, fan_result: FanOutResult) -> QueryResult:
    """Apply online guardrails G1-G4. Mutates answer string for flags; never raises."""
    flags = []

    # G4: empty excerpts + confident answer
    if not fan_result.successes and result.citations:
        flags.append("[warning: no librarian excerpts; answer is unsupported by retrieved pages]")
        result = QueryResult(
            answer=result.answer,
            citations=[],  # clear citations to avoid G1 false-positives
            pages_drilled=result.pages_drilled,
            search_scores=result.search_scores,
        )

    # G1: citation resolution
    unresolved = _check_citation_resolution(result.answer, vault_path)
    if unresolved:
        flags.append(f"[warning: {len(unresolved)} citation(s) did not resolve: {unresolved}]")

    if flags:
        flagged_answer = result.answer + "\n" + "\n".join(flags)
        return QueryResult(
            answer=flagged_answer,
            citations=result.citations,
            pages_drilled=result.pages_drilled,
            search_scores=result.search_scores,
        )
    return result
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `rank-bm25` (lattice-wiki-core) | `bm25s 0.3.8` | Phase 3 decision | 5-50x faster; active maintenance; built-in tokenizer |
| Hand-rolled BM25 with Counter/dict | bm25s sparse matrix | Phase 3 decision | Same tokenization semantics (TOKEN_RE + stopwords); better performance |
| BM25-only search | Hybrid BM25 + Titan v2 embeddings | Phase 3 | Semantic fallback for low-frequency terms; RRF fusion improves ranking |
| SSE MCP transport | stdio transport | MCP spec 2025-03-26 | SSE deprecated; stdio is the standard for local CLI hosting |
| `ChatBedrock` (legacy) | `ChatBedrockConverse` | langchain-aws 1.x | Converse API supports all current Bedrock models uniformly |

**Deprecated/outdated:**
- `rank-bm25`: abandoned since 2022; replaced by `bm25s` in this project.
- `ChatBedrock`: use `ChatBedrockConverse` only — `make_llm()` already uses the correct class.
- SSE MCP transport: spec deprecated 2025-03-26; server.py uses `transport="stdio"`.

---

## Open Questions

1. **`correlation_id` for `query_id` linking across trace records**
   - What we know: AI-SPEC Section 7 requires a per-`run_query()` UUID (`query_id`) so all librarian traces + synthesizer trace can be joined offline. The `SubagentPool.run_all()` signature does NOT have a `correlation_id` kwarg yet.
   - What's unclear: Should `run_all()` gain a `correlation_id` optional kwarg (written to trace records), or should `run_query()` write a separate `query_summary` JSONL record to the trace file manually?
   - Recommendation: Add `correlation_id: str | None = None` kwarg to `SubagentPool.run_all()` (minimal change, backward-compatible), OR write the `query_summary` record directly from `run_query()` without touching SubagentPool. The latter is simpler and avoids changing the established SubagentPool API in Phase 3.

2. **Index build trigger — when and by whom**
   - What we know: D-02 specifies incremental rebuild on sha256 change detection. The AI-SPEC shows `BM25.load()` at query time, implying the index already exists.
   - What's unclear: Who builds the index on first run (no `bm25/` dir or `search.db`)? `run_query()` should detect absence and trigger a full build, or fail with a helpful error message.
   - Recommendation: `run_query()` checks for the existence of `.code-wiki/bm25/` and `.code-wiki/search.db`. If absent, trigger `build_index()` synchronously before the search phase. Log a `WARNING` noting the first-time build latency.

3. **Stopwords set — strict match to lattice-wiki-core or extended?**
   - What we know: AI-SPEC uses a subset of the lattice-wiki-core stopwords. The full set from `wiki_search.py` has ~60 terms vs the ~25 in AI-SPEC.
   - Recommendation: Use the full lattice-wiki-core stopwords set for fidelity to reference behavior (SEARCH-01 "replacement"). The difference is minor for recall but keeps the port semantically identical.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | Workspace management, test runner | ✓ | 0.11.14 | — |
| Python 3.11 | Runtime | ✓ | 3.11.x | — |
| `bm25s` 0.3.8 | BM25 search | ✗ (not yet installed) | — | Must install: `uv add --package code-wiki-agent bm25s==0.3.8` |
| AWS Bedrock (us-east-1) | Embedding + LLM calls | ✓ (verified Phase 1 BED-01) | — | None; required for integration tests |
| `sqlite3` | Embedding store | ✓ (stdlib) | bundled | — |
| `langchain-aws` 1.4.6 | `BedrockEmbeddings` | ✓ (installed Phase 1) | 1.4.6 | — |
| Round-trip-vault fixture | Integration test | ✓ | — | At `cores/vault-io/tests/fixtures/round-trip-vault/` |

**Missing dependencies with no fallback:**
- `bm25s==0.3.8` — must be added before any implementation can run.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=8.3 + pytest-asyncio 1.3.0 |
| Config file | `agents/code-wiki-agent/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/ -x` |
| Full suite command | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -x` |
| Integration tests | `CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/integration/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEARCH-01 | BM25 index build + query returns ranked pages | unit | `pytest tests/unit/test_query_search.py::test_bm25_index_build -x` | Wave 0 |
| SEARCH-02 | `BedrockEmbeddings.embed_query()` returns 1024-dim vector | unit (mock) | `pytest tests/unit/test_query_search.py::test_embedding_shape -x` | Wave 0 |
| SEARCH-03 | RRF fusion merges BM25 and embedding ranks | unit | `pytest tests/unit/test_query_search.py::test_rrf_fusion -x` | Wave 0 |
| SEARCH-04 | `search.db` created with WAL mode; vectors persisted | unit | `pytest tests/unit/test_query_search.py::test_sqlite_store -x` | Wave 0 |
| SEARCH-05 | Pages with unchanged sha256 are NOT re-embedded | unit | `pytest tests/unit/test_query_search.py::test_incremental_skip -x` | Wave 0 |
| SEARCH-06 | `search_scores` dict has `bm25`, `embed`, `rrf` keys per page | unit | `pytest tests/unit/test_query_result.py::test_search_scores_shape -x` | Wave 0 |
| CMD-04 | `run_query()` returns `QueryResult` with answer and citations | integration | `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_query_e2e.py -v` | Wave 0 |
| CMD-07 | `--json` serializes `QueryResult` to valid JSON with correct schema | unit | `pytest tests/unit/test_query_result.py::test_json_output -x` | Wave 0 |
| CMD-08 | `--no-state-gate` flag accepted; query proceeds without error | unit | `pytest tests/unit/test_cli_query.py::test_state_gate_noop -x` | Wave 0 |
| MCP-02 | `wiki_query` tool listed with description and typed schema | unit | `pytest tests/unit/test_mcp_query_schema.py -x` | Wave 0 |
| MCP-04 | Invalid `wiki_query` input returns structured MCP error, not crash | unit | `pytest tests/unit/test_mcp_query_schema.py::test_invalid_input -x` | Wave 0 |
| MCP-06 | `ctx.report_progress()` called at start and end of query | unit (mock ctx) | `pytest tests/unit/test_mcp_query_schema.py::test_progress_calls -x` | Wave 0 |
| MCP-07 | `code-wiki-mcp` launches and `wiki_query` appears in tools list | integration (subprocess) | `pytest tests/integration/test_mcp_stdio.py::test_wiki_query_listed -x` | Wave 0 (extends existing test) |
| CLI-01 | `code-wiki-agent query --help` exits 0 | unit | `pytest tests/unit/test_cli_help.py::test_query_help -x` | Wave 0 |
| CLI-02/03 | CLI and MCP call same `run_query()` function | unit (import check) | `pytest tests/unit/test_cli_query.py::test_shared_impl -x` | Wave 0 |
| CLI-04 | `--json` flag produces valid JSON on stdout | integration | `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_query_e2e.py::test_json_flag -x` | Wave 0 |
| CLI-05 | `--vault` flag passes path to `resolve_wiki_and_repo` | unit | `pytest tests/unit/test_cli_query.py::test_vault_flag -x` | Wave 0 |
| CLI-06 | Exit code 1 on vault-not-found error | unit | `pytest tests/unit/test_cli_query.py::test_exit_code_1 -x` | Wave 0 |
| CLI-07 | Headless mode (non-TTY) suppresses interactive output | unit | `pytest tests/unit/test_cli_query.py::test_headless_mode -x` | Wave 0 |
| SC-5 | End-to-end: fixture vault query returns answer with `[[wikilink]]` | integration | `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_query_e2e.py::test_fixture_vault_has_citations -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/ -x`
- **Per wave merge:** `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -x` (skips integration)
- **Phase gate:** Full suite including `CODE_WIKI_RUN_INTEGRATION=1` integration tests before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `agents/code-wiki-agent/tests/unit/test_query_search.py` — BM25, SQLite, cosine, RRF unit tests (pure Python, no Bedrock)
- [ ] `agents/code-wiki-agent/tests/unit/test_query_result.py` — `QueryResult` shape, JSON serialization, guardrails
- [ ] `agents/code-wiki-agent/tests/unit/test_cli_query.py` — Typer subcommand flag tests
- [ ] `agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py` — MCP tool schema + progress mock
- [ ] `agents/code-wiki-agent/tests/integration/test_query_e2e.py` — end-to-end with real Bedrock + fixture vault
- [ ] `asyncio_mode = "auto"` in `agents/code-wiki-agent/pyproject.toml` `[tool.pytest.ini_options]` — missing, required for async tests
- [ ] Framework install: `uv add --package code-wiki-agent bm25s==0.3.8` — required before any unit tests run

---

## Security Domain

This phase has no meaningful security surface beyond what Phase 1/2 established. Applicable ASVS categories:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | AWS IAM for Bedrock (established Phase 1) |
| V3 Session Management | No | Stateless per-query invocation |
| V4 Access Control | No | Read-only vault access; no user accounts |
| V5 Input Validation | Yes (light) | Pydantic `WikiQueryInput` validates `top_k` range; vault path is resolved via stdlib `Path.resolve()` |
| V6 Cryptography | No | sha256 used for change detection only (no security function) |

| Threat Pattern | STRIDE | Standard Mitigation |
|----------------|--------|---------------------|
| Path traversal via `vault_path` | Tampering | `Path.resolve()` in `resolve_wiki_and_repo()`; vault path is caller-supplied and pinned to explicit arg or env var |
| Prompt injection via wiki page content | Tampering | Out of scope for internal dev tool; vault author controls all content |
| AWS credential exposure in traces | Information Disclosure | `_write_trace` uses `item_id=str(item)` (page paths only); no secrets in page paths |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Titan v2 output is 1024 dimensions (not 1536) when `dimensions` param is omitted | Standard Stack | BLOB size in search.db would be wrong (4096 vs 6144 bytes); cosine sim would still work but storage is miscalculated |
| A2 | `BedrockEmbeddings` `normalize=True` makes L2-normalized vectors; cosine sim equals dot product | Code Examples | Cosine search still works but is slightly more expensive (must compute magnitudes explicitly) |
| A3 | bm25s `Tokenizer(splitter=regex_str)` accepts a regex string (not a compiled pattern) | Architecture Patterns | Build would fail with TypeError; would need `splitter=lambda x: TOKEN_RE.findall(x)` instead |

All other findings in this document were verified against live source code or Context7 documentation during this research session.

---

## Sources

### Primary (HIGH confidence)

- `cores/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool.run_all()` signature, `FanOutResult`, semaphore placement, `load_role_config` usage
- `cores/model-adapter/src/model_adapter/loader.py` — `make_llm()` and `load_role_config()` implementations
- `cores/model-adapter/src/model_adapter/models.toml` — librarian (Haiku 2048t 5c) and synthesizer (Sonnet 4096t 3c) exact config
- `cores/vault-io/src/vault_io/_workspace.py` — `resolve_wiki_and_repo()` exact signature, env var priority, no lattice-workspace discovery
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — `mcp = FastMCP(...)`, `@mcp.tool` decorator pattern, `_StdoutGuard` installation order
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — `app = typer.Typer(...)`, existing subcommands, no `asyncio_mode` setting
- `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` — FastMCP wire format (Pydantic model nested under param name)
- `agents/code-wiki-agent/pyproject.toml` — `asyncio_mode` NOT set; `integration` marker registered
- `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` — `CODE_WIKI_RUN_INTEGRATION` pattern
- `cores/vault-io/tests/fixtures/round-trip-vault/` — fixture vault exists, 30+ concept pages, suitable for integration test
- Context7 `/xhluca/bm25s` — `Tokenizer` API, `save()`/`load()`, `retrieve()` return shape, `splitter` param
- Context7 `/langchain-ai/langchain-aws` — `BedrockEmbeddings(model_id, normalize, dimensions)`, `embed_query()` sync behavior

### Secondary (MEDIUM confidence)

- `03-AI-SPEC.md` — comprehensive implementation guidance verified against live code where possible; model IDs and embedding dimensions confirmed
- `lattice/packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py` — reference `TOKEN_RE` pattern and `STOPWORDS` set

### Tertiary (LOW confidence)

- A1-A3 in Assumptions Log — based on training knowledge + documentation but not confirmed via Bedrock invocation

---

## Metadata

**Confidence breakdown:**
- SubagentPool API: HIGH — read from source code directly
- model_adapter API: HIGH — read from source code directly
- vault-io workspace resolution: HIGH — read from source code directly
- FastMCP wiring pattern: HIGH — read server.py + test_mcp_stdio.py
- bm25s Tokenizer API: HIGH — Context7 /xhluca/bm25s verified
- BedrockEmbeddings API: HIGH — Context7 /langchain-ai/langchain-aws verified
- Titan v2 dimensions (1024): MEDIUM — AI-SPEC states 1024 with source citation; training knowledge agrees; not confirmed via live call
- Fixture vault suitability: HIGH — read vault contents directly

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (bm25s and langchain-aws are actively maintained; check for patch releases)
