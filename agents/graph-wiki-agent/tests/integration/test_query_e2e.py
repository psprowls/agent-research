from __future__ import annotations

"""End-to-end integration tests for the query workflow (Plan 04 deliverable).

Gated by CODE_WIKI_RUN_INTEGRATION=1 — never run in CI by default, since
they require real AWS Bedrock access and build the search index on first run
(may take 2-3 minutes).

Requirements covered: CMD-04 SC-5, SEARCH-06, CLI-04.

Module-level FIXTURE_VAULT constant is exposed here for later plans to reuse
(see RESEARCH Pitfall 6 — cross-package path must be precomputed at import time
so test files can use it as a default argument, class attribute, or parametrize
value without re-computing the path on every call).
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

# Cross-package fixture vault path (RESEARCH Pitfall 6).
# Precomputed at import time so downstream plans can reference FIXTURE_VAULT
# as a module-level constant without re-deriving the path.
FIXTURE_VAULT: Path = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages"
    / "vault-io"
    / "tests"
    / "fixtures"
    / "round-trip-vault"
)

# Project root — required for subprocess invocations so uv resolves the workspace
_PROJECT_ROOT: Path = Path(__file__).parent.parent.parent.parent.parent

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


@pytest.mark.integration
@INTEGRATION_GATE
def test_fixture_vault_has_citations() -> None:
    """End-to-end query against round-trip-vault returns wikilink citations (CMD-04 SC-5).

    Asserts:
    - exit code 0 or 3 (partial success per CLI-06)
    - stdout parses as JSON
    - citations has at least one entry OR answer contains [[
    - pages_drilled >= 1
    """
    result = subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "code-wiki-agent",
            "code-wiki-agent",
            "query",
            "What concepts are documented in the wiki?",
            "--vault",
            str(FIXTURE_VAULT),
            "--top-k",
            "3",
            "--json",
        ],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=180,  # generous: first-run index build + Bedrock calls
    )
    assert result.returncode in (0, 3), (
        f"Unexpected exit code {result.returncode}.\nstdout: {result.stdout[:1000]}\nstderr: {result.stderr[:500]}"
    )
    data = json.loads(result.stdout)
    assert data["pages_drilled"] >= 1, f"Expected pages_drilled >= 1, got: {data['pages_drilled']}"
    has_citations = len(data.get("citations", [])) >= 1 or "[[" in data.get("answer", "")
    assert has_citations, (
        f"Expected at least one [[wikilink]] citation in answer.\nanswer: {data.get('answer', '')[:500]}"
    )


@pytest.mark.integration
@INTEGRATION_GATE
def test_json_flag_emits_search_scores() -> None:
    """--json output includes search_scores with bm25/embed/rrf keys per page (SEARCH-06 + CLI-04)."""
    result = subprocess.run(
        [
            "uv",
            "run",
            "--package",
            "code-wiki-agent",
            "code-wiki-agent",
            "query",
            "What concepts are documented in the wiki?",
            "--vault",
            str(FIXTURE_VAULT),
            "--top-k",
            "3",
            "--json",
        ],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode in (0, 3), (
        f"Unexpected exit code {result.returncode}.\nstdout: {result.stdout[:1000]}\nstderr: {result.stderr[:500]}"
    )
    data = json.loads(result.stdout)
    search_scores = data.get("search_scores", {})
    assert search_scores, f"Expected non-empty search_scores, got: {search_scores!r}"
    for page_path, scores in search_scores.items():
        assert isinstance(scores, dict), f"search_scores[{page_path!r}] is not a dict: {scores!r}"
        assert set(scores.keys()) == {"bm25", "embed", "rrf"}, (
            f"search_scores[{page_path!r}] missing keys: expected bm25/embed/rrf, got {set(scores.keys())}"
        )
