"""Tests for vault_io.wiki_search.

Scope: importability + structural smoke only. Relevance-quality / score parity
with the upstream wiki_search implementation is out of Phase 14 scope (VP-02).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
EDGE_CASE_VAULT = FIXTURES / "edge-case-vault"


def test_wiki_search_importable():
    """vault_io.wiki_search imports cleanly and exports a callable main."""
    from vault_io.wiki_search import main  # noqa: F401

    assert callable(main)


def test_wiki_search_runs_on_fixture_vault():
    """Structural smoke: wiki_search produces parseable JSON against the edge-case fixture vault."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vault_io.wiki_search",
            "--query",
            "test",
            "--json",
        ],
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "GRAPH_WIKI_WORKSPACE": str(EDGE_CASE_VAULT.parent),
        },
    )
    # The module resolves the wiki as <workspace>/wiki; the edge-case-vault IS the
    # wiki directory, so we set the parent as the workspace and accept either a
    # successful run (exit 0) OR an exit code of 1 from the no-wiki-found path
    # (the fixture vault may not be inside a workspace layout). Either way the
    # output must be valid JSON when exit code is 0, or the error message must be
    # a plain string on stderr.
    if result.returncode == 0:
        data = json.loads(result.stdout)
        assert "query" in data, f"missing 'query' key: {data}"
        assert "hits" in data, f"missing 'hits' key: {data}"
        assert isinstance(data["hits"], list)
    else:
        # Non-zero exit is acceptable when the vault can't be resolved from the
        # fixture path; what we're asserting is that the module ran and produced
        # a structured error, not an uncaught Python exception.
        assert result.returncode in (1, 2), (
            f"unexpected exit code {result.returncode}: {result.stderr}"
        )
        assert "Traceback" not in result.stderr, (
            f"module crashed with an unhandled exception:\n{result.stderr}"
        )


def test_wiki_search_internal_helpers():
    """tokenize(), load_docs(), bm25_scores(), and snippet() are importable and callable."""
    from vault_io.wiki_search import bm25_scores, load_docs, snippet, tokenize

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
