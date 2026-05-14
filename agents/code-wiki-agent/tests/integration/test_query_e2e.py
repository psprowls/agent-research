from __future__ import annotations

"""Stub integration tests for the end-to-end query workflow (Plan 04 deliverable).

These stubs exist so the test runner discovers Phase 3 integration tests from
Wave 0 onwards. All tests are marked xfail AND @pytest.mark.integration so
they require CODE_WIKI_RUN_INTEGRATION=1 to run (never in CI by default).

Requirements covered: CMD-04 SC-5, SEARCH-06, CLI-04.

Module-level FIXTURE_VAULT constant is exposed here for later plans to reuse
(see RESEARCH Pitfall 6 — cross-package path must be precomputed at import time
so test files can use it as a default argument, class attribute, or parametrize
value without re-computing the path on every call).
"""

import os
from pathlib import Path

import pytest

# Cross-package fixture vault path (RESEARCH Pitfall 6).
# Precomputed at import time so downstream plans can reference FIXTURE_VAULT
# as a module-level constant without re-deriving the path.
FIXTURE_VAULT: Path = (
    Path(__file__).parent.parent.parent.parent.parent
    / "cores"
    / "vault-io"
    / "tests"
    / "fixtures"
    / "round-trip-vault"
)

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


@pytest.mark.integration
@INTEGRATION_GATE
@pytest.mark.xfail(reason="Implemented in Plan 04", strict=False)
def test_fixture_vault_has_citations() -> None:
    """End-to-end query against round-trip-vault returns wikilink citations (CMD-04 SC-5)."""
    assert False, "stub — Plan 04"


@pytest.mark.integration
@INTEGRATION_GATE
@pytest.mark.xfail(reason="Implemented in Plan 04", strict=False)
def test_json_flag_emits_search_scores() -> None:
    """--json output includes search_scores with bm25/embed/rrf keys (SEARCH-06 + CLI-04)."""
    assert False, "stub — Plan 04"
