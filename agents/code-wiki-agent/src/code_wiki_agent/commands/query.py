from __future__ import annotations

"""Hybrid BM25 + embedding search layer for code-wiki-agent.

Public API (Plan 02):
    build_index(vault_path)          -- Build/refresh BM25 + SQLite embedding index
    bm25_query(query_text, vault_path, top_k) -- Query the BM25 index
    _build_tokenizer()               -- bm25s Tokenizer matching lattice-wiki-core behavior
    _discover_pages(vault_path)      -- Vault page discovery with skip-list
    _rrf_fuse(bm25_ranks, embed_ranks, k) -- Reciprocal Rank Fusion
    _cosine_search_sqlite(vault_path, query_vec, top_k) -- Cosine similarity search

Plan 03 will add: run_query(), QueryResult, librarian fan-out, synthesizer.
"""

import hashlib
import logging
import math
import re
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path

import bm25s
from bm25s.tokenization import Tokenizer
from langchain_aws import BedrockEmbeddings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_TOKEN_RE_PATTERN = r"[a-zA-Z0-9][a-zA-Z0-9_\-']+"

# Full stopword set copied verbatim from lattice-wiki-core wiki_search.py
# (Open Question 3 from RESEARCH.md — use the full ~60-word set)
_STOPWORDS: frozenset[str] = frozenset({
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "if",
    "then",
    "so",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "by",
    "with",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "as",
    "we",
    "you",
    "they",
    "their",
    "our",
    "us",
    "i",
    "not",
    "no",
    "yes",
    "do",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "should",
    "about",
    "into",
    "than",
    "out",
    "up",
    "down",
    "over",
    "under",
    "also",
})

_BM25_SUBDIR = "bm25"          # relative to .code-wiki/
_SEARCH_DB_NAME = "search.db"  # filename under .code-wiki/

# SQLite DDL — used by build_index; defined here for reuse
_DDL_PAGES = """
CREATE TABLE IF NOT EXISTS pages (
    path         TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    embedding    BLOB NOT NULL
)
"""
_PRAGMA_WAL = "PRAGMA journal_mode=WAL"


# ---------------------------------------------------------------------------
# Helper: tokenizer
# ---------------------------------------------------------------------------


def _build_tokenizer() -> Tokenizer:
    """Return a bm25s Tokenizer replicating lattice-wiki-core's TOKEN_RE behavior."""
    return Tokenizer(
        lower=True,
        splitter=_TOKEN_RE_PATTERN,
        stopwords=list(_STOPWORDS),
    )


# ---------------------------------------------------------------------------
# Helper: page discovery
# ---------------------------------------------------------------------------


def _discover_pages(vault_path: Path) -> list[tuple[str, str]]:
    """Walk vault_path and return [(posix_rel_path, page_text), ...] sorted.

    Skip rules (matching lattice-wiki-core reference behavior):
    - rel.name in {"index.md", "log.md"}
    - any path component starts with "." (e.g. .git/, .templates/)
    """
    results: list[tuple[str, str]] = []
    for md in sorted(vault_path.rglob("*.md")):
        rel = md.relative_to(vault_path)
        if rel.name in {"index.md", "log.md"}:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        posix_path = str(rel).replace("\\", "/")
        results.append((posix_path, text))
    return results


# ---------------------------------------------------------------------------
# Helper: RRF fusion
# ---------------------------------------------------------------------------


def _rrf_fuse(
    bm25_ranks: dict[str, int],
    embed_ranks: dict[str, int],
    k: int = 60,
) -> dict[str, float]:
    """Reciprocal Rank Fusion.

    score(p) = 1/(k + rank_bm25(p)) + 1/(k + rank_embed(p))

    Missing pages use sentinel rank = n + k where n = len(all_pages).
    """
    all_pages = set(bm25_ranks) | set(embed_ranks)
    n = len(all_pages)
    return {
        p: 1.0 / (k + bm25_ranks.get(p, n + k)) + 1.0 / (k + embed_ranks.get(p, n + k))
        for p in all_pages
    }


# ---------------------------------------------------------------------------
# Helper: cosine search over SQLite
# ---------------------------------------------------------------------------


