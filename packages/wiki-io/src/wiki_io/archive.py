"""Plan archiving of terminal curated wiki pages (adrs / concepts / proposals).

Pure planning, no filesystem mutation — parallel to the work-io archive planner. The
two trivial dataclasses are duplicated rather than imported from ``work-io`` to
avoid a ``wiki-io -> work-io`` dependency (spec decision #6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

# Per-directory terminal status sets. A page is archivable iff its `status`
# frontmatter is in its own directory's set.
TERMINAL_STATUSES_BY_DIR: dict[str, frozenset[str]] = {
    "adrs": frozenset({"superseded", "deprecated"}),
    "concepts": frozenset({"superseded", "deprecated"}),
    # `created` = the curated page was already written from this proposal, so the
    # note has served its purpose and is as archivable as approved/rejected.
    "proposals": frozenset({"approved", "rejected", "created"}),
}


@dataclass
class ArchiveAction:
    slug: str  # path-qualified "<dir>/<stem>"
    src: Path
    dst: Path


@dataclass
class ArchivePlan:
    actions: list[ArchiveAction] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


def plan_wiki_archive(
    wiki: Path,
    dirs: list[str] | None = None,
    slugs: list[str] | None = None,
) -> ArchivePlan:
    """Plan archiving of terminal curated wiki pages.

    Sweep mode (``slugs=None``): scan each directory in ``dirs`` (default: all
    three archivable dirs), top level only. Targeted mode (``slugs`` given):
    each slug is a path-qualified ``<dir>/<stem>`` token.

    Non-terminal, missing, unknown-dir, and parse-error candidates are recorded
    in ``skipped`` (never fatal). ``dst`` is always ``<dir>/_archive/<name>``.
    """
    actions: list[ArchiveAction] = []
    skipped: list[dict] = []

    # Build the candidate list as (dir, path, slug_token) triples, recording
    # resolution failures (unknown dir / missing file) into skipped up front.
    candidates: list[tuple[str, Path, str]] = []

    if slugs is not None:
        for token in slugs:
            parts = token.split("/", 1)
            if len(parts) != 2 or parts[0] not in TERMINAL_STATUSES_BY_DIR:
                skipped.append({"slug": token, "reason": "unqualified or unknown dir (expected <dir>/<slug>)"})
                continue
            d, stem = parts
            md = wiki / d / f"{stem}.md"
            if not md.exists():
                skipped.append({"slug": token, "reason": f"not found in {d}/"})
                continue
            candidates.append((d, md, token))
    else:
        scan_dirs = dirs if dirs is not None else list(TERMINAL_STATUSES_BY_DIR)
        for d in scan_dirs:
            if d not in TERMINAL_STATUSES_BY_DIR:
                skipped.append({"slug": d, "reason": f"{d!r} is not an archivable directory"})
                continue
            dir_path = wiki / d
            if not dir_path.is_dir():
                continue
            for md in sorted(dir_path.glob("*.md")):  # top level only — never _archive/
                if md.name == "index.md":
                    continue
                candidates.append((d, md, f"{d}/{md.stem}"))

    for d, md, token in candidates:
        terminal = TERMINAL_STATUSES_BY_DIR[d]
        try:
            post = frontmatter.load(str(md))
        except Exception as e:  # noqa: BLE001 — a malformed page must not abort the plan
            skipped.append({"slug": token, "reason": f"parse error: {e}"})
            continue
        status = str(post.metadata.get("status", ""))
        if status not in terminal:
            skipped.append({"slug": token, "reason": f"status={status!r} is not terminal"})
            continue
        actions.append(ArchiveAction(slug=token, src=md, dst=wiki / d / "_archive" / md.name))

    return ArchivePlan(actions=actions, skipped=skipped)
