from __future__ import annotations

"""Stub tests for the wiki_query MCP tool schema (Plan 04 deliverable).

These stubs exist so the test runner discovers Phase 3 MCP schema tests from
Wave 0 onwards. All tests are marked xfail until Plan 04 registers the
wiki_query tool on the FastMCP server.

Requirements covered: MCP-02, MCP-04, MCP-06.
"""

import pytest


@pytest.mark.xfail(reason="Implemented in Plan 04", strict=False)
def test_wiki_query_tool_registered() -> None:
    """wiki_query tool is present in the MCP server's tool list (MCP-02)."""
    assert False, "stub — Plan 04"


@pytest.mark.xfail(reason="Implemented in Plan 04", strict=False)
def test_invalid_input_returns_structured_error() -> None:
    """wiki_query with invalid input returns a structured MCP error, not an exception (MCP-04)."""
    assert False, "stub — Plan 04"


@pytest.mark.xfail(reason="Implemented in Plan 04", strict=False)
def test_progress_calls_made() -> None:
    """wiki_query emits MCP progress notifications during long-running search (MCP-06)."""
    assert False, "stub — Plan 04"
