"""Wiki-page archive command — orchestration over wiki_io.archive.

Resolves the wiki from the workspace, plans terminal curated-page moves via the
pure ``wiki_io.archive.plan_wiki_archive`` primitive, and executes them as
``git mv`` (falling back to ``os.rename``). Move-only, never mutates
frontmatter, never deletes — the curated-page parallel to ``run_work_archive``.

Unlike work archiving there is NO sidecar regeneration (wiki pages have no
sidecar) and NO index regeneration (``index.md`` already excludes every
``<dir>/_archive/`` and refreshes on the next scan/ingest).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from wiki_io import archive as _archive
from wiki_io._workspace import resolve_wiki_and_repo


@dataclass
class WikiArchiveResult:
    """Result of run_wiki_archive()."""

    dry_run: bool
    moved: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def _move(action: _archive.ArchiveAction) -> None:
    """Move a page into _archive/, preferring `git mv`, falling back to rename."""
    action.dst.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "mv", str(action.src), str(action.dst)],
        cwd=action.src.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        os.rename(action.src, action.dst)


async def run_wiki_archive(
    workspace_path: Path | None = None,
    slugs: list[str] | None = None,
    dirs: list[str] | None = None,
    dry_run: bool = False,
) -> WikiArchiveResult:
    """Archive terminal curated pages into <dir>/_archive/.

    Sweep mode (slugs=None): all terminal adrs/concepts/proposals pages (or the
    subset named by `dirs`). Targeted mode (slugs given): path-qualified
    `<dir>/<slug>` tokens. Executes the moves unless dry_run.
    """
    wiki, _repo = resolve_wiki_and_repo(workspace_path)

    plan = _archive.plan_wiki_archive(wiki, dirs=dirs, slugs=slugs)
    moved = [{"slug": a.slug, "src": str(a.src), "dst": str(a.dst)} for a in plan.actions]

    if not dry_run and plan.actions:
        for action in plan.actions:
            _move(action)

    return WikiArchiveResult(dry_run=dry_run, moved=moved, skipped=plan.skipped)
