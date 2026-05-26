from __future__ import annotations

"""Schema unit tests for WikiScanInput.repo_path field.

Requirements covered: DACLI-02 (precondition).
"""

import pytest


def test_wiki_scan_input_default_repo_path_is_empty() -> None:
    """WikiScanInput defaults to repo_path='' (no override — resolves from workspace_path) (DACLI-02)."""
    from graph_wiki_agent.mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.repo_path == ""


def test_wiki_scan_input_accepts_repo_path() -> None:
    """WikiScanInput accepts an explicit repo_path string (DACLI-02)."""
    from graph_wiki_agent.mcp.server import WikiScanInput

    inp = WikiScanInput(repo_path="/tmp/test-repo")
    assert inp.repo_path == "/tmp/test-repo"


def test_wiki_scan_input_preserves_existing_defaults() -> None:
    """Adding repo_path does not regress existing workspace_path / no_file_map / max_depth defaults (regression guard)."""
    from graph_wiki_agent.mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.workspace_path == ""
    assert inp.no_file_map is False
    assert inp.max_depth == 3
