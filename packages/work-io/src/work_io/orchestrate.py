"""Read-only auto-drive dispatch planner. Pure logic only — no IO, no git.

Given an extended-hierarchy-view item list (work_io.hierarchy shape plus
affects/effort/worktree/branch/has_plan_doc), computes every dispatch decision
for a root work item's subtree: which leaves run now, in which worktree, mode,
model, and prompt — from durable vault state alone. plan() never mutates
anything; identical inputs produce an identical OrchestratePlan.

Mirrors work_io.workflow.route()'s "pure decision, IO-free" split — the
graph-wiki-core command layer (commands/orchestrate.py) owns config/git IO and
calls plan() with everything pre-resolved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from work_io import hierarchy as _hierarchy
from work_io import lifecycle_lint as _lint
from work_io import workflow as _workflow
from work_io.auto_drive import resolve_model

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_MODE_BY_PHASE = {"design": "attend", "plan": "autonomous", "execute": "autonomous", "finish": "relay"}


@dataclass(frozen=True)
class WorktreeAction:
    action: str  # "reuse" | "fork-child" | "create-top-level"
    path: str | None  # concrete only for "reuse"; None until Orca creates it otherwise
    branch: str
    base_branch: str | None  # set for fork-child / create-top-level
    exists: bool | None  # best-effort stat; None when path is unknown or stat failed


@dataclass(frozen=True)
class PlannedDispatch:
    key: str  # "<slug>#<phase>"
    slug: str
    phase: str
    kind: str
    effort: str | None
    skill: str
    mode: str  # "autonomous" | "attend" | "relay"
    model: str | None  # None = inherit (omit --model)
    reasoning_effort: str | None
    worktree: WorktreeAction
    merge_target: str
    prompt: str


@dataclass(frozen=True)
class PlannedAdvance:
    slug: str
    reason: str


@dataclass(frozen=True)
class BlockedItem:
    slug: str
    kind: str  # "deps" | "capacity" | "affects-overlap" | "effort-required" | "human" | "worktree-pending" | "invalid"
    reason: str


@dataclass(frozen=True)
class OrchestratePlan:
    slug: str
    terminal: bool
    max_parallel: int
    permission_mode: str
    live: tuple[str, ...]
    slots_free: int
    dispatches: tuple[PlannedDispatch, ...]
    advances: tuple[PlannedAdvance, ...]
    blocked: tuple[BlockedItem, ...]
    warnings: tuple[str, ...]


def _branch_name(slug: str, kind: str) -> str:
    """Deterministic slug->branch: strip the date prefix and, for epic
    children, the 'epic-' filing marker; the kind becomes the path segment.

    2026-08-07-epic-orca-auto-drive-pipeline (kind=epic)
      -> epic/orca-auto-drive-pipeline
    2026-08-07-epic-feature-orchestrate-dispatch-decision-engine (kind=feature)
      -> feature/orchestrate-dispatch-decision-engine
    """
    stripped = _DATE_PREFIX_RE.sub("", slug)
    if kind != "epic" and stripped.startswith("epic-"):
        stripped = stripped[len("epic-") :]
    prefix = f"{kind}-"
    if stripped.startswith(prefix):
        stripped = stripped[len(prefix) :]
    return f"{kind}/{stripped}"


def _state_for_item(items: list[dict], item: dict) -> _workflow.WorkItemState:
    """Build a WorkItemState from one extended-hierarchy-view item dict —
    the orchestrate-side equivalent of graph_wiki_core.commands.work._state_from_fm,
    operating on plain dicts instead of parsed frontmatter."""
    depends_on = tuple(item.get("depends_on") or ())
    unmet_deps = _hierarchy.dep_states(items, depends_on) if depends_on else ()
    rollup = None
    kind = str(item.get("kind", ""))
    if kind in _lint.PARENT_KINDS:
        rollup = _hierarchy.child_rollup(items, item["slug"])
        if kind == "feature" and rollup.total == 0:
            rollup = None
    return _workflow.WorkItemState(
        kind=kind,
        status=str(item.get("status", "")),
        phase=item.get("phase"),
        effort=item.get("effort"),
        has_plan_doc=bool(item.get("has_plan_doc")),
        depends_on=depends_on,
        unmet_deps=unmet_deps,
        child_rollup=rollup,
    )


def _classify_blocker(reason: str) -> str:
    if reason.startswith("blocked on dependencies"):
        return "deps"
    if reason.startswith("effort required"):
        return "effort-required"
    if "never dispatches" in reason or "human-owned" in reason:
        return "human"
    return "invalid"


def _frontier(
    items: list[dict], root: str
) -> tuple[list[tuple[dict, _workflow.RouteResult]], list[PlannedAdvance], list[BlockedItem]]:
    """Generalizes work_io.hierarchy.descend() from 'pick one leaf' to 'collect
    all': walks the parent/child tree from root (cycle-safe, depth-capped),
    recursing into every child-gated node's non-terminal children, and routing
    every non-gated node it lands on. Terminal children are skipped silently —
    a resolved child is a satisfied input, not a blocked item."""
    by_slug = {it["slug"]: it for it in items}
    root_item = by_slug.get(root)
    if root_item is None:
        return [], [], [BlockedItem(slug=root, kind="invalid", reason=f"unknown slug {root!r}")]

    children_of: dict[str, list[dict]] = {}
    for it in items:
        parent = it.get("parent")
        if parent:
            children_of.setdefault(parent, []).append(it)

    candidates: list[tuple[dict, _workflow.RouteResult]] = []
    advances: list[PlannedAdvance] = []
    blocked: list[BlockedItem] = []

    stack: list[tuple[str, int]] = [(root, 0)]
    visited = {root}
    while stack:
        slug, depth = stack.pop()
        node = by_slug.get(slug)
        if node is None:
            blocked.append(BlockedItem(slug=slug, kind="invalid", reason=f"unknown slug {slug!r}"))
            continue
        if depth >= _hierarchy.WALK_DEPTH_CAP:
            blocked.append(
                BlockedItem(
                    slug=slug, kind="invalid", reason=f"frontier walk depth cap ({_hierarchy.WALK_DEPTH_CAP}) reached"
                )
            )
            continue
        children = children_of.get(slug, [])
        if _hierarchy.child_gated_node(node, children):
            for child in children:
                if child.get("status") in _lint.TERMINAL_STATUSES:
                    continue  # satisfied input, not noise
                if child["slug"] in visited:
                    blocked.append(
                        BlockedItem(slug=slug, kind="invalid", reason=f"parent cycle detected at {child['slug']!r}")
                    )
                    continue
                visited.add(child["slug"])
                stack.append((child["slug"], depth + 1))
            continue
        state = _state_for_item(items, node)
        r = _workflow.route(state)
        if r.skill and not r.blockers:
            candidates.append((node, r))
        elif r.skill is None and r.on_complete is not None and not r.blockers:
            advances.append(PlannedAdvance(slug=slug, reason=r.reason))
        else:
            reason = r.blockers[0] if r.blockers else r.reason
            blocked.append(BlockedItem(slug=slug, kind=_classify_blocker(reason), reason=reason))
    return candidates, advances, blocked


def _slug_from_live_key(key: str) -> str:
    return key.split("#", 1)[0]


def _live_warnings(by_slug: dict[str, dict], live: tuple[str, ...]) -> list[str]:
    return [f"--live key {key!r} matches no known item" for key in live if _slug_from_live_key(key) not in by_slug]


def _sort_candidates(candidates: list[tuple[dict, _workflow.RouteResult]]) -> list[tuple[dict, _workflow.RouteResult]]:
    return sorted(
        candidates,
        key=lambda pair: (
            _hierarchy.PICK_ORDER.get(pair[0].get("status"), 99),
            str(pair[0].get("opened") or ""),
            pair[0]["slug"],
        ),
    )


def _subtree_items(items: list[dict], root: str) -> list[dict]:
    """All descendants of root at any depth, any status — for the epic-worktree
    stamp fallback, which must see items the (gated) frontier walk wouldn't
    necessarily visit."""
    children_of: dict[str, list[dict]] = {}
    for it in items:
        parent = it.get("parent")
        if parent:
            children_of.setdefault(parent, []).append(it)
    out: list[dict] = []
    stack = list(children_of.get(root, []))
    seen = {root}
    while stack:
        node = stack.pop()
        if node["slug"] in seen:
            continue
        seen.add(node["slug"])
        out.append(node)
        stack.extend(children_of.get(node["slug"], []))
    return out


def _epic_worktree_stamp(items: list[dict], root_item: dict) -> tuple[str, str] | None:
    """(path, branch) of 'the epic worktree' rules 2-3 reuse/fork against: the
    root's own stamp, falling back to the first stamped descendant in pick
    order (children inherit the epic worktree stamp by running stages inside
    it — see design spec 'Cold start')."""
    if root_item.get("worktree") and root_item.get("branch"):
        return str(root_item["worktree"]), str(root_item["branch"])
    stamped = [it for it in _subtree_items(items, root_item["slug"]) if it.get("worktree") and it.get("branch")]
    if not stamped:
        return None
    stamped.sort(
        key=lambda it: (_hierarchy.PICK_ORDER.get(it.get("status"), 99), str(it.get("opened") or ""), it["slug"])
    )
    chosen = stamped[0]
    return str(chosen["worktree"]), str(chosen["branch"])


def _resolve_worktree(
    item: dict,
    *,
    epic_worktree_path: str | None,
    epic_branch: str,
    live_worktrees: set[str],
    accepted_worktrees: set[str],
    epic_worktree_claimed: bool,
    worktree_exists: dict[str, bool | None],
    default_base: str,
) -> tuple[WorktreeAction | None, bool]:
    """Resolve one accepted dispatch's worktree action (design spec rules 1-4).

    Returns (action, claims_epic_slot). action is None only for the
    worktree-pending case: the caller drops the item to blocked/worktree-pending
    without consuming a dispatch slot or advancing epic_worktree_claimed.
    """
    own_path, own_branch = item.get("worktree"), item.get("branch")
    if own_path and own_branch:
        return (
            WorktreeAction(
                action="reuse",
                path=str(own_path),
                branch=str(own_branch),
                base_branch=None,
                exists=worktree_exists.get(str(own_path)),
            ),
            False,
        )
    if epic_worktree_path is not None:
        occupied = epic_worktree_path in live_worktrees or epic_worktree_path in accepted_worktrees
        if not occupied:
            return (
                WorktreeAction(
                    action="reuse",
                    path=epic_worktree_path,
                    branch=epic_branch,
                    base_branch=None,
                    exists=worktree_exists.get(epic_worktree_path),
                ),
                False,
            )
        return (
            WorktreeAction(
                action="fork-child",
                path=None,
                branch=_branch_name(item["slug"], str(item.get("kind", ""))),
                base_branch=epic_branch,
                exists=None,
            ),
            False,
        )
    if epic_worktree_claimed:
        return None, False
    return (
        WorktreeAction(action="create-top-level", path=None, branch=epic_branch, base_branch=default_base, exists=None),
        True,
    )


def _assemble_prompt(*, slug: str, key: str, mode: str, workspace: str, merge_target: str) -> str:
    lines = [
        f"Run /graph-wiki:next {slug}.",
        f"GRAPH_WIKI_WORKSPACE={workspace}",
        f"Dispatch key: {key}",
        "Send worker_done when the stage artifact is written and the item advanced.",
    ]
    if mode == "attend":
        lines.append(
            "The user may join this terminal to answer this stage's questions; ask normally via interactive prompts."
        )
    elif mode == "relay":
        lines.append(
            "Auto-drive context: relay the merge/PR/hold/discard decision via one `orca orchestration ask`; "
            f"merge target is `{merge_target}`."
        )
    return "\n".join(lines)


def plan(
    items: list[dict],
    root: str,
    *,
    auto_drive: dict,
    permission_mode: str,
    live: tuple[str, ...],
    worktree_exists: dict[str, bool | None],
    workspace: str,
    default_base: str,
) -> OrchestratePlan:
    """Compute the full dispatch plan for root's subtree. Never mutates anything."""
    by_slug = {it["slug"]: it for it in items}
    warnings = _live_warnings(by_slug, live)
    max_parallel = int(auto_drive.get("max_parallel", 2))

    root_item = by_slug.get(root)
    if root_item is not None and (
        str(root_item.get("status")) in _lint.TERMINAL_STATUSES or root_item.get("phase") == "done"
    ):
        return OrchestratePlan(
            slug=root,
            terminal=True,
            max_parallel=max_parallel,
            permission_mode=permission_mode,
            live=tuple(live),
            slots_free=0,
            dispatches=(),
            advances=(),
            blocked=(),
            warnings=tuple(warnings),
        )

    candidates, advances, blocked = _frontier(items, root)
    candidates = _sort_candidates(candidates)
    slots_free = max(0, max_parallel - len(live))

    live_affects: set[str] = set()
    live_worktrees: set[str] = set()
    for key in live:
        it = by_slug.get(_slug_from_live_key(key))
        if it is None:
            continue
        live_affects.update(it.get("affects") or [])
        if it.get("worktree"):
            live_worktrees.add(str(it["worktree"]))

    epic_stamp = _epic_worktree_stamp(items, root_item) if root_item is not None else None
    epic_worktree_path = epic_stamp[0] if epic_stamp else None
    epic_branch = (
        epic_stamp[1] if epic_stamp else _branch_name(root, str(root_item.get("kind", "")) if root_item else "")
    )

    # Pass 1: affects serialization over ALL candidates (spec: checked against
    # live items and already-accepted candidates, in sorted order).
    accepted_affects: set[str] = set()
    survivors: list[tuple[dict, _workflow.RouteResult]] = []
    for item, route_result in candidates:
        affects = set(item.get("affects") or [])
        overlap = affects & (live_affects | accepted_affects)
        if not affects:
            blocked.append(
                BlockedItem(
                    slug=item["slug"], kind="affects-overlap", reason="declare affects to allow parallel dispatch"
                )
            )
            continue
        if overlap:
            blocked.append(
                BlockedItem(
                    slug=item["slug"],
                    kind="affects-overlap",
                    reason=f"affects overlap with a live or already-planned dispatch: {', '.join(sorted(overlap))}",
                )
            )
            continue
        survivors.append((item, route_result))
        accepted_affects |= affects

    # Pass 2: first slots_free survivors become dispatches; the rest -> capacity.
    accepted_worktrees: set[str] = set()
    epic_worktree_claimed = False
    dispatches: list[PlannedDispatch] = []
    for item, route_result in survivors:
        if len(dispatches) >= slots_free:
            blocked.append(BlockedItem(slug=item["slug"], kind="capacity", reason="ready, but no worker slot free"))
            continue
        phase = item.get("phase") or (route_result.on_dispatch.phase if route_result.on_dispatch else None)
        assert phase is not None, "a routed candidate always resolves a dispatch phase"
        worktree_action, claimed_now = _resolve_worktree(
            item,
            epic_worktree_path=epic_worktree_path,
            epic_branch=epic_branch,
            live_worktrees=live_worktrees,
            accepted_worktrees=accepted_worktrees,
            epic_worktree_claimed=epic_worktree_claimed,
            worktree_exists=worktree_exists,
            default_base=default_base,
        )
        if worktree_action is None:
            blocked.append(
                BlockedItem(
                    slug=item["slug"],
                    kind="worktree-pending",
                    reason="epic worktree is being created by another dispatch in this plan",
                )
            )
            continue
        if claimed_now:
            epic_worktree_claimed = True
        if worktree_action.path:
            accepted_worktrees.add(worktree_action.path)

        mode = _MODE_BY_PHASE.get(phase, "autonomous")
        # Every non-root candidate reached _frontier's walk via children_of, which only
        # indexes items with a truthy "parent" — so item["slug"] != root already implies
        # item.get("parent") is set; the parent check would be redundant.
        merge_target = epic_branch if item["slug"] != root else default_base
        model_resolution = resolve_model(
            auto_drive, phase=phase, kind=str(item.get("kind", "")), effort=item.get("effort")
        )
        key = f"{item['slug']}#{phase}"
        dispatches.append(
            PlannedDispatch(
                key=key,
                slug=item["slug"],
                phase=phase,
                kind=str(item.get("kind", "")),
                effort=item.get("effort"),
                skill=route_result.skill,
                mode=mode,
                model=model_resolution.model if model_resolution else None,
                reasoning_effort=model_resolution.reasoning_effort if model_resolution else None,
                worktree=worktree_action,
                merge_target=merge_target,
                prompt=_assemble_prompt(
                    slug=item["slug"], key=key, mode=mode, workspace=workspace, merge_target=merge_target
                ),
            )
        )

    return OrchestratePlan(
        slug=root,
        terminal=False,
        max_parallel=max_parallel,
        permission_mode=permission_mode,
        live=tuple(live),
        slots_free=slots_free,
        dispatches=tuple(dispatches),
        advances=tuple(advances),
        blocked=tuple(blocked),
        warnings=tuple(warnings),
    )
