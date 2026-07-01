"""Pure hierarchy helpers for epic/child work items.

Shared by the command layer (which feeds WorkItemState into the router) and the
sidecar build. Operates on already-normalized item dicts — each item is a dict
with at least 'slug', 'status', and 'parent' keys — so it stays free of any
frontmatter-parsing or graph-wiki-core dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from work_io.lifecycle_lint import TERMINAL_STATUSES

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


@dataclass(frozen=True)
class ChildRollup:
    """A snapshot of an epic's children for the execute/finish gate and status."""

    total: int
    terminal: int
    open_slugs: tuple[str, ...]  # children not yet terminal (for messaging)


def child_rollup(items: list[dict], epic_slug: str) -> ChildRollup:
    """Roll up the children of `epic_slug` (items whose parent == epic_slug)."""
    children = [it for it in items if it.get("parent") == epic_slug]
    terminal = sum(1 for it in children if it.get("status") in TERMINAL_STATUSES)
    open_slugs = tuple(sorted(it["slug"] for it in children if it.get("status") not in TERMINAL_STATUSES))
    return ChildRollup(total=len(children), terminal=terminal, open_slugs=open_slugs)


def dep_states(items: list[dict], depends_on: tuple[str, ...]) -> tuple[str, ...]:
    """Return the subset of `depends_on` slugs that are not yet terminal.

    A dep slug with no matching item is treated as unmet (fail-safe: blocks
    rather than silently running). Order follows `depends_on`.
    """
    by_slug = {it["slug"]: it for it in items}
    return tuple(d for d in depends_on if by_slug.get(d, {}).get("status") not in TERMINAL_STATUSES)


def unresolved_depends_on(items: list[dict], depends_on: list[str]) -> dict[str, str | None]:
    """Values with no matching slug, mapped to a same-title hint or None."""
    known = {it["slug"] for it in items}
    unresolved: dict[str, str | None] = {}
    for value in depends_on:
        if value in known:
            continue
        title_matches = [s for s in known if _DATE_PREFIX_RE.sub("", s) == value]
        unresolved[value] = title_matches[0] if len(title_matches) == 1 else None
    return unresolved
