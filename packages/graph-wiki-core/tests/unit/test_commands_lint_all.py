from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch


def test_run_lint_all_runs_both_and_propagates_params() -> None:
    from graph_wiki_core.commands.lint import LintResult
    from graph_wiki_core.commands.lint_all import run_lint_all
    from graph_wiki_core.commands.work import WorkLintResult

    wiki_res = LintResult(wiki="w", total_pages=1)
    work_res = WorkLintResult(total_items=0, findings=[])

    with (
        patch("graph_wiki_core.commands.lint_all.run_lint", new=AsyncMock(return_value=wiki_res)) as mock_lint,
        patch(
            "graph_wiki_core.commands.lint_all.run_work_lint",
            new=AsyncMock(return_value=work_res),
        ),
    ):
        result = asyncio.run(run_lint_all(stale_days=30, log_gap_days=7))

    assert result.wiki is wiki_res
    assert result.work is work_res
    assert result.errors == []
    assert mock_lint.call_args.kwargs["stale_days"] == 30
    assert mock_lint.call_args.kwargs["log_gap_days"] == 7


def test_run_lint_all_continues_when_work_raises() -> None:
    from graph_wiki_core.commands.lint import LintResult
    from graph_wiki_core.commands.lint_all import run_lint_all

    wiki_res = LintResult(wiki="w", total_pages=1)

    with (
        patch("graph_wiki_core.commands.lint_all.run_lint", new=AsyncMock(return_value=wiki_res)),
        patch(
            "graph_wiki_core.commands.lint_all.run_work_lint",
            new=AsyncMock(side_effect=RuntimeError("nope")),
        ),
    ):
        result = asyncio.run(run_lint_all())

    assert result.wiki is wiki_res
    assert result.work is None
    assert result.errors == [{"command": "work", "error": "nope"}]


def test_run_lint_all_continues_when_wiki_raises() -> None:
    from graph_wiki_core.commands.lint_all import run_lint_all
    from graph_wiki_core.commands.work import WorkLintResult

    work_res = WorkLintResult(total_items=0, findings=[])

    with (
        patch("graph_wiki_core.commands.lint_all.run_lint", new=AsyncMock(side_effect=RuntimeError("boom"))),
        patch(
            "graph_wiki_core.commands.lint_all.run_work_lint",
            new=AsyncMock(return_value=work_res),
        ),
    ):
        result = asyncio.run(run_lint_all())

    assert result.wiki is None
    assert result.work is work_res
    assert result.errors == [{"command": "wiki", "error": "boom"}]
