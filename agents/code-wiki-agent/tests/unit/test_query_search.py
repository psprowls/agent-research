from __future__ import annotations

"""Stub tests for the hybrid search layer (Plan 02 deliverable).

These stubs exist so the test runner discovers Phase 3 search tests from
Wave 0 onwards. All tests are marked xfail until Plan 02 implements the
search module at code_wiki_agent.commands.query (BM25 index, embedding
retrieval, RRF fusion, SQLite store, incremental hashing).

Requirements covered: SEARCH-01 through SEARCH-05.
"""

import pytest


@pytest.mark.xfail(reason="Implemented in Plan 02", strict=False)
def test_bm25_index_build_and_query() -> None:
    """BM25 index builds from vault pages and returns ranked results (SEARCH-01)."""
    assert False, "stub — Plan 02"


@pytest.mark.xfail(reason="Implemented in Plan 02", strict=False)
def test_embedding_shape_1024() -> None:
    """Bedrock embedding call returns 1024-dim vector per page (SEARCH-02, mock embed)."""
    assert False, "stub — Plan 02"


@pytest.mark.xfail(reason="Implemented in Plan 02", strict=False)
def test_rrf_fuse() -> None:
    """Reciprocal Rank Fusion combines BM25 and embedding scores correctly (SEARCH-03)."""
    assert False, "stub — Plan 02"


@pytest.mark.xfail(reason="Implemented in Plan 02", strict=False)
def test_sqlite_store_wal_mode() -> None:
    """SQLite vector/index store opens with WAL journal mode (SEARCH-04)."""
    assert False, "stub — Plan 02"


@pytest.mark.xfail(reason="Implemented in Plan 02", strict=False)
def test_incremental_skip_unchanged_hash() -> None:
    """Incremental indexer skips pages whose content hash has not changed (SEARCH-05)."""
    assert False, "stub — Plan 02"
