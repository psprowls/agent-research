from __future__ import annotations

from work_io.hierarchy import ChildRollup, child_rollup, dep_states, unresolved_depends_on


def _item(slug: str, status: str = "open", parent: str | None = None) -> dict:
    return {"slug": slug, "status": status, "parent": parent}


def test_child_rollup_empty() -> None:
    items = [_item("epic-x", parent=None), _item("unrelated", parent="other")]
    assert child_rollup(items, "epic-x") == ChildRollup(total=0, terminal=0, open_slugs=())


def test_child_rollup_partial() -> None:
    items = [
        _item("a", status="resolved", parent="epic-x"),
        _item("b", status="open", parent="epic-x"),
        _item("c", status="in-progress", parent="epic-x"),
    ]
    r = child_rollup(items, "epic-x")
    assert r.total == 3
    assert r.terminal == 1
    assert r.open_slugs == ("b", "c")  # sorted, non-terminal


def test_child_rollup_all_terminal() -> None:
    items = [
        _item("a", status="resolved", parent="epic-x"),
        _item("b", status="wontfix", parent="epic-x"),
    ]
    r = child_rollup(items, "epic-x")
    assert r.total == 2 and r.terminal == 2 and r.open_slugs == ()


def test_dep_states_met_and_unmet() -> None:
    items = [_item("dep1", status="resolved"), _item("dep2", status="open")]
    assert dep_states(items, ("dep1", "dep2")) == ("dep2",)


def test_dep_states_missing_is_unmet() -> None:
    items = [_item("dep1", status="resolved")]
    assert dep_states(items, ("dep1", "ghost")) == ("ghost",)


def test_dep_states_all_met() -> None:
    items = [_item("dep1", status="resolved"), _item("dep2", status="superseded")]
    assert dep_states(items, ("dep1", "dep2")) == ()


def test_unresolved_depends_on_exact_match_is_absent() -> None:
    items = [_item("2026-06-26-sib")]
    assert unresolved_depends_on(items, ["2026-06-26-sib"]) == {}


def test_unresolved_depends_on_no_title_match_maps_to_none() -> None:
    items = [_item("2026-06-26-sib")]
    assert unresolved_depends_on(items, ["ghost"]) == {"ghost": None}


def test_unresolved_depends_on_unique_title_match_maps_to_full_slug() -> None:
    items = [_item("2026-06-26-sib")]
    assert unresolved_depends_on(items, ["sib"]) == {"sib": "2026-06-26-sib"}


def test_unresolved_depends_on_ambiguous_title_match_maps_to_none() -> None:
    items = [_item("2026-06-26-sib"), _item("2026-06-27-sib")]
    assert unresolved_depends_on(items, ["sib"]) == {"sib": None}


def test_unresolved_depends_on_archived_slug_counts_as_known() -> None:
    items = [_item("2026-06-26-sib", status="resolved")]
    assert unresolved_depends_on(items, ["2026-06-26-sib"]) == {}


def _hitem(slug: str, status: str = "open", parent: str | None = None, opened: str = "") -> dict:
    return {"slug": slug, "status": status, "parent": parent, "opened": opened}


def test_parent_kinds_constant() -> None:
    from work_io.lifecycle_lint import PARENT_KINDS

    assert PARENT_KINDS == frozenset({"epic", "feature"})


def test_children_map_sorts_by_opened_then_slug() -> None:
    from work_io.hierarchy import children_map

    items = [
        _hitem("p"),
        _hitem("b-later", parent="p", opened="2026-07-02"),
        _hitem("a-early", parent="p", opened="2026-07-01"),
        _hitem("z-same-day", parent="p", opened="2026-07-01"),
    ]
    assert children_map(items) == {"p": ["a-early", "z-same-day", "b-later"]}


def test_children_map_includes_terminal_children() -> None:
    from work_io.hierarchy import children_map

    items = [_hitem("p"), _hitem("c1", status="resolved", parent="p", opened="2026-07-01")]
    assert children_map(items) == {"p": ["c1"]}


def test_children_map_omits_childless_parents() -> None:
    from work_io.hierarchy import children_map

    assert children_map([_hitem("p"), _hitem("standalone")]) == {}


