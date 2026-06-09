"""Routing table for the work-item workflow: (kind, status, phase, effort) -> action.

Pure functions, no I/O. `route()` returns the stage skill to dispatch plus the
dispatch-time and completion-time transitions. `gw work next` reports the
result; `gw work advance` applies `on_dispatch or on_complete` as the single
mutation point. Kind variants later are one-row edits here.
"""

from __future__ import annotations

from dataclasses import dataclass

from work_io.lifecycle_lint import (
    BUG_LIKE_KINDS,
    TERMINAL_STATUSES,
    VALID_EFFORTS,
    VALID_KINDS,
    VALID_PHASES,
    VALID_STATUSES,
)

SMALL_EFFORTS = frozenset({"xs", "s"})
DIAGNOSIS_KINDS = frozenset({"bug", "security", "perf"})

# Sentinel phase reported when the design-complete fork cannot be decided
# without an effort value. Never written to frontmatter — `advance` refuses
# any transition that still requires effort.
PLAN_OR_EXECUTE = "plan-or-execute"


@dataclass(frozen=True)
class WorkItemState:
    kind: str
    status: str
    phase: str | None = None
    effort: str | None = None
    has_plan_doc: bool = False


@dataclass(frozen=True)
class Transition:
    """A single frontmatter mutation. None fields are left unchanged."""

    phase: str | None = None
    status: str | None = None
    requires: tuple[str, ...] = ()
    sync_plan_table: bool = False
    stamp_doc: str | None = None  # "spec_doc" | "plan_doc"


@dataclass(frozen=True)
class RouteResult:
    skill: str | None
    reason: str
    artifact_slot: str | None = None  # "specs" | "plans" | None
    on_dispatch: Transition | None = None
    on_complete: Transition | None = None
    blockers: tuple[str, ...] = ()


def route(state: WorkItemState) -> RouteResult:
    """Compute the workflow action for a work item's current state."""
    blockers = _validate(state)
    if blockers:
        return RouteResult(skill=None, reason="invalid item", blockers=tuple(blockers))
    if state.phase == "done":
        return RouteResult(
            skill=None,
            reason="pipeline complete",
            blockers=("phase=done: nothing to dispatch; archive once the item ages out",),
        )
    if state.status in TERMINAL_STATUSES or state.status == "mitigated":
        return RouteResult(
            skill=None,
            reason="disposition is human-owned",
            blockers=(f"status {state.status!r} never dispatches; set status to 'open' to re-enter the pipeline",),
        )
    if state.phase is None:
        return _entry(state)
    stage = {"design": _design, "plan": _plan, "execute": _execute, "finish": _finish}
    return stage[state.phase](state)


def _validate(state: WorkItemState) -> list[str]:
    blockers = []
    if state.kind not in VALID_KINDS:
        blockers.append(f"kind {state.kind!r} not in {sorted(VALID_KINDS)}")
    if state.status not in VALID_STATUSES:
        blockers.append(f"status {state.status!r} not in {sorted(VALID_STATUSES)}")
    if state.phase is not None and state.phase not in VALID_PHASES:
        blockers.append(f"phase {state.phase!r} not in {sorted(VALID_PHASES)}")
    if state.effort is not None and state.effort not in VALID_EFFORTS:
        blockers.append(f"effort {state.effort!r} not in {sorted(VALID_EFFORTS)}; re-size via --effort")
    return blockers


def _entry(state: WorkItemState) -> RouteResult:
    """First dispatch: status open, no phase. Sets the entry phase via on_dispatch."""
    if state.status != "open":
        return RouteResult(
            skill=None,
            reason="invalid entry",
            blockers=(
                f"no phase and status {state.status!r}; set status 'open' to enter at design, "
                "or hand-set phase (e.g. phase: execute for an accepted item with a plan) "
                "to adopt an in-flight item mid-pipeline",
            ),
        )
    if state.kind == "test-gap":
        # The gap is identified at filing time — skip design. The effort fork
        # applies here since there is no design stage to advance out of.
        if state.effort is None:
            return RouteResult(
                skill=None,
                reason="test-gap entry forks on effort",
                blockers=(
                    "effort required: test-gap routes to execute (xs/s) or plan (m/l/xl); "
                    "size the item and advance with --effort",
                ),
            )
        if state.effort in SMALL_EFFORTS:
            return RouteResult(
                skill="test-driven-development",
                reason=f"test-gap with effort {state.effort}: skip design and plan",
                on_dispatch=Transition(phase="execute", status="in-progress", requires=("owner",)),
                on_complete=Transition(phase="finish"),
            )
        return RouteResult(
            skill="writing-plans",
            reason=f"test-gap with effort {state.effort}: skip design, plan first",
            artifact_slot="plans",
            on_dispatch=Transition(phase="plan"),
            on_complete=Transition(phase="execute", status="accepted", sync_plan_table=True, stamp_doc="plan_doc"),
        )
    skill = "systematic-debugging" if state.kind in DIAGNOSIS_KINDS else "brainstorming"
    return RouteResult(
        skill=skill,
        reason=f"{state.kind} entering the pipeline at design",
        artifact_slot="specs",
        on_dispatch=Transition(phase="design"),
        on_complete=_design_complete(state),
    )


def _design_complete(state: WorkItemState) -> Transition:
    """The effort fork: small bug-like work skips planning."""
    if state.kind in BUG_LIKE_KINDS:
        if state.effort is None:
            return Transition(phase=PLAN_OR_EXECUTE, requires=("effort",), stamp_doc="spec_doc")
        if state.effort in SMALL_EFFORTS:
            return Transition(phase="execute", stamp_doc="spec_doc")
    return Transition(phase="plan", stamp_doc="spec_doc")


def _design(state: WorkItemState) -> RouteResult:
    skill = "systematic-debugging" if state.kind in DIAGNOSIS_KINDS else "brainstorming"
    return RouteResult(
        skill=skill,
        reason=f"{state.kind} at design stage",
        artifact_slot="specs",
        on_complete=_design_complete(state),
    )


def _plan(state: WorkItemState) -> RouteResult:
    return RouteResult(
        skill="writing-plans",
        reason=f"{state.kind} at plan stage",
        artifact_slot="plans",
        on_complete=Transition(phase="execute", status="accepted", sync_plan_table=True, stamp_doc="plan_doc"),
    )


def _execute(state: WorkItemState) -> RouteResult:
    if state.has_plan_doc:
        skill, reason = "subagent-driven-development", "execute stage with a written plan"
    else:
        skill, reason = "test-driven-development", "execute stage via small-bug shortcut (no plan)"
    on_dispatch = None
    if state.status != "in-progress":
        on_dispatch = Transition(status="in-progress", requires=("owner",))
    return RouteResult(
        skill=skill,
        reason=reason,
        on_dispatch=on_dispatch,
        on_complete=Transition(phase="finish"),
    )


def _finish(state: WorkItemState) -> RouteResult:
    return RouteResult(
        skill="finishing-a-development-branch",
        reason=f"{state.kind} at finish stage",
        on_complete=Transition(phase="done", status="resolved", requires=("resolved_in",)),
    )
