from __future__ import annotations

from work_io.hierarchy import ChildRollup, child_rollup, dep_states


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
