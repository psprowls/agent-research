from __future__ import annotations

"""Unit tests for the hybrid search layer (Plan 02).

Covers: SEARCH-01 through SEARCH-05.
All tests use tmp_path fixture; no real Bedrock calls.
"""

import sqlite3
import struct
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from graph_wiki_agent.commands.query import (
    _build_tokenizer,
    _discover_pages,
    _rrf_fuse,
    _cosine_search_sqlite,
    build_index,
    bm25_query,
)


# ---------------------------------------------------------------------------
# Task 1 tests: tokenizer, page discovery, RRF, cosine scan
# ---------------------------------------------------------------------------


def test_tokenizer_splits_camel_case_and_filters_stopwords() -> None:
    """Tokenizer uses TOKEN_RE pattern and filters stopwords from _STOPWORDS."""
    tokenizer = _build_tokenizer()
    # tokenize() returns list of lists of integer token IDs in bm25s 0.3.8
    # Recover strings via word_to_id reverse map
    result = tokenizer.tokenize(["The SubagentPool and fan-out logic"])
    id_to_word = {v: k for k, v in tokenizer.word_to_id.items()}
    tokens = [id_to_word[tid] for tid in result[0] if tid in id_to_word]

    assert "subagentpool" in tokens, f"Expected 'subagentpool' in {tokens}"
    assert "fan-out" in tokens, f"Expected 'fan-out' in {tokens}"
    # stopwords filtered
    assert "the" not in tokens, f"Expected 'the' filtered from {tokens}"
    assert "and" not in tokens, f"Expected 'and' filtered from {tokens}"


def test_discover_pages_skips_index_and_log_and_dot_dirs(tmp_path: Path) -> None:
    """_discover_pages returns only content pages in POSIX path format."""
    # Create vault structure
    (tmp_path / "concepts").mkdir()
    (tmp_path / "concepts" / "a.md").write_text("Page A content")
    (tmp_path / "concepts" / "b.md").write_text("Page B content")
    (tmp_path / "index.md").write_text("Index page — should be skipped")
    (tmp_path / "log.md").write_text("Log page — should be skipped")
    # Dot-prefixed directories should be skipped
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.md").write_text("Git file — should be skipped")
    (tmp_path / ".templates").mkdir()
    (tmp_path / ".templates" / "t.md").write_text("Template — should be skipped")

    pages = _discover_pages(tmp_path)
    paths = [p for p, _ in pages]

    assert "concepts/a.md" in paths, f"Expected concepts/a.md in {paths}"
    assert "concepts/b.md" in paths, f"Expected concepts/b.md in {paths}"
    assert "index.md" not in paths, "index.md should be skipped"
    assert "log.md" not in paths, "log.md should be skipped"
    # dot-prefixed dirs
    assert not any(".git" in p for p in paths), ".git/ files should be skipped"
    assert not any(".templates" in p for p in paths), ".templates/ files should be skipped"
    # POSIX paths (no backslashes)
    for path in paths:
        assert "\\" not in path, f"Path should be POSIX (no backslashes): {path}"