def _ditem(slug, kind="bug", status="open", parent=None, phase=None, depends_on=(), opened=""):
    return {
        "slug": slug,
        "kind": kind,
        "status": status,
        "parent": parent,
        "phase": phase,
        "depends_on": tuple(depends_on),
        "opened": opened,
    }


def test_descend_epic_to_oldest_open_child() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("e", kind="epic", phase="execute"),
        _ditem("c-new", parent="e", opened="2026-07-02"),
        _ditem("c-old", parent="e", opened="2026-07-01"),
    ]
    r = descend(items, "e")
    assert r.leaf == "c-old" and r.path == ("e", "c-old") and r.blocked_at is None


def test_descend_prefers_in_progress_then_accepted() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("e", kind="epic", phase="execute"),
        _ditem("c-open", parent="e", opened="2026-07-01"),
        _ditem("c-acc", status="accepted", parent="e", opened="2026-07-02"),
        _ditem("c-wip", status="in-progress", parent="e", opened="2026-07-03"),
    ]
    assert descend(items, "e").leaf == "c-wip"
    items = [it for it in items if it["slug"] != "c-wip"]
    assert descend(items, "e").leaf == "c-acc"


def test_descend_skips_dep_blocked_children() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("e", kind="epic", phase="execute"),
        _ditem("blocked", parent="e", depends_on=("free",), opened="2026-07-01"),
        _ditem("free", parent="e", opened="2026-07-02"),
    ]
    assert descend(items, "e").leaf == "free"


def test_descend_recurses_into_gated_feature_child() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("e", kind="epic", phase="execute"),
        _ditem("f", kind="feature", status="in-progress", parent="e", phase="execute", opened="2026-07-01"),
        _ditem("fbug", parent="f", opened="2026-07-02"),
    ]
    r = descend(items, "e")
    assert r.leaf == "fbug" and r.path == ("e", "f", "fbug")


def test_descend_stops_at_feature_child_still_at_design() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("e", kind="epic", phase="execute"),
        _ditem("f", kind="feature", parent="e", phase="design", opened="2026-07-01"),
        _ditem("fbug", parent="f", opened="2026-07-02"),
    ]
    assert descend(items, "e").leaf == "f"  # design-phase feature is dispatched itself


def test_descend_no_candidate_reports_blocked_at() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("e", kind="epic", phase="execute"),
        _ditem("m", status="mitigated", parent="e", opened="2026-07-01"),
    ]
    r = descend(items, "e")
    assert r.leaf is None and r.blocked_at == "e" and r.reason


def test_descend_cycle_is_safe() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("a", kind="feature", status="in-progress", phase="execute", parent="b", opened="2026-07-01"),
        _ditem("b", kind="feature", status="in-progress", phase="execute", parent="a", opened="2026-07-01"),
    ]
    r = descend(items, "a")
    assert r.leaf is None and "cycle" in (r.reason or "")


def test_descend_depth_cap_on_acyclic_chain() -> None:
    from work_io.hierarchy import descend

    items = [_ditem("e", kind="epic", phase="execute")]
    for i in range(40):
        items.append(
            _ditem(
                f"f{i}",
                kind="feature",
                status="in-progress",
                parent=f"f{i - 1}" if i > 0 else "e",
                phase="execute",
                opened="2026-07-01",
            )
        )
    items.append(_ditem("leaf", parent="f39", opened="2026-07-01"))
    r = descend(items, "e")
    assert r.leaf is None and "depth cap" in (r.reason or "") and "cycle" not in (r.reason or "")


def test_descend_unknown_slug_blocks() -> None:
    from work_io.hierarchy import descend

    r = descend([], "ghost")
    assert r.leaf is None and r.blocked_at == "ghost"


def test_descend_non_gated_node_is_its_own_leaf() -> None:
    from work_io.hierarchy import descend

    items = [_ditem("f", kind="feature", phase="plan"), _ditem("c", parent="f")]
    assert descend(items, "f").leaf == "f"  # plan phase never gates


def test_descend_epic_at_plan_with_open_child_is_its_own_leaf() -> None:
    from work_io.hierarchy import descend

    items = [
        _ditem("e", kind="epic", phase="plan"),
        _ditem("c", parent="e", opened="2026-07-01"),
    ]
    assert descend(items, "e").leaf == "e"  # not yet at execute: the epic is its own actionable item
