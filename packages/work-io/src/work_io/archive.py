"""Plan archiving of terminal work items."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

TERMINAL_STATUSES = frozenset({"resolved", "wontfix", "superseded"})


@dataclass
class ArchiveAction:
    slug: str
    src: Path
    dst: Path


@dataclass
class ArchivePlan:
    actions: list[ArchiveAction] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def plan_archive(
    work_dir: Path,
    slugs: list[str] | None = None,
) -> ArchivePlan:
    """Plan archiving of terminal work items.

    Sweep mode (slugs=None): all terminal items.
    Targeted mode (slugs provided): named items; non-terminal skipped.
    """
    from work_io.frontmatter import parse as fm_parse

    archived_dir = work_dir / "_archived"
    actions: list[ArchiveAction] = []
    skipped: list[dict] = []

    candidates = list(work_dir.glob("*.md"))

    if slugs is not None:
        slug_set = set(slugs)
        found_stems = {f.stem: f for f in candidates}
        candidates = [found_stems[s] for s in slug_set if s in found_stems]
        for s in slug_set:
            if s not in found_stems:
                skipped.append({"slug": s, "reason": "not found in work/"})

    for md in candidates:
        slug = md.stem
        try:
            fm, _ = fm_parse(md.read_text(encoding="utf-8"))
        except Exception as e:
            skipped.append({"slug": slug, "reason": f"parse error: {e}"})
            continue

        status = str(fm.get("status", ""))
        if status not in TERMINAL_STATUSES:
            skipped.append({"slug": slug, "reason": f"status={status!r} is not terminal"})
            continue

        actions.append(ArchiveAction(slug=slug, src=md, dst=archived_dir / md.name))

    return ArchivePlan(actions=actions, skipped=skipped)
