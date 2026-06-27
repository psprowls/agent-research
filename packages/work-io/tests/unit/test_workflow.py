from __future__ import annotations

import pytest
from work_io.hierarchy import ChildRollup
from work_io.workflow import PLAN_OR_EXECUTE, Transition, WorkItemState, route


def _state(
    kind: str = "feature",
    status: str = "open",
    phase: str | None = None,
    effort: str | None = None,
    has_plan_doc: bool = False,
) -> WorkItemState:
    return WorkItemState(kind=kind, status=status, phase=phase, effort=effort, has_plan_doc=has_plan_doc)


# --- Validation blockers ---


@pytest.mark.parametrize(
    "state",
    [
        _state(kind="initiative"),
        _state(status="todo"),
        _state(phase="designing"),
        _state(effort="s"),
    ],
)
def test_invalid_enums_block(state: WorkItemState) -> None:
    r = route(state)
    assert r.skill is None
    assert r.blockers


# --- Terminal / mitigated / done ---


@pytest.mark.parametrize("status", ["resolved", "wontfix", "superseded", "mitigated"])
def test_terminal_and_mitigated_never_dispatch(status: str) -> None:
    r = route(_state(status=status, phase="execute"))
    assert r.skill is None
    assert r.on_dispatch is None and r.on_complete is None
    assert r.blockers


def test_phase_done_reports_complete() -> None:
    r = route(_state(status="resolved", phase="done"))
    assert r.skill is None
    assert r.blockers  # report-and-exit surfaces as a blocker for uniform CLI handling


# --- First dispatch (entry) ---


@pytest.mark.parametrize("kind", ["feature", "epic", "spike", "tech-debt"])
def test_entry_design_first_kinds_get_brainstorming(kind: str) -> None:
    r = route(_state(kind=kind))
    assert r.skill == "brainstorming"
    assert r.artifact_slot == "specs"
    assert r.on_dispatch == Transition(phase="design")


@pytest.mark.parametrize("kind", ["bug", "security", "perf"])
def test_entry_diagnosis_kinds_get_systematic_debugging(kind: str) -> None:
    r = route(_state(kind=kind))
    assert r.skill == "systematic-debugging"
    assert r.artifact_slot == "specs"
    assert r.on_dispatch == Transition(phase="design")


def test_entry_requires_open_status() -> None:
    r = route(_state(status="accepted", phase=None))
    assert r.skill is None
    assert r.blockers


def test_entry_test_gap_without_effort_blocks() -> None:
    r = route(_state(kind="test-gap"))
    assert r.skill is None
    assert any("effort" in b for b in r.blockers)


@pytest.mark.parametrize("effort", ["xtra-small", "small"])
def test_entry_test_gap_small_goes_straight_to_execute(effort: str) -> None:
    r = route(_state(kind="test-gap", effort=effort))
    assert r.skill == "test-driven-development"
    assert r.on_dispatch == Transition(phase="execute", status="in-progress", requires=("owner",))


@pytest.mark.parametrize("effort", ["medium", "large", "xtra-large"])
def test_entry_test_gap_large_goes_to_plan(effort: str) -> None:
    r = route(_state(kind="test-gap", effort=effort))
    assert r.skill == "writing-plans"
    assert r.artifact_slot == "plans"
    assert r.on_dispatch == Transition(phase="plan")


# --- Design stage ---


def test_design_bug_like_small_effort_shortcuts_to_execute() -> None:
    r = route(_state(kind="bug", phase="design", effort="small"))
    assert r.skill == "systematic-debugging"
    assert r.on_dispatch is None
    assert r.on_complete == Transition(phase="execute", stamp_doc="spec_doc")


def test_design_bug_like_large_effort_goes_to_plan() -> None:
    r = route(_state(kind="tech-debt", phase="design", effort="large"))
    assert r.skill == "brainstorming"
    assert r.on_complete == Transition(phase="plan", stamp_doc="spec_doc")


def test_design_bug_like_missing_effort_reports_fork_sentinel() -> None:
    r = route(_state(kind="bug", phase="design"))
    assert r.skill == "systematic-debugging"
    assert not r.blockers  # dispatch is fine; only completion needs effort
    assert r.on_complete == Transition(phase=PLAN_OR_EXECUTE, requires=("effort",), stamp_doc="spec_doc")


