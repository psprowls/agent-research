from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch


def test_run_archive_all_runs_both_and_propagates_dry_run() -> None:
    from graph_wiki_core.commands.archive_all import run_archive_all
    from graph_wiki_core.commands.wiki_archive import WikiArchiveResult
    from graph_wiki_core.commands.work import WorkArchiveResult

    wiki_res = WikiArchiveResult(dry_run=True, moved=[{"slug": "adrs/x", "src": "a", "dst": "b"}], skipped=[])
    work_res = WorkArchiveResult(dry_run=True, moved=[], skipped=[], repointed=[])

    with (
        patch(
            "graph_wiki_core.commands.archive_all.run_wiki_archive",
            new=AsyncMock(return_value=wiki_res),
        ) as mock_wiki,
        patch(
            "graph_wiki_core.commands.archive_all.run_work_archive",
            new=AsyncMock(return_value=work_res),
        ) as mock_work,
    ):
        result = asyncio.run(run_archive_all(dry_run=True))

    assert result.dry_run is True
    assert result.wiki is wiki_res
    assert result.work is work_res
    assert result.errors == []
    assert mock_wiki.call_args.kwargs["dry_run"] is True
    assert mock_work.call_args.kwargs["dry_run"] is True


def test_run_archive_all_continues_when_wiki_raises() -> None:
    from graph_wiki_core.commands.archive_all import run_archive_all
    from graph_wiki_core.commands.work import WorkArchiveResult

    work_res = WorkArchiveResult(dry_run=False, moved=[], skipped=[], repointed=[])

    with (
        patch(
            "graph_wiki_core.commands.archive_all.run_wiki_archive",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "graph_wiki_core.commands.archive_all.run_work_archive",
            new=AsyncMock(return_value=work_res),
        ),
    ):
        result = asyncio.run(run_archive_all())

    assert result.wiki is None
    assert result.work is work_res
    assert result.errors == [{"command": "wiki", "error": "boom"}]