def _cosine_search_sqlite(
    vault_path: Path,
    query_vec: list[float],
    top_k: int,
) -> list[tuple[str, float]]:
    """Linear cosine scan over embeddings in search.db.

    Opens and closes the connection per call (no module-level state).
    Returns list of (page_path, cosine_score) sorted descending.
    """
    db_path = vault_path / ".code-wiki" / _SEARCH_DB_NAME
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT path, embedding FROM pages").fetchall()
    finally:
        conn.close()

    q_mag = math.sqrt(sum(x * x for x in query_vec))
    results: list[tuple[str, float]] = []
    for path, blob in rows:
        vec = struct.unpack(f"{len(blob) // 4}f", blob)
        dot = sum(a * b for a, b in zip(query_vec, vec))
        v_mag = math.sqrt(sum(x * x for x in vec))
        score = dot / (q_mag * v_mag) if (q_mag and v_mag) else 0.0
        results.append((path, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


# ---------------------------------------------------------------------------
# Public: build_index
# ---------------------------------------------------------------------------


def build_index(vault_path: Path) -> None:
    """Build/refresh BM25 and embedding indexes for the vault.

    BM25 index: always rebuilt from scratch (cheap for small vaults).
    Embedding index: incremental via sha256 content hash (D-02 / SEARCH-05).

    Threat model T-03-07: WAL mode enables safe concurrent reads during rebuild.
    Threat model T-03-06: log WARNING for pages exceeding 32000 chars.
    """
    pages = _discover_pages(vault_path)
    if not pages:
        logger.warning("build_index: no pages discovered in %s", vault_path)
        return

    # ---- BM25 ----
    bm25_dir = vault_path / ".code-wiki" / _BM25_SUBDIR
    bm25_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Rebuilding BM25 index for %d pages", len(pages))
    tokenizer = _build_tokenizer()
    corpus_paths = [path for path, _ in pages]
    corpus_texts = [text for _, text in pages]
    corpus_tokens = tokenizer.tokenize(corpus_texts)

    retriever = bm25s.BM25(method="lucene", k1=1.5, b=0.75)
    retriever.index(corpus_tokens)
    retriever.save(str(bm25_dir), corpus=corpus_paths)  # corpus items = page paths
    tokenizer.save_vocab(str(bm25_dir))
    tokenizer.save_stopwords(str(bm25_dir))

    # ---- Embedding index (incremental) ----
    db_path = vault_path / ".code-wiki" / _SEARCH_DB_NAME
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(_PRAGMA_WAL)
        conn.execute(_DDL_PAGES)
        conn.commit()

        embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v2:0",  # no "us." prefix for Titan (Pitfall 2)
            region_name="us-east-1",
            normalize=True,
        )

        for path, text in pages:
            if len(text) > 32000:
                logger.warning(
                    "Page %s exceeds 32000 chars (%d); Titan v2 will truncate at 8192 tokens",
                    path,
                    len(text),
                )
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            row = conn.execute(
                "SELECT content_hash FROM pages WHERE path = ?", (path,)
            ).fetchone()
            if row is not None and row[0] == content_hash:
                continue  # unchanged — skip re-embedding (SEARCH-05 / D-02)

            vec = embeddings.embed_query(text)
            blob = struct.pack(f"{len(vec)}f", *vec)
            conn.execute(
                "INSERT OR REPLACE INTO pages (path, content_hash, embedding) VALUES (?, ?, ?)",
                (path, content_hash, blob),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public: bm25_query
# ---------------------------------------------------------------------------


def bm25_query(
    query_text: str,
    vault_path: Path,
    top_k: int,
) -> tuple[list[str], list[float]]:
    """Load BM25 index and return top-k (page_paths, bm25_scores).

    Vocab is frozen at query time (update_vocab=False) — Pitfall 1 fix.
    """
    bm25_dir = vault_path / ".code-wiki" / _BM25_SUBDIR

    retriever = bm25s.BM25.load(str(bm25_dir), load_corpus=True)

    tokenizer = _build_tokenizer()
    tokenizer.load_vocab(str(bm25_dir))
    tokenizer.load_stopwords(str(bm25_dir))

    # update_vocab=False: prevents expanding the frozen index vocabulary (Pitfall 1)
    query_tokens = tokenizer.tokenize([query_text], update_vocab=False)
    results, scores = retriever.retrieve(query_tokens, k=top_k)

    page_paths = [str(results[0, i]) for i in range(results.shape[1])]
    bm25_scores = [float(scores[0, i]) for i in range(scores.shape[1])]
    return page_paths, bm25_scores
