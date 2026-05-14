---
phase: 03-query-vertical-slice-hybrid-search
plan: "02"
subsystem: search
tags: [search, bm25, embedding, rrf, sqlite, hybrid-search, incremental]
dependency_graph:
  requires: [03-01]
  provides: [build_index, bm25_query, _rrf_fuse, _cosine_search_sqlite, _build_tokenizer, _discover_pages]
  affects: [03-03]
tech_stack:
  added: [bm25s==0.3.8 (already in pyproject from 03-01)]
  patterns:
    - bm25s Tokenizer with return_as="tuple" to produce string-keyed vocab_dict
    - SQLite WAL mode for concurrent read safety
    - struct.pack/unpack for embedding BLOB storage
    - sha256 hash-based incremental rebuild (D-02)
key_files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
  modified:
    - agents/code-wiki-agent/tests/unit/test_query_search.py
decisions:
  - "Use return_as='tuple' in tokenizer.tokenize() to get Tokenized object with string-keyed vocab_dict (required for orjson serialization in retriever.save())"
  - "Extract item['text'] from retrieve() results — bm25s 0.3.8 returns dicts {'id': int, 'text': str} when load_corpus=True"
  - "Full ~60-word STOPWORDS set from lattice-wiki-core (not trimmed AI-SPEC sample)"
metrics:
  duration: "~4 minutes"
  completed: "2026-05-14"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  tests_added: 10
  tests_passing: 10
---

# Phase 3 Plan 2: Hybrid Search Layer Summary

**One-liner:** Pure-Python hybrid BM25 + SQLite embedding search layer with sha256-keyed incremental rebuild and RRF fusion, backed by 10 unit tests with no Bedrock dependency.

## What Was Built

`agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` (324 lines) provides the complete search foundation:

- `_STOPWORDS` — full ~60-word frozenset copied verbatim from lattice-wiki-core
- `_TOKEN_RE_PATTERN` — regex matching lattice-wiki-core reference behavior
- `_build_tokenizer()` — bm25s Tokenizer with lowercase + regex splitter + stopwords
- `_discover_pages(vault_path)` — rglob with skip-list (index.md, log.md, dot-prefixed dirs)
- `_rrf_fuse(bm25_ranks, embed_ranks, k=60)` — Reciprocal Rank Fusion with sentinel rank
- `_cosine_search_sqlite(vault_path, query_vec, top_k)` — linear cosine scan, connection per call
- `build_index(vault_path)` — rebuilds BM25 + embeds new/changed pages, WAL mode SQLite
- `bm25_query(query_text, vault_path, top_k)` — loads frozen index, returns (paths, scores)

`agents/code-wiki-agent/tests/unit/test_query_search.py` (340 lines) replaces all 5 xfail stubs with 10 real unit tests, all passing.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | f6dd439 | Search helpers — tokenizer, page discovery, RRF, cosine scan |
| Task 2 | 8c42872 | build_index + bm25_query with sha256 incremental rebuild |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] bm25s tokenize() returns integer IDs, not string tokens**
- **Found during:** Task 2 (build_index test failure)
- **Issue:** `tokenizer.tokenize(texts)` returns `[[1, 2, 3], ...]` (integer IDs). When passed to `retriever.index()` and then `retriever.save()`, the `vocab_dict` had integer keys, causing `orjson.dumps()` to raise `TypeError: Dict key must be str`.
- **Fix:** Use `return_as="tuple"` in `tokenizer.tokenize()` to get a `Tokenized` object whose `vocab_dict` has string keys (e.g., `{'alpha': 1, 'beta': 2}`).
- **Files modified:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`
- **Commit:** 8c42872

**2. [Rule 1 - Bug] bm25s retrieve() returns dict corpus items, not plain strings**
- **Found during:** Task 2 (test for bm25_query ranking)
- **Issue:** When `load_corpus=True`, `retriever.retrieve(query_tokens, k=top_k)` returns `results[0, i]` as `{'id': 0, 'text': 'a.md'}` dicts, not plain strings. `str({'id': 0, 'text': 'a.md'})` does not equal `'a.md'`.
- **Fix:** Extract `item['text']` from each corpus item via a `_corpus_text()` helper that checks `isinstance(item, dict)`.
- **Files modified:** `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py`
- **Commit:** 8c42872

**3. [Rule 1 - Bug] Test for tokenizer used vocab attribute that doesn't exist on Tokenizer**
- **Found during:** Task 1 (first test run)
- **Issue:** `tokenizer.vocab` attribute does not exist; the vocabulary is in `tokenizer.word_to_id` (a dict).
- **Fix:** Use `id_to_word = {v: k for k, v in tokenizer.word_to_id.items()}` to recover token strings from IDs.
- **Files modified:** `agents/code-wiki-agent/tests/unit/test_query_search.py`
- **Commit:** f6dd439

## Requirements Coverage

| Requirement | Status | Test |
|-------------|--------|------|
| SEARCH-01 | Done | test_bm25_query_ranks_target_page_first |
| SEARCH-02 | Done | test_build_index_creates_bm25_and_sqlite (mock embed) |
| SEARCH-03 | Done | test_rrf_fuse_combines_ranks, test_rrf_fuse_missing_in_one_map |
| SEARCH-04 | Done | test_build_index_creates_bm25_and_sqlite (WAL mode assertion) |
| SEARCH-05 | Done | test_incremental_skip_unchanged_hash, test_one_page_changed_reembeds_only_that_page |
| SEARCH-06 | Foundation — score dict assembly in Plan 03 run_query() |

## Known Stubs

None. `query.py` exports the full search layer. Plan 03 will add `run_query()`, `QueryResult`, librarian fan-out, and synthesizer on top of these helpers.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes beyond what the threat model (T-03-04 through T-03-07) already covers:
- `_discover_pages` uses `vault_path.rglob("*.md")` rooted at vault_path (T-03-04 mitigated)
- WAL mode active (T-03-07 mitigated)
- Per-page `len(text) > 32000` warning logged (T-03-06 mitigated)
- Bedrock content disclosure is accepted (T-03-05)

## Self-Check

### Created files exist:
- `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` — FOUND
- `agents/code-wiki-agent/tests/unit/test_query_search.py` — FOUND (modified)

### Commits exist:
- f6dd439 — FOUND (feat(03-02): implement search helpers)
- 8c42872 — FOUND (feat(03-02): implement build_index + bm25_query)

### Tests passing:
- 10/10 unit tests green, 0 xfail markers remain

## Self-Check: PASSED
