"""Tests for wiki_io.wiki_search.

Scope: importability + structural smoke only. Relevance-quality / score parity
with the upstream wiki_search implementation is out of Phase 14 scope (VP-02).
"""

from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
EDGE_CASE_VAULT = FIXTURES / "edge-case-vault"


def test_wiki_search_importable():
    """wiki_io.wiki_search imports cleanly and exports library helpers."""
    from wiki_io import wiki_search

    assert callable(wiki_search.load_docs)
    assert callable(wiki_search.tokenize)
    assert callable(wiki_search.bm25_scores)
    assert callable(wiki_search.snippet)
    assert not hasattr(wiki_search, "main")


def test_wiki_search_internal_helpers():
    """tokenize(), load_docs(), bm25_scores(), and snippet() are importable and callable."""
    from wiki_io.wiki_search import bm25_scores, load_docs, snippet, tokenize

    # tokenize — basic contract
    tokens = tokenize("middleware pipeline integration")
    assert isinstance(tokens, list)
    assert "middleware" in tokens
    assert "pipeline" in tokens

    # load_docs — runs against the edge-case-vault fixture
    docs = load_docs(EDGE_CASE_VAULT)
    assert isinstance(docs, list)
    # edge-case-vault has concepts/*.md files (excluding index.md and log.md)
    assert len(docs) > 0, "load_docs() returned no documents from edge-case-vault"
    first = docs[0]
    assert "path" in first
    assert "tokens" in first
    assert "tf" in first
    assert "len" in first

    # bm25_scores — returns a list of (index, score) tuples
    qtokens = tokenize("test concept")
    scores = bm25_scores(docs, qtokens)
    assert isinstance(scores, list)
    for item in scores:
        assert len(item) == 2
        idx, score = item
        assert isinstance(idx, int)
        assert isinstance(score, float)

    # snippet — returns a string
    sample_text = "This is a test of the snippet helper function."
    result = snippet(sample_text, ["test"])
    assert isinstance(result, str)
    assert len(result) > 0
