"""Gated integration test for vault_io.update_tokens.count_tokens.

Lives in tests/integration/ and is skipped unless GRAPH_WIKI_RUN_INTEGRATION=1.
Per docs/testing.md §3.

Requirements: TOK-02 (live).
"""

from __future__ import annotations

import os

import pytest

# Canonical GRAPH_WIKI_RUN_INTEGRATION gate — matches docs/testing.md verbatim
# so the docs/testing.md grep gate sees this file as canonical.
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


@pytest.mark.integration
@INTEGRATION_GATE
def test_count_tokens_real_bedrock() -> None:
    """Calls real Bedrock when GRAPH_WIKI_RUN_INTEGRATION=1; otherwise skips."""
    from vault_io.update_tokens import count_tokens

    n = count_tokens("hello world")
    assert isinstance(n, int) and n > 0
