from __future__ import annotations

"""Unit tests for commands/lint.py — LintResult shape, run_lint orchestration, and
mechanical pass behavior (placeholder filter, stale threshold, module calls).

Requirements: CMD-05
"""

import dataclasses
import hashlib
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

EDGE_CASE_VAULT = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages"
    / "wiki-io"
    / "tests"
    / "fixtures"
    / "edge-case-vault"
)


# ---------------------------------------------------------------------------
# Test 1: LintResult dataclass shape
# ---------------------------------------------------------------------------


def test_lint_result_dataclass_shape() -> None:
    """LintResult has all 18 required fields."""
    from graph_wiki_agent.commands.lint import LintResult

    required_fields = {
        "wiki",
        "total_pages",
        "orphans",
        "broken_links",
        "stale",
        "missing_frontmatter",
        "duplicate_titles",
        "log_gap",
        "code_drift",
        "container_drift",
        "source_sync_drift",
        "file_map_drift",
        "package_sync_drift",
        "domain_placement",
        "workflow_hints",
        "semantic_findings",
        "errors",
        "dependency_layer",
    }
    field_names = {f.name for f in dataclasses.fields(LintResult)}
    for name in required_fields:
        assert name in field_names, f"LintResult missing field: {name}"


# ---------------------------------------------------------------------------
# Test 2: run_lint finds orphans in edge-case-vault fixture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_mechanical_finds_orphans_in_fixture() -> None:
    """run_lint against edge-case-vault: result.orphans is a list."""
    from graph_wiki_agent.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_agent.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(
            return_value=FanOutResult(successes=[], errors=[])
        )
        result = await run_lint(workspace_path=EDGE_CASE_VAULT)

    assert isinstance(result.orphans, list)
    assert isinstance(result.total_pages, int)
    assert result.total_pages >= 0