@pytest.mark.parametrize("kind", ["feature", "epic", "spike"])
def test_design_feature_like_always_plans_even_when_small(kind: str) -> None:
    r = route(_state(kind=kind, phase="design", effort="xtra-small"))
    assert r.on_complete == Transition(phase="plan", stamp_doc="spec_doc")


# --- Plan stage ---


def test_plan_stage_routes_to_writing_plans() -> None:
    r = route(_state(kind="feature", phase="plan"))
    assert r.skill == "writing-plans"
    assert r.artifact_slot == "plans"
    assert r.on_complete == Transition(phase="execute", status="accepted", sync_plan_table=True, stamp_doc="plan_doc")


# --- Execute stage ---


def test_execute_with_plan_doc_uses_subagent_driven_development() -> None:
    r = route(_state(kind="feature", status="accepted", phase="execute", has_plan_doc=True))
    assert r.skill == "subagent-driven-development"
    assert r.on_dispatch == Transition(status="in-progress", requires=("owner",))
    assert r.on_complete == Transition(phase="finish")


def test_execute_shortcut_path_uses_tdd() -> None:
    r = route(_state(kind="bug", status="open", phase="execute", effort="small"))
    assert r.skill == "test-driven-development"
    assert r.on_dispatch == Transition(status="in-progress", requires=("owner",))


def test_execute_already_in_progress_has_no_dispatch_transition() -> None:
    r = route(_state(kind="bug", status="in-progress", phase="execute", effort="small"))
    assert r.on_dispatch is None
    assert r.on_complete == Transition(phase="finish")


# --- Finish stage ---


def test_finish_routes_to_finishing_a_development_branch() -> None:
    r = route(_state(kind="feature", status="in-progress", phase="finish"))
    assert r.skill == "finishing-a-development-branch"
    assert r.on_complete == Transition(phase="done", status="resolved", requires=("resolved_in",))


# --- Epic routing + dependency gate ---


def _epic_state(
    phase: str | None = None,
    effort: str | None = "large",
    rollup: ChildRollup | None = None,
    unmet_deps: tuple[str, ...] = (),
    depends_on: tuple[str, ...] = (),
) -> WorkItemState:
    return WorkItemState(
        kind="epic",
        status="open" if phase in (None, "design") else "accepted",
        phase=phase,
        effort=effort,
        depends_on=depends_on,
        unmet_deps=unmet_deps,
        child_rollup=rollup,
    )


def test_dependency_gate_blocks_when_unmet() -> None:
    state = WorkItemState(kind="feature", status="open", depends_on=("sib",), unmet_deps=("sib",))
    r = route(state)
    assert r.skill is None and r.on_dispatch is None and r.on_complete is None
    assert any("sib" in b for b in r.blockers)


def test_dependency_gate_passes_when_all_terminal() -> None:
    state = WorkItemState(kind="feature", status="open", depends_on=("sib",), unmet_deps=())
    r = route(state)
    assert r.skill == "brainstorming"


def test_epic_never_skips_plan_any_effort() -> None:
    for eff in ("xtra-small", "small", "medium", "large", "xtra-large"):
        r = route(_epic_state(phase="design", effort=eff))
        assert r.on_complete == Transition(phase="plan", stamp_doc="spec_doc")


def test_epic_plan_dispatches_planning_epics() -> None:
    r = route(_epic_state(phase="plan"))
    assert r.skill == "planning-epics"
    assert r.artifact_slot == "plans"
    assert r.on_complete == Transition(phase="execute", status="accepted", stamp_doc="plan_doc")
    assert r.on_complete.sync_plan_table is False


def test_epic_execute_no_children_blocks() -> None:
    r = route(_epic_state(phase="execute", rollup=ChildRollup(0, 0, ())))
    assert r.skill is None and r.blockers


def test_epic_execute_partial_waits_with_open_slugs() -> None:
    r = route(_epic_state(phase="execute", rollup=ChildRollup(2, 1, ("child-b",))))
    assert r.skill is None
    assert r.on_complete is None
    assert any("child-b" in b for b in r.blockers)


def test_epic_execute_all_terminal_is_satisfied_gate() -> None:
    r = route(_epic_state(phase="execute", rollup=ChildRollup(2, 2, ())))
    assert r.skill is None
    assert r.blockers == ()
    assert r.on_complete == Transition(phase="finish")


def test_epic_finish_satisfied_gate_to_done() -> None:
    r = route(_epic_state(phase="finish"))
    assert r.skill is None and r.blockers == ()
    assert r.on_complete == Transition(phase="done", status="resolved")
    assert r.on_complete.requires == ()
