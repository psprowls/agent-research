# Phase 3: Query Vertical Slice + Hybrid Search - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 3-Query Vertical Slice + Hybrid Search
**Areas discussed:** Embedding model, Index persistence format, Command layer architecture, State gate for read-only query

---

## Embedding Model

| Option | Description | Selected |
|--------|-------------|----------|
| Titan Embeddings G1 v2 | Amazon-native, no extra IAM, 1536 dims, langchain-aws supported | ✓ |
| Cohere Embed v3 | Higher benchmark scores, 1024 dims, requires separate Bedrock grant | |
| You decide (researcher picks) | Defer to researcher based on account access | |

**User's choice:** Titan Embeddings G1 v2
**Notes:** Chosen for IAM simplicity (already proven in Phase 1) and native langchain-aws support.

---

## Incremental Rebuild Check

| Option | Description | Selected |
|--------|-------------|----------|
| Content hash (sha256 of page text) | Hash raw markdown; deterministic; stored in search.db | ✓ |
| File mtime | Faster check; can miss same-content overwrites; fragile on git checkout | |
| You decide | Researcher picks cheapest reliable strategy | |

**User's choice:** sha256 content hash
**Notes:** Matches the spirit of the Phase 1 round-trip golden gate — deterministic and content-based.

---

## Hybrid Fusion Algorithm

| Option | Description | Selected |
|--------|-------------|----------|
| RRF — Reciprocal Rank Fusion (k=60) | Parameter-free: score = 1/(k+rank_bm25) + 1/(k+rank_embed) | ✓ |
| Weighted sum with configurable alpha | score = alpha*bm25_norm + (1-alpha)*embed_norm; requires tuning | |
| You decide | Researcher picks based on bm25s integration | |

**User's choice:** RRF (k=60)
**Notes:** No tuning required; well-established in retrieval literature.

---

## Index Persistence Format

| Option | Description | Selected |
|--------|-------------|----------|
| SQLite — one file, stdlib | `.code-wiki/search.db`; no extra deps; queryable for debugging | ✓ |
| NumPy array + JSON manifest | Pure NumPy; sequential reads fast; harder for incremental updates | |
| You decide | Researcher picks based on bm25s format | |

**User's choice:** SQLite for embeddings at `.code-wiki/search.db`
**Notes:** Initially selected "bm25s alongside embeddings in SQLite" (single file), then clarified to two separate stores: SQLite for embeddings, bm25s native directory (`.code-wiki/bm25/`) for BM25. The consolidation into a single SQLite blob was explored and rejected in favor of the simpler dual-store approach.

---

## Command Layer Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| agents/code-wiki-agent/commands/ | Command logic in agent package; CLI + MCP both import it | ✓ |
| New cores/wiki-search package | Shared reusable core; consistent with tiered design | |
| You decide | Planner picks given one-agent-in-v1 constraint | |

**User's choice:** Agent-owned in `code_wiki_agent/commands/query.py`
**Notes:** Only one agent in v1; extract to cores if a second agent needs it in v2.

---

## QueryResult Return Type

| Option | Description | Selected |
|--------|-------------|----------|
| QueryResult dataclass | `answer`, `citations`, `pages_drilled`, `search_scores`; typed; consistent with FanOutResult | ✓ |
| Plain dict / JSON-serializable mapping | Simpler; less typed; CLI and MCP serialize as-is | |

**User's choice:** QueryResult dataclass
**Notes:** Consistent with Phase 2's FanOutResult / PerItemError pattern.

---

## Default Top-K

| Option | Description | Selected |
|--------|-------------|----------|
| 5 pages | Middle of 3–10 range; configurable via --top-k | ✓ |
| 3 pages | Fast and cheap; may miss context on complex queries | |
| You decide / match lattice-wiki | Researcher reads lattice-wiki query and matches its default | |

**User's choice:** 5 pages (configurable via `--top-k`)

---

## State Gate for Read-Only Query

| Option | Description | Selected |
|--------|-------------|----------|
| Present but always passes (no-op for query) | Flag exists for CLI consistency; git check skipped for read-only | ✓ |
| Warn-and-proceed on dirty git state | Checks git; emits warning; continues | |
| Block on dirty git state | Treats query like write commands; strictest interpretation of CMD-08 | |

**User's choice:** Gate interface present; underlying check is a no-op for query
**Notes:** Query is read-only — blocking on dirty git would be false-positive friction. The flag exists for interface consistency with other commands.

---

## Claude's Discretion

- **Exact Titan embedding model ID / cross-region ARN** — researcher confirms current naming against Pat's account
- **BedrockEmbeddings call batching** — researcher determines safe batch size for Titan v2's token limits
- **bm25s tokenizer settings** — whether to use bm25s built-in or replicate lattice-wiki-core's TOKEN_RE + stopwords
- **search.db DDL and upsert pattern** — planner designs CREATE TABLE + INSERT OR REPLACE; WAL mode consideration
- **MCP wiki_query input schema** — Pydantic fields; planner designs
- **MCP progress notifications (MCP-06)** — when and how to emit during librarian fan-out; planner designs
- **Vault path resolution in query** — researcher checks Phase 1 `_workspace.py` port

## Deferred Ideas

- `cores/wiki-search` package — extract if a second agent needs search in v2
- `cost_usd` accounting — null until Phase 4 adds pricing layer
- File-write-back after query (`--write-back`) — CMD-04 mentions it as optional; deferred
- Titan v2 dimension tuning (256/512/1024 via normalize param) — using default 1536 in v1
