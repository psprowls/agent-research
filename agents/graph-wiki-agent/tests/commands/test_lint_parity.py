from __future__ import annotations

"""Parity tests for the lint command (Plan 05-06).

Uses edge-case-vault fixture; mocks SubagentPool.run_all to avoid Bedrock calls.
Verifies finding shape invariants (NOT exact counts — counts may drift with fixture).

Requirements: CMD-05 (parity against lattice-wiki lint behavior)
Success criterion 3: broken-link placeholder filter verified at parity layer.
"""

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

EDGE_CASE_VAULT = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages"
    / "vault-io"
    / "tests"
    / "fixtures"
    / "edge-case-vault"
)


@pytest.fixture
def no_semantic_pool():
    """Context manager that patches SubagentPool to return empty semantic findings."""
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_agent.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        yield mock_pool


# ---------------------------------------------------------------------------
# Parity test 1: LintResult JSON-serializes without error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lint_result_json_serializable(no_semantic_pool) -> None:
    """LintResult from edge-case-vault serializes via dataclasses.asdict + json.dumps."""
    from graph_wiki_agent.commands.lint import run_lint

    result = await run_lint(workspace_path=EDGE_CASE_VAULT)

    d = dataclasses.asdict(result)
    # Should not raise
    serialized = json.dumps(d, default=list)
    assert serialized  # non-empty
    parsed = json.loads(serialized)
    assert "wiki" in parsed
    assert "total_pages" in parsed
    assert "broken_links" in parsed
    assert "missing_frontmatter" in parsed
    assert "semantic_findings" in parsed


# ---------------------------------------------------------------------------
# Parity test 2: broken_links contains at least one entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lint_edge_case_vault_has_broken_links(no_semantic_pool) -> None:
    """edge-case-vault has known broken links — result.broken_links is non-empty."""
    from graph_wiki_agent.commands.lint import run_lint

    result = await run_lint(workspace_path=EDGE_CASE_VAULT)

    assert isinstance(result.broken_links, list)
    # edge-case-vault/concepts/broken-wikilinks.md has 3 broken links
    assert len(result.broken_links) >= 1, (
        f"Expected at least 1 broken link in edge-case-vault, got: {result.broken_links}"
    )


# ---------------------------------------------------------------------------
# Parity test 3: missing_frontmatter contains at least one entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lint_edge_case_vault_has_missing_frontmatter(no_semantic_pool) -> None:
    """edge-case-vault has pages with incomplete frontmatter — result.missing_frontmatter non-empty."""
    from graph_wiki_agent.commands.lint import run_lint

    result = await run_lint(workspace_path=EDGE_CASE_VAULT)

    assert isinstance(result.missing_frontmatter, list)
    # edge-case-vault/concepts/missing-title.md lacks the required 'title' field
    # edge-case-vault/concepts/truncated-frontmatter.md has no closing ---
    assert len(result.missing_frontmatter) >= 1, (
        f"Expected at least 1 page with missing frontmatter, got: {result.missing_frontmatter}"
    )


# ---------------------------------------------------------------------------
# Parity test 4 (phase success criterion 3): placeholder filter at parity layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lint_no_placeholder_targets_in_broken_links(no_semantic_pool) -> None:
    """No entries in broken_links match placeholder patterns ([[wiki/...]] or [[work/<slug>]]).

    This is phase success criterion 3 verified at the parity integration layer.
    """
    from graph_wiki_agent.commands.lint import run_lint

    result = await run_lint(workspace_path=EDGE_CASE_VAULT)

    for src, target in result.broken_links:
        assert "..." not in target, (
            f"Placeholder target with '...' in broken_links: ({src}, {target})"
        )
        assert "<" not in target, (
            f"Placeholder target with '<' in broken_links: ({src}, {target})"
        )
        assert ">" not in target, (
            f"Placeholder target with '>' in broken_links: ({src}, {target})"
        )
