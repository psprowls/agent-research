from __future__ import annotations

"""Stub tests for the QueryResult dataclass and output formatting (Plan 03 deliverable).

These stubs exist so the test runner discovers Phase 3 result-format tests from
Wave 0 onwards. All tests are marked xfail until Plan 03 implements QueryResult
and the CLI/JSON output layer.

Requirements covered: SEARCH-06, CMD-07.
"""

import pytest


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_query_result_is_dataclass() -> None:
    """QueryResult is a Python dataclass with the required fields."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_query_result_asdict_has_required_keys() -> None:
    """dataclasses.asdict(QueryResult(...)) contains answer, citations, pages_drilled, search_scores."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_search_scores_shape_per_page() -> None:
    """search_scores dict maps page path to {bm25, embed, rrf} float keys (SEARCH-06)."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_json_output_valid_schema() -> None:
    """JSON output from --json flag validates against the expected schema (CMD-07)."""
    assert False, "stub — Plan 03"