def test_rrf_fuse_combines_ranks() -> None:
    """RRF fusion: pages with symmetric rank-sums produce equal scores."""
    # a gets rank 1 in bm25 and rank 3 in embed -> sum = 4
    # c gets rank 3 in bm25 and rank 1 in embed -> sum = 4
    # b gets rank 2 in both -> sum = 4 as well... wait, let's use the plan's test case
    # Per plan: _rrf_fuse({"a":1,"b":2,"c":3}, {"a":3,"b":2,"c":1}, k=60)
    # a: 1/(60+1) + 1/(60+3) = 1/61 + 1/63
    # c: 1/(60+3) + 1/(60+1) = 1/63 + 1/61
    # So a == c
    scores = _rrf_fuse({"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 2, "c": 1}, k=60)
    assert set(scores.keys()) == {"a", "b", "c"}
    # a and c should have equal scores (symmetric rank assignment)
    assert abs(scores["a"] - scores["c"]) < 1e-9, (
        f"Expected scores[a] == scores[c], got {scores['a']} vs {scores['c']}"
    )
    # b gets rank 2 in both signals: score = 2 * 1/(60+2) = 2/62
    # a/c get: 1/61 + 1/63 -- which is > 2/62 because 1/61 > 1/62 and 1/63 < 1/62
    # Actually let's just check b is different from a
    assert scores["b"] != scores["a"], "b should have a different score than a/c"


def test_rrf_fuse_missing_in_one_map() -> None:
    """Page in only one rank map scores lower than a page in both."""
    # "both" appears in both maps with rank 1
    # "bm25_only" appears only in bm25 with rank 1
    scores = _rrf_fuse(
        bm25_ranks={"both": 1, "bm25_only": 1},
        embed_ranks={"both": 1},
        k=60,
    )
    assert "both" in scores
    assert "bm25_only" in scores
    # "both" appears in both maps -> higher score
    assert scores["both"] > scores["bm25_only"], (
        f"Expected both({scores['both']}) > bm25_only({scores['bm25_only']})"
    )


def _make_vec(dim: int, hot_index: int, value: float = 1.0) -> list[float]:
    """Create a unit vector with a single non-zero dimension."""
    vec = [0.0] * dim
    vec[hot_index] = value
    return vec


def _write_page_to_db(db_path: Path, path: str, vec: list[float], content_hash: str = "abc") -> None:
    """Insert a page with a known embedding blob into search.db."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pages "
        "(path TEXT PRIMARY KEY, content_hash TEXT NOT NULL, embedding BLOB NOT NULL)"
    )
    blob = struct.pack(f"{len(vec)}f", *vec)
    conn.execute(
        "INSERT OR REPLACE INTO pages (path, content_hash, embedding) VALUES (?, ?, ?)",
        (path, content_hash, blob),
    )
    conn.commit()
    conn.close()


def test_cosine_search_sqlite_orders_by_similarity(tmp_path: Path) -> None:
    """Cosine scan returns most similar page first."""
    dim = 1024
    # vec1: hot on dimension 0
    vec1 = _make_vec(dim, 0)
    # vec2: hot on dimension 1
    vec2 = _make_vec(dim, 1)

    db_path = tmp_path / ".graph-wiki" / "search.db"
    _write_page_to_db(db_path, "page1.md", vec1, "hash1")
    _write_page_to_db(db_path, "page2.md", vec2, "hash2")

    # Query vector aligned to vec1 (dimension 0)
    query_vec = _make_vec(dim, 0)
    results = _cosine_search_sqlite(tmp_path, query_vec, top_k=2)

    assert len(results) == 2
    assert results[0][0] == "page1.md", f"Expected page1.md first, got {results[0][0]}"
    assert results[0][1] > results[1][1], "page1 should have higher cosine score than page2"


# ---------------------------------------------------------------------------
# Task 2 tests: build_index + bm25_query
# ---------------------------------------------------------------------------


def _make_fake_embed(text_to_vec_map: dict[str, list[float]] | None = None):
    """Return a fake embed_query function that returns deterministic vectors."""
    dim = 1024

    def fake_embed(self: object, text: str) -> list[float]:
        if text_to_vec_map and text in text_to_vec_map:
            return text_to_vec_map[text]
        # Hash-derived: vary first float by hash so each text gets a unique vector
        h = int(hashlib.sha256_of_text(text) % 1000) if hasattr(hashlib, "sha256_of_text") else (
            int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big") % 1000
        )
        vec = [0.1] * dim
        vec[0] = float(h) / 1000.0
        return vec

    return fake_embed


import hashlib as _hashlib


def _fake_embed_deterministic(self: object, text: str) -> list[float]:
    """Deterministic fake embed: varies first two elements by content hash."""
    dim = 1024
    h = int.from_bytes(_hashlib.sha256(text.encode()).digest()[:4], "big") % 1000
    vec = [0.1] * dim
    vec[0] = float(h) / 1000.0
    vec[1] = float(h % 100) / 100.0
    return vec


def _setup_vault(tmp_path: Path, pages: dict[str, str]) -> Path:
    """Create a vault directory with the given {rel_path: content} pages."""
    vault = tmp_path / "vault"
    vault.mkdir()
    for rel_path, content in pages.items():
        full = vault / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return vault


def test_build_index_creates_bm25_and_sqlite(tmp_path: Path) -> None:
    """build_index creates .graph-wiki/bm25/ (non-empty) and .graph-wiki/search.db (WAL mode)."""
    vault = _setup_vault(tmp_path, {
        "concepts/alpha.md": "Alpha is the first letter",
        "concepts/beta.md": "Beta is the second letter",
        "concepts/gamma.md": "Gamma is the third letter",
    })

    with patch("graph_wiki_agent.commands.query.BedrockEmbeddings") as MockEmbed:
        instance = MockEmbed.return_value
        instance.embed_query.side_effect = _fake_embed_deterministic.__func__ if hasattr(
            _fake_embed_deterministic, "__func__"
        ) else lambda text: _fake_embed_deterministic(None, text)
        # Simpler: just return a list directly
        instance.embed_query.side_effect = None
        instance.embed_query.return_value = [0.1] * 1024

        build_index(vault)

    bm25_dir = vault / ".graph-wiki" / "bm25"
    assert bm25_dir.exists(), ".graph-wiki/bm25/ should exist after build_index"
    assert any(bm25_dir.iterdir()), ".graph-wiki/bm25/ should be non-empty"

    db_path = vault / ".graph-wiki" / "search.db"
    assert db_path.exists(), ".graph-wiki/search.db should exist after build_index"

    # Verify WAL mode
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("PRAGMA journal_mode").fetchone()
    conn.close()
    assert row[0] == "wal", f"Expected WAL mode, got {row[0]}"


def test_incremental_skip_unchanged_hash(tmp_path: Path) -> None:
    """Second build_index call with unchanged pages invokes embed_query zero additional times."""
    vault = _setup_vault(tmp_path, {
        "concepts/a.md": "Content of page A",
        "concepts/b.md": "Content of page B",
    })

    call_count = 0

    def counting_embed(text: str) -> list[float]:
        nonlocal call_count
        call_count += 1
        return [0.1] * 1024

    with patch("graph_wiki_agent.commands.query.BedrockEmbeddings") as MockEmbed:
        MockEmbed.return_value.embed_query.side_effect = counting_embed
        build_index(vault)

    first_call_count = call_count  # should be 2 (one per page)

    # Second call — same content, no changes
    with patch("graph_wiki_agent.commands.query.BedrockEmbeddings") as MockEmbed:
        MockEmbed.return_value.embed_query.side_effect = counting_embed
        build_index(vault)

    second_call_count = call_count - first_call_count
    assert second_call_count == 0, (
        f"Expected 0 embed_query calls on second build with unchanged pages, got {second_call_count}"
    )


def test_one_page_changed_reembeds_only_that_page(tmp_path: Path) -> None:
    """When one page changes, only that page is re-embedded on the second build."""
    vault = _setup_vault(tmp_path, {
        "concepts/a.md": "Content of page A — original",
        "concepts/b.md": "Content of page B — never changes",
        "concepts/c.md": "Content of page C — original",
    })

    call_count = 0

    def counting_embed(text: str) -> list[float]:
        nonlocal call_count
        call_count += 1
        return [0.1] * 1024

    with patch("graph_wiki_agent.commands.query.BedrockEmbeddings") as MockEmbed:
        MockEmbed.return_value.embed_query.side_effect = counting_embed
        build_index(vault)

    first_call_count = call_count  # should be 3

    # Change only page A
    (vault / "concepts" / "a.md").write_text("Content of page A — MODIFIED")

    with patch("graph_wiki_agent.commands.query.BedrockEmbeddings") as MockEmbed:
        MockEmbed.return_value.embed_query.side_effect = counting_embed
        build_index(vault)

    second_call_count = call_count - first_call_count
    assert second_call_count == 1, (
        f"Expected exactly 1 embed_query call after changing one page, got {second_call_count}"
    )


def test_bm25_query_ranks_target_page_first(tmp_path: Path) -> None:
    """Page with unique term appears at top of bm25_query results."""
    vault = _setup_vault(tmp_path, {
        "concepts/kafka.md": "This page is about kafkaesque bureaucratic processes",
        "concepts/lambda.md": "Lambda functions are anonymous function literals",
        "concepts/monad.md": "Monads are a design pattern from category theory",
    })

    with patch("graph_wiki_agent.commands.query.BedrockEmbeddings") as MockEmbed:
        MockEmbed.return_value.embed_query.return_value = [0.1] * 1024
        build_index(vault)

    paths, scores = bm25_query("kafkaesque", vault, top_k=3)

    assert len(paths) >= 1, "Expected at least one result"
    assert paths[0] == "concepts/kafka.md", (
        f"Expected concepts/kafka.md first, got {paths[0]}"
    )


def test_bm25_query_vocab_frozen_handles_unseen_term(tmp_path: Path) -> None:
    """Query with a word never seen at index time returns normally without raising."""
    vault = _setup_vault(tmp_path, {
        "concepts/alpha.md": "Alpha is the first letter of the Greek alphabet",
        "concepts/beta.md": "Beta is the second letter of the Greek alphabet",
    })

    with patch("graph_wiki_agent.commands.query.BedrockEmbeddings") as MockEmbed:
        MockEmbed.return_value.embed_query.return_value = [0.1] * 1024
        build_index(vault)

    # "zymurgy" was never seen at index time — should not raise
    paths, scores = bm25_query("zymurgy", vault, top_k=2)
    # May return empty results or low scores — just must not raise
    assert isinstance(paths, list)
    assert isinstance(scores, list)
