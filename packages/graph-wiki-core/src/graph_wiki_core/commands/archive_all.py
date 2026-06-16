"""run_archive_all — sweep-archive curated pages and work items in one call.

Thin orchestrator over run_wiki_archive (curated adrs/concepts/proposals pages)
and run_work_archive (work items). Continue-on-error: a failure in one pass is
captured and does not block the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from graph_wiki_core.commands.wiki_archive import WikiArchiveResult, run_wiki_archive
from graph_wiki_core.commands.work import WorkArchiveResult, run_work_archive


@dataclass
class ArchiveAllResult:
    """Aggregate of a wiki + work archive sweep."""

    dry_run: bool
    wiki: WikiArchiveResult | None = None
    work: WorkArchiveResult | None = None
    errors: list[dict] = field(default_factory=list)


async def run_archive_all(
    workspace_path: Path | None = None,
    dry_run: bool = False,
) -> ArchiveAllResult:
    """Sweep-archive curated pages then work items; capture per-pass failures."""
    errors: list[dict] = []
    wiki: WikiArchiveResult | None = None
    work: WorkArchiveResult | None = None

    try:
        wiki = await run_wiki_archive(workspace_path=workspace_path, dry_run=dry_run)
    except (RuntimeError, FileNotFoundError) as e:
        errors.append({"command": "wiki", "error": str(e)})

    try:
        work = await run_work_archive(workspace_path=workspace_path, dry_run=dry_run)
    except (RuntimeError, FileNotFoundError) as e:
        errors.append({"command": "work", "error": str(e)})

    return ArchiveAllResult(dry_run=dry_run, wiki=wiki, work=work, errors=errors)
