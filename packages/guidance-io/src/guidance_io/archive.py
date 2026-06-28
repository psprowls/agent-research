"""Plan archiving of guidance pages: wiki/guidance/<topic>/<slug>.md.

Pure planning, no filesystem mutation — parallel to ``wiki_io.archive`` and
``work_io.archive``. The two trivial dataclasses are duplicated rather than
imported from ``wiki-io`` to keep ``guidance-io`` dependency-free (the
established "spec decision #6" pattern in ``wiki_io/archive.py``).

Targeted-only: ``slugs`` is required. Guidance has no lifecycle ``status``
field, so there is nothing for a sweep to key on — archiving is always by
explicit ``<topic>/<slug>`` token. Unqualified, missing, and malformed tokens
are recorded in ``skipped`` (never fatal); other valid slugs still archive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


@dataclass
class ArchiveAction:
    slug: str  # path-qualified "<topic>/<slug>"
    src: Path
    dst: Path


@dataclass
class ArchivePlan:
    actions: list[ArchiveAction] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def plan_guidance_archive(wiki: Path, slugs: list[str]) -> ArchivePlan:
    """Plan archiving of the named guidance pages.

    Each ``slug`` is a path-qualified ``<topic>/<slug>`` token (the shape recall
    and the indexes already use, e.g. ``python/old-pattern``). Resolves
    ``wiki/guidance/<topic>/<slug>.md``; ``dst`` is always
    ``wiki/guidance/<topic>/_archive/<slug>.md``. Unqualified tokens, missing
    files, and unreadable/malformed pages go to ``skipped`` and never abort.
    """
    actions: list[ArchiveAction] = []
    skipped: list[dict] = []

    for token in slugs:
        parts = token.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            skipped.append({"slug": token, "reason": "unqualified (expected <topic>/<slug>)"})
            continue
        topic, stem = parts
        md = wiki / "guidance" / topic / f"{stem}.md"
        if not md.exists():
            skipped.append({"slug": token, "reason": f"not found in guidance/{topic}/"})
            continue
        try:
            frontmatter.load(str(md))
        except Exception as e:  # noqa: BLE001 — a malformed page must not abort the plan
            skipped.append({"slug": token, "reason": f"parse error: {e}"})
            continue
        actions.append(ArchiveAction(slug=token, src=md, dst=wiki / "guidance" / topic / "_archive" / f"{stem}.md"))

    return ArchivePlan(actions=actions, skipped=skipped)
