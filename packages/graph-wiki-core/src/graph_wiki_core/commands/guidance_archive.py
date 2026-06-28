"""Guidance-page archive command — orchestration over guidance_io.archive.

Resolves the wiki from the workspace, plans guidance-page moves via the pure
``guidance_io.archive.plan_guidance_archive`` primitive, executes them as
``git mv`` (falling back to ``os.rename``), then regenerates the guidance
indexes so the archived page's wikilink is dropped.

Targeted-only (no sweep): guidance has no lifecycle ``status`` to sweep on.

Emptied-topic cleanup: ``update_guidance_indexes`` only rewrites ``index.md``
for topics that still have content pages, so a topic whose last content page was
just archived would keep a STALE ``index.md`` linking the archived page. This
command detects topics that dropped to zero content pages and removes their
orphaned ``index.md``.

Lives in core (not guidance-io) because ``update_index`` is a wiki-io concern —
the same boundary reasoning as ``run_work_archive`` / ``run_wiki_archive``.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from guidance_io import archive as _archive
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.update_index import update_index


@dataclass
class GuidanceArchiveResult:
    """Result of run_guidance_archive()."""

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


def _remove(path: Path) -> None:
    """Remove a file, preferring `git rm`, falling back to os.remove."""
    result = subprocess.run(
        ["git", "rm", "-f", str(path)],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        os.remove(path)


def _topic_content_pages(wiki: Path, topic: str) -> list[Path]:
    """Top-level content pages in a topic dir (excludes generated index.md)."""
    topic_dir = wiki / "guidance" / topic
    if not topic_dir.is_dir():
        return []
    return [p for p in topic_dir.glob("*.md") if p.name != "index.md"]


def run_guidance_archive(
    workspace_path: Path | None = None,
    slugs: list[str] | None = None,
    dry_run: bool = False,
) -> GuidanceArchiveResult:
    """Archive the named guidance pages into guidance/<topic>/_archive/.

    `slugs` are path-qualified `<topic>/<slug>` tokens (targeted-only). Executes
    the moves and regenerates the guidance indexes unless `dry_run`.
    """
    wiki, _repo = resolve_wiki_and_repo(workspace_path)

    plan = _archive.plan_guidance_archive(wiki, slugs or [])
    moved = [{"slug": a.slug, "src": str(a.src), "dst": str(a.dst)} for a in plan.actions]

    if not dry_run and plan.actions:
        affected_topics = {a.slug.split("/", 1)[0] for a in plan.actions}
        for action in plan.actions:
            _move(action)
        # Regenerate root + per-topic indexes (drops archived pages' wikilinks).
        update_index(wiki)
        # Emptied-topic cleanup: a topic with no remaining content pages keeps a
        # stale index.md that update_guidance_indexes did not rewrite. Remove it.
        for topic in affected_topics:
            if not _topic_content_pages(wiki, topic):
                stale = wiki / "guidance" / topic / "index.md"
                if stale.exists():
                    _remove(stale)

    return GuidanceArchiveResult(dry_run=dry_run, moved=moved, skipped=plan.skipped)
