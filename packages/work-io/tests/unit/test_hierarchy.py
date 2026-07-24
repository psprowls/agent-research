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
