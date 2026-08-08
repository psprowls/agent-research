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


def children_map(items: list[dict]) -> dict[str, list[str]]:
    """Map parent slug -> child slugs, sorted by (opened, slug).

    Terminal and archived children are included — the parent/child relationship
    is permanent. Parents with no children are omitted (the `children` key is
    omitted-when-empty on pages). Items need 'slug' and 'parent'; 'opened' is
    optional and defaults to "".
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    for it in items:
        parent = it.get("parent")
        if parent:
            grouped.setdefault(str(parent), []).append((str(it.get("opened") or ""), it["slug"]))
    return {parent: [slug for _opened, slug in sorted(pairs)] for parent, pairs in grouped.items()}


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


WALK_DEPTH_CAP = 32
PICK_ORDER = {"in-progress": 0, "accepted": 1, "open": 2}


@dataclass(frozen=True)
class DescendResult:
    """Resolution of `--descend`: the chain walked and where it landed."""

    path: tuple[str, ...]  # requested slug .. leaf (or blocked node), inclusive
    leaf: str | None  # actionable leaf slug; None when blocked
    blocked_at: str | None = None
    reason: str | None = None


def child_gated_node(item: dict, children: list[dict]) -> bool:
    """Descend-into rule: epic at execute with open children, or feature at
    execute/finish with open children. Anything else — including an epic still
    at plan/design — is its own actionable leaf (an epic at plan is dispatched
    to planning-epics; the "waiting on children" gate only applies once it has
    reached execute, mirroring work_io.workflow._epic_execute_gate)."""
    if not any(c.get("status") not in TERMINAL_STATUSES for c in children):
        return False
    if item.get("kind") == "epic":
        return item.get("phase") == "execute"
    return item.get("kind") == "feature" and item.get("phase") in ("execute", "finish")


def descend(items: list[dict], slug: str) -> DescendResult:
    """Resolve the next actionable leaf below `slug` (recursive, cycle-safe).

    Items are extended hierarchy views: slug, status, parent, kind, phase,
    depends_on, opened. Candidates at each level are children in
    {in-progress, accepted, open} whose depends_on are all terminal; pick
    in-progress > accepted > oldest open by (opened, slug). Non-dispatchable
    non-terminal statuses (mitigated) still hold the gate open but are never
    descend targets.
    """
    by_slug = {it["slug"]: it for it in items}
    node = by_slug.get(slug)
    if node is None:
        return DescendResult(path=(slug,), leaf=None, blocked_at=slug, reason=f"unknown slug {slug!r}")
    path = [slug]
    visited = {slug}
    while True:
        children = [it for it in items if it.get("parent") == node["slug"]]
        if not child_gated_node(node, children):
            return DescendResult(path=tuple(path), leaf=node["slug"])
        candidates = [
            c
            for c in children
            if c.get("status") in PICK_ORDER
            and not dep_states(items, tuple(str(d) for d in (c.get("depends_on") or ())))
        ]
        if not candidates:
            return DescendResult(
                path=tuple(path),
                leaf=None,
                blocked_at=node["slug"],
                reason="no dep-ready child: open children are blocked on dependencies or not dispatchable",
            )
        candidates.sort(key=lambda c: (PICK_ORDER[str(c.get("status"))], str(c.get("opened") or ""), c["slug"]))
        nxt = candidates[0]
        if nxt["slug"] in visited:
            return DescendResult(
                path=tuple(path),
                leaf=None,
                blocked_at=node["slug"],
                reason="parent cycle detected: " + " -> ".join([*path, nxt["slug"]]),
            )
        if len(path) >= WALK_DEPTH_CAP:
            return DescendResult(
                path=tuple(path),
                leaf=None,
                blocked_at=node["slug"],
                reason=f"descend depth cap ({WALK_DEPTH_CAP}) reached: " + " -> ".join([*path, nxt["slug"]]),
            )
        path.append(nxt["slug"])
        visited.add(nxt["slug"])
        node = nxt
