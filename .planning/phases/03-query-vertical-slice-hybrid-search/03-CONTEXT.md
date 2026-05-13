# Phase 3: Query Vertical Slice + Hybrid Search - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the `query` command end-to-end — hybrid BM25+embedding search, parallel librarian drilling, Sonnet synthesis — wired through both the MCP `wiki_query` tool and the headless CLI `code-wiki-agent query`. Both delivery surfaces share a single implementation.

Three deliverables:
1. **Hybrid search index** — BM25 (bm25s, native directory at `.code-wiki/bm25/`) + Titan embedding vectors (SQLite at `.code-wiki/search.db`). Incremental rebuild keyed on sha256 content hash. RRF fusion.
2. **`commands/query.py`** — agent-owned shared command implementation: reads `index.md`, hybrid-searches top-K pages, drills in parallel via librarian fan-out, synthesizes via synthesizer role, returns `QueryResult` dataclass.
3. **Two delivery surfaces** — CLI subcommand (`code-wiki-agent query`) and MCP tool (`wiki_query`) both call `commands/query.py`; MCP is a thin wrapper; both honor `--json` and state-gate interface.

**Out of scope this phase:** any other command (scan, lint, init, ingest, log), the eval harness, file-write-back after query, cost_usd accounting (null until Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Embedding Model (SEARCH-02)

- **D-01:** Use **Titan Embeddings G1 v2** (`amazon.titan-embed-text-v2:0` or equivalent cross-region ARN). Amazon-native, no extra IAM grants beyond Phase 1's Bedrock access proof. 1536 dimensions. Supported in `langchain-aws` via `BedrockEmbeddings`. Researcher confirms the exact model ID and ARN format.

### Incremental Rebuild (SEARCH-05)

- **D-02:** Change detection uses **sha256 content hash** of the raw markdown text. Hash stored alongside the embedding vector in `search.db`. On each query (or explicit rebuild), compare the current file's sha256 against the stored hash; re-embed only if different. Deterministic and cheap — matches the spirit of the vault round-trip golden gate from Phase 1.

### Hybrid Fusion (SEARCH-03)

- **D-03:** Use **RRF (Reciprocal Rank Fusion)** with `k=60`: `score = 1/(k + rank_bm25) + 1/(k + rank_embed)`. Parameter-free — no alpha tuning required. Both raw BM25 score and raw cosine similarity are preserved and included in `--json` output alongside the fused RRF score (SEARCH-06 compliance).

### Index Persistence (SEARCH-04)

- **D-04:** **Two separate stores** — bm25s native directory at `.code-wiki/bm25/` (bm25s manages its own joblib-based serialization); embedding vectors in SQLite at `.code-wiki/search.db` (stdlib `sqlite3`, no extra deps). `search.db` schema: a `pages` table with columns `(path TEXT PRIMARY KEY, content_hash TEXT, embedding BLOB)`. Planner designs exact DDL and upsert pattern.

### Command Layer Architecture (CLI-03)

- **D-05:** Shared implementation lives at **`agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`**. This is the single source of truth for query behavior. The CLI `query` subcommand and the MCP `wiki_query` tool both import and call `commands/query.py`. The MCP tool is a thin wrapper (validates inputs, calls `run_query()`, serializes `QueryResult` to JSON). No new `cores/` package — kept agent-owned for v1 simplicity (only one agent).

- **D-06:** The shared function returns a **`QueryResult` dataclass** (not a plain dict):
  ```python
  @dataclass
  class QueryResult:
      answer: str
      citations: list[str]       # [[wikilink]] strings found in answer
      pages_drilled: int
      search_scores: dict        # {page_path: {"bm25": float, "embed": float, "rrf": float}}
  ```
  Consistent with `FanOutResult` / `PerItemError` pattern established in Phase 2. CLI renders it; MCP serializes to JSON.

- **D-07:** Default **top-K = 5** pages sent to librarian fan-out. Configurable via `--top-k` flag on the CLI subcommand and a `top_k: int = 5` parameter on the MCP tool's input schema. The 3–10 range from CMD-04 is the allowed window; 5 is the default.

### Role Assignment for Query Flow

*(Carried from Phase 2 models.toml — not re-discussed, included for planner clarity)*

- **Librarian** (Haiku, 2048t, 5 concurrent): parallel page drilling — each librarian call reads one wiki page and extracts relevant excerpts for the query.
- **Synthesizer** (Sonnet, 4096t, 3 concurrent): single synthesis call — receives all librarian excerpts and produces the final answer with `[[wikilink]]` citations and code-path references.

### State Gate (CMD-08 + Success Criterion 4)

- **D-08:** The state gate **interface is present** on the `query` subcommand (accepts `--no-state-gate` flag or equivalent, consistent with other commands) but the **underlying git check is a no-op for query**. Query is read-only — it never modifies the vault — so blocking on dirty git state would create false-positive friction. The gate always passes. This satisfies "state-gate mechanism are present on the query subcommand" from success criterion 4 while remaining read-safe.

### Claude's Discretion

- **Exact Titan embedding model ID / cross-region ARN** — researcher confirms current naming (e.g., `us.amazon.titan-embed-text-v2:0`) against Pat's Bedrock account and langchain-aws docs.
- **`BedrockEmbeddings` call batching** — Titan v2 accepts up to 8192 input tokens per call; researcher determines the safe batch size for vault pages to avoid token overflow.
- **bm25s tokenizer settings** — whether to use bm25s's built-in tokenizer or replicate lattice-wiki-core's `TOKEN_RE` + stopword set; researcher checks bm25s API.
- **`search.db` schema DDL and upsert** — planner designs `CREATE TABLE` + `INSERT OR REPLACE` pattern; must handle concurrent read safety (WAL mode?).
- **MCP `wiki_query` input schema** — exact Pydantic fields (query string, vault_path, top_k, json output flag); planner designs.
- **MCP progress notifications (MCP-06)** — when and how to emit `notifications/progress` during librarian fan-out; planner designs.
- **`--config` and vault path resolution** — how `query` finds the vault (from `.lattice-wiki.json` in the workspace? explicit `--vault` flag?); researcher checks Phase 1 `_workspace.py` port.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 3" — phase goal, success criteria, requirement list (SEARCH-01..06, CMD-04, CMD-07, CMD-08, MCP-02, MCP-04, MCP-06, MCP-07, CLI-01..07)
- `.planning/REQUIREMENTS.md` §"Search" (SEARCH-01..06) + §"Commands" (CMD-04, CMD-07, CMD-08) + §"MCP Server Surface" (MCP-02, MCP-04, MCP-06, MCP-07) + §"Headless CLI" (CLI-01..07) — full requirement text
- `.planning/STATE.md` §"Active TODOs" — embedding model was flagged as an open TODO; now resolved (Titan v2)
- `.planning/PROJECT.md` §"Constraints" + §"Key Decisions" — Bedrock-only, read-compatible vaults, MCP primary surface

### Prior Phase CONTEXT (critical — sets patterns this phase extends)
- `.planning/phases/02-subagent-fan-out-runtime/02-CONTEXT.md` — D-04 (SubagentPool API: `run_all(items, task, role, model_id, max_concurrency)`), D-05 (task owns model via closure), D-06 (`FanOutResult` dataclass), D-09 (tokens from `usage_metadata`), D-10 (trace writer in subagent-runtime)
- `.planning/phases/01-infrastructure-vault-io-and-mcp-skeleton/01-CONTEXT.md` — D-13 (`wiki_ping` pattern for MCP tool registration), D-14 (`code-wiki-mcp` entry point), D-15 (stdout guard)

### Existing Code — Phase 1 & 2 Deliverables
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool.run_all()` API; `FanOutResult`, `PerItemError` types; trace writing; semaphore pattern
- `cores/model-adapter/src/model_adapter/models.toml` — `librarian` (Haiku, 2048t, 5c) and `synthesizer` (Sonnet, 4096t, 3c) role config; `make_llm(role)` is the resolver
- `cores/model-adapter/src/model_adapter/loader.py` — `make_llm(role)` implementation; how to call
- `cores/vault-io/src/vault_io/_workspace.py` — vault and repo path resolution; how query finds the vault
- `cores/vault-io/src/vault_io/update_index.py` — index.md format; query reads this first
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — `wiki_ping` tool as the pattern for wiring MCP tools; stdout guard; `FastMCP` + Pydantic input/output schemas
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — existing Typer app; `query` subcommand adds to this file

### Source Reference (lattice-wiki-core — what we're porting semantics from)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py` — current BM25-only search implementation; Phase 3 replaces with bm25s + Titan embedding hybrid, but the tokenization approach (TOKEN_RE + stopwords) and skip-list (index.md, log.md, dot-prefixed dirs) are reference behavior
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py` — index.md format the query command reads first

### External Documentation (researcher should verify)
- langchain-aws `BedrockEmbeddings`: Context7 `/langchain-ai/langchain-aws` — `BedrockEmbeddings` class, model ID format, batch size limits for Titan v2
- bm25s docs: Context7 or PyPI `bm25s` 0.3.8 — tokenizer API, `save()`/`load()` directory format, Okapi BM25 variant
- AWS Bedrock Titan Embeddings v2: `https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html` — model ID, dimensions (1536), token limits
- MCP spec (progress notifications): `https://modelcontextprotocol.io/docs/develop/build-server` §notifications — `notifications/progress` format for long-running tools

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SubagentPool.run_all(items, task, role, model_id, max_concurrency)` in `cores/subagent-runtime/src/subagent_runtime/pool.py` — Phase 3's librarian fan-out calls this directly. `task` closure owns `make_llm("librarian")`. Returns `FanOutResult` with partial-failure isolation.
- `make_llm("librarian")` / `make_llm("synthesizer")` in `cores/model-adapter` — resolves to Haiku / Sonnet respectively from models.toml; no changes needed.
- `_workspace.py` in `cores/vault-io` — resolves vault + repo paths; `query` uses this to locate the vault (same pattern as all other commands).
- `wiki_ping` in `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — the established pattern for FastMCP tool registration with Pydantic input/output schemas; `wiki_query` follows the same structure.
- `_StdoutGuard` already installed — no stdout writes anywhere in `commands/query.py` or the search index; all logging via `logging` to stderr.

### Established Patterns
- **Workspace member structure** — `agents/code-wiki-agent/src/code_wiki_agent/commands/` is a new subpackage (flat module `commands/query.py`). No new workspace member needed.
- **`@pytest.mark.integration` + `CODE_WIKI_RUN_INTEGRATION=1`** — the end-to-end fixture-vault integration test (success criterion 5) follows this skip pattern from Phase 2.
- **`FanOutResult` partial-failure** — if a librarian call fails on one page, `run_all()` returns the successes; synthesizer proceeds with whatever excerpts landed. Query degrades gracefully.
- **JSONL trace output** — `SubagentPool` writes traces automatically; query gets OBS-01 compliance for free.

### Integration Points
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — Phase 3 adds the `query` subcommand to the existing Typer `app` object (alongside `version` and `trace`).
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — Phase 3 registers `wiki_query` tool on the existing `mcp` FastMCP instance (alongside `wiki_ping`).
- `.code-wiki/traces/` — already created by SubagentPool in Phase 2; query writes librarian traces there.
- `.code-wiki/search.db` and `.code-wiki/bm25/` — new directories/files created by Phase 3; `.code-wiki/` is the established base dir from Phase 2's trace design.

</code_context>

<specifics>
## Specific Ideas

- The integration test (success criterion 5) should run `code-wiki-agent query` in headless CLI mode against the committed fixture vault (`tests/fixtures/round-trip-vault/`) and assert the answer contains at least one valid `[[wikilink]]` citation. Uses `@pytest.mark.integration` + `CODE_WIKI_RUN_INTEGRATION=1` skip pattern.
- `--json` output from `query` should serialize `QueryResult` to JSON including `search_scores` per page (BM25 raw score, cosine similarity, RRF fused score) for SEARCH-06 compliance.
- The librarian prompt should receive: (1) the original query, (2) the full page text. Its job is to extract the most relevant excerpt(s) from that page in relation to the query — not to answer. The synthesizer receives all excerpts and produces the final answer.
- `bm25s` replaces the hand-rolled BM25 in `lattice-wiki-core/wiki_search.py` (which uses a custom tokenizer and pure Python scoring). The skip-list for vault pages remains the same: skip `index.md`, `log.md`, and any path with a dot-prefixed component.

</specifics>

<deferred>
## Deferred Ideas

- **`cores/wiki-search` package** — if a second agent needs search in v2, extract `commands/query.py` into a shared core then. Not worth the overhead for one agent in v1.
- **Cost accounting (`cost_usd`)** — trace records have `"cost_usd": null` until Phase 4 adds the pricing layer.
- **File-write-back after query** (`--write-back` option to persist the answer into the vault) — mentioned as "optional" in CMD-04; deferred. Not in Phase 3 scope.
- **`--stale-days` / `--log-gap-days` thresholds** — applicable to lint (CMD-05), not to query. Phase 5 concern.
- **Embedding dimension tuning** — Titan v2 supports multiple output dimensions (256, 512, 1024 via `normalize` param). Using the default 1536 in v1; revisit if storage becomes a concern.

</deferred>

---

*Phase: 3-Query Vertical Slice + Hybrid Search*
*Context gathered: 2026-05-13*