# ---------------------------------------------------------------------------
# Test 3: broken_links skips placeholder targets ([[wiki/...]], [[work/<slug>]])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_broken_links_skip_placeholder_targets(tmp_path: Path) -> None:
    """Placeholder wikilinks [[wiki/...]] and [[work/...]] do not appear in broken_links."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")
    concepts_dir = wiki / "concepts"
    concepts_dir.mkdir()
    # Use the exact placeholder formats: [[wiki/packages/...]] (contains ...) and
    # [[work/<slug>]] (contains < and >). Per _is_placeholder_target(), these are
    # filtered because they contain "...", "<", or ">" tokens.
    (concepts_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\ncategory: concept\nsummary: test\nupdated: 2026-05-14\n---\n\n"
        "[[wiki/packages/...]] placeholder should be ignored (contains ...)\n"
        "[[work/<slug>]] placeholder should be ignored (contains <)\n"
        "[[real-broken]] this is really broken\n",
        encoding="utf-8",
    )

    from graph_wiki_agent.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_agent.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(
            return_value=FanOutResult(successes=[], errors=[])
        )
        result = await run_lint(workspace_path=wiki)

    broken_targets = [t for _, t in result.broken_links]
    # Placeholder targets (... or < or >) must NOT appear in broken_links
    for t in broken_targets:
        assert "..." not in t, f"Placeholder target with '...' leaked into broken_links: {t}"
        assert "<" not in t, f"Placeholder target with '<' leaked into broken_links: {t}"
    # The real broken link should appear
    assert any("real-broken" in t for t in broken_targets), (
        f"Expected 'real-broken' in broken_links, got: {result.broken_links}"
    )


# ---------------------------------------------------------------------------
# Test 4: stale_days defaults to 90
# ---------------------------------------------------------------------------


def test_run_lint_stale_days_threshold_default_90() -> None:
    """run_lint has stale_days: int = 90 default."""
    from graph_wiki_agent.commands.lint import run_lint

    sig = inspect.signature(run_lint)
    assert "stale_days" in sig.parameters
    assert sig.parameters["stale_days"].default == 90


# ---------------------------------------------------------------------------
# Test 5: log_gap_days defaults to 14
# ---------------------------------------------------------------------------


def test_run_lint_log_gap_days_threshold_default_14() -> None:
    """run_lint has log_gap_days: int = 14 default."""
    from graph_wiki_agent.commands.lint import run_lint

    sig = inspect.signature(run_lint)
    assert "log_gap_days" in sig.parameters
    assert sig.parameters["log_gap_days"].default == 14


# ---------------------------------------------------------------------------
# Test 6: all 7 module check() functions are called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_calls_all_7_module_check_functions(tmp_path: Path) -> None:
    """run_lint calls all 7 lint module check() functions.

    We mock resolve_wiki_and_repo to return a non-None repo path so that all 7
    module checks are exercised (the 4 repo-dependent checks are guarded by
    repo is not None in _module_pass).
    """
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    from graph_wiki_agent.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    mock_container = MagicMock(return_value=[])
    mock_dependency = MagicMock(return_value=[])
    mock_domain = MagicMock(return_value=[])
    mock_file_map = MagicMock(return_value=[])
    mock_package_sync = MagicMock(return_value=[])
    mock_source_sync = MagicMock(return_value=[])
    mock_workflow = MagicMock(return_value=[])

    with (
        patch("graph_wiki_agent.commands.lint.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_agent.commands.lint.check_container_drift", mock_container),
        patch("graph_wiki_agent.commands.lint.check_dependency_layer", mock_dependency),
        patch("graph_wiki_agent.commands.lint.check_domain_placement", mock_domain),
        patch("graph_wiki_agent.commands.lint.check_file_map_drift", mock_file_map),
        patch("graph_wiki_agent.commands.lint.check_package_sync_drift", mock_package_sync),
        patch("graph_wiki_agent.commands.lint.check_source_sync_drift", mock_source_sync),
        patch("graph_wiki_agent.commands.lint.check_workflow_hints", mock_workflow),
        patch("graph_wiki_agent.commands.lint.SubagentPool") as MockPool,
    ):
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        await run_lint(workspace_path=wiki)

    assert mock_container.called, "check_container_drift not called"
    assert mock_dependency.called, "check_dependency_layer not called"
    assert mock_domain.called, "check_domain_placement not called"
    assert mock_file_map.called, "check_file_map_drift not called"
    assert mock_package_sync.called, "check_package_sync_drift not called"
    assert mock_source_sync.called, "check_source_sync_drift not called"
    assert mock_workflow.called, "check_workflow_hints not called"


# ---------------------------------------------------------------------------
# Test 7: semantic fan-out runs 3 groups with role="linter"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_semantic_fanout_3_groups(tmp_path: Path) -> None:
    """SubagentPool.run_all is called once with 3 items and role='linter'."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    from graph_wiki_agent.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    captured_calls: list[dict] = []

    with patch("graph_wiki_agent.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool

        async def capture_run_all(items, task, role, *, model_id, max_concurrency, **kwargs):
            captured_calls.append({"items": list(items), "role": role})
            return FanOutResult(
                successes=[(item, []) for item in items],
                errors=[],
            )

        mock_pool.run_all = capture_run_all
        await run_lint(workspace_path=wiki)

    assert len(captured_calls) == 1, f"Expected 1 run_all call, got {len(captured_calls)}"
    assert captured_calls[0]["role"] == "linter"
    assert len(captured_calls[0]["items"]) == 3, (
        f"Expected 3 semantic groups, got {len(captured_calls[0]['items'])}"
    )


# ---------------------------------------------------------------------------
# Test 8: semantic errors surface in result.errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_semantic_errors_surface_in_result_errors(tmp_path: Path) -> None:
    """If semantic fan-out has PerItemError entries, they appear in result.errors."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    from graph_wiki_agent.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult, PerItemError

    stale_group = ("stale_claims", "sys", [])

    with patch("graph_wiki_agent.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(
            return_value=FanOutResult(
                successes=[],
                errors=[PerItemError(item=stale_group, exception=RuntimeError("Bedrock error"))],
            )
        )
        result = await run_lint(workspace_path=wiki)

    assert len(result.errors) >= 1
    # Error message should contain something about the failure
    assert any("Bedrock error" in e or "stale_claims" in e for e in result.errors), (
        f"Expected error message containing 'Bedrock error' or 'stale_claims', got: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Test 9: no write-back to vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_no_write_back_to_vault(tmp_path: Path) -> None:
    """Vault directory contents are unchanged after run_lint (D-10)."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")
    concepts_dir = wiki / "concepts"
    concepts_dir.mkdir()
    (concepts_dir / "my-page.md").write_text(
        "---\ntitle: My Page\ncategory: concept\nsummary: test\n---\n\nContent.\n",
        encoding="utf-8",
    )

    def _dir_hash(directory: Path) -> str:
        h = hashlib.sha256()
        for p in sorted(directory.rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(directory)).encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    before_hash = _dir_hash(wiki)

    from graph_wiki_agent.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_agent.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        await run_lint(workspace_path=wiki)

    after_hash = _dir_hash(wiki)
    assert before_hash == after_hash, "Vault was modified by run_lint (D-10 violation)"
