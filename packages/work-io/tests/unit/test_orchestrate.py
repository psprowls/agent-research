from __future__ import annotations

from work_io.orchestrate import _branch_name


def test_branch_name_root_epic() -> None:
    assert _branch_name("2026-08-07-epic-orca-auto-drive-pipeline", "epic") == "epic/orca-auto-drive-pipeline"


def test_branch_name_epic_child_feature() -> None:
    assert (
        _branch_name("2026-08-07-epic-feature-orchestrate-dispatch-decision-engine", "feature")
        == "feature/orchestrate-dispatch-decision-engine"
    )


def test_branch_name_lone_bug() -> None:
    assert _branch_name("2026-08-07-fix-login-timeout", "bug") == "bug/fix-login-timeout"


def _item(
    slug: str,
    *,
    status: str = "open",
    kind: str = "feature",
    phase: str | None = None,
    parent: str | None = None,
    depends_on: tuple[str, ...] = (),
    opened: str = "2026-08-01",
    affects: list[str] | None = None,
    effort: str | None = None,
    worktree: str | None = None,
    branch: str | None = None,
    has_plan_doc: bool = False,
) -> dict:
    return {
        "slug": slug,
        "status": status,
        "kind": kind,
        "phase": phase,
        "parent": parent,
        "depends_on": depends_on,
        "opened": opened,
        "affects": affects or [],
        "effort": effort,
        "worktree": worktree,
        "branch": branch,
        "has_plan_doc": has_plan_doc,
    }


def test_frontier_epic_execute_recurses_into_open_children() -> None:
    from work_io.orchestrate import _frontier

    items = [
        _item("epic-x", kind="epic", status="accepted", phase="execute"),
        _item("epic-x-child-a", kind="feature", status="accepted", phase="execute", parent="epic-x", has_plan_doc=True),
        _item("epic-x-child-b", kind="feature", status="resolved", phase="done", parent="epic-x"),
    ]
    candidates, advances, blocked = _frontier(items, "epic-x")
    assert [c[0]["slug"] for c in candidates] == ["epic-x-child-a"]
    assert advances == []
    assert blocked == []  # terminal child-b is skipped silently, not blocked


def test_frontier_satisfied_gate_becomes_advance() -> None:
    from work_io.orchestrate import _frontier

    items = [
        _item("epic-x", kind="epic", status="accepted", phase="execute"),
        _item("epic-x-child-a", kind="feature", status="resolved", phase="done", parent="epic-x"),
    ]
    candidates, advances, blocked = _frontier(items, "epic-x")
    assert candidates == []
    assert [a.slug for a in advances] == ["epic-x"]
    assert advances[0].reason == "epic children complete"


def test_frontier_unknown_root_is_single_invalid_blocked() -> None:
    from work_io.orchestrate import _frontier

    candidates, advances, blocked = _frontier([], "ghost")
    assert candidates == [] and advances == []
    assert [b.kind for b in blocked] == ["invalid"]


def test_frontier_unmet_deps_blocks_as_deps() -> None:
    from work_io.orchestrate import _frontier

    items = [
        _item("dep", status="open"),
        _item("leaf", depends_on=("dep",)),
    ]
    _candidates, _advances, blocked = _frontier(items, "leaf")
    assert [b.kind for b in blocked] == ["deps"]


def test_sort_candidates_by_pick_order_then_opened_then_slug() -> None:
    from work_io.orchestrate import _sort_candidates

    a = (_item("b-open", status="open", opened="2026-08-01"), None)
    b = (_item("a-accepted", status="accepted", opened="2026-08-02"), None)
    c = (_item("c-in-progress", status="in-progress", opened="2026-08-03"), None)
    got = [pair[0]["slug"] for pair in _sort_candidates([a, b, c])]
    assert got == ["c-in-progress", "a-accepted", "b-open"]


def test_live_warnings_flags_unknown_slug() -> None:
    from work_io.orchestrate import _live_warnings

    by_slug = {"known": _item("known")}
    assert _live_warnings(by_slug, ("known#execute", "ghost#plan")) == ["--live key 'ghost#plan' matches no known item"]


def test_resolve_worktree_reuses_own_stamp() -> None:
    from work_io.orchestrate import _resolve_worktree

    item = _item("child", worktree="/wt/child", branch="feature/child")
    action, claimed = _resolve_worktree(
        item,
        epic_worktree_path="/wt/epic",
        epic_branch="epic/x",
        live_worktrees=set(),
        accepted_worktrees=set(),
        epic_worktree_claimed=False,
        worktree_exists={"/wt/child": True},
        default_base="develop",
    )
    assert action.action == "reuse" and action.path == "/wt/child" and action.exists is True
    assert claimed is False


def test_resolve_worktree_reuses_free_epic_worktree() -> None:
    from work_io.orchestrate import WorktreeAction, _resolve_worktree

    item = _item("child")
    action, claimed = _resolve_worktree(
        item,
        epic_worktree_path="/wt/epic",
        epic_branch="epic/x",
        live_worktrees=set(),
        accepted_worktrees=set(),
        epic_worktree_claimed=False,
        worktree_exists={"/wt/epic": True},
        default_base="develop",
    )
    assert action == WorktreeAction(action="reuse", path="/wt/epic", branch="epic/x", base_branch=None, exists=True)
    assert claimed is False


def test_resolve_worktree_forks_when_epic_worktree_occupied() -> None:
    from work_io.orchestrate import _resolve_worktree

    item = _item("child", kind="feature")
    action, claimed = _resolve_worktree(
        item,
        epic_worktree_path="/wt/epic",
        epic_branch="epic/x",
        live_worktrees={"/wt/epic"},
        accepted_worktrees=set(),
        epic_worktree_claimed=False,
        worktree_exists={},
        default_base="develop",
    )
    assert action.action == "fork-child" and action.path is None and action.base_branch == "epic/x"
    assert claimed is False


def test_resolve_worktree_first_candidate_creates_top_level() -> None:
    from work_io.orchestrate import _resolve_worktree

    item = _item("root", kind="epic")
    action, claimed = _resolve_worktree(
        item,
        epic_worktree_path=None,
        epic_branch="epic/x",
        live_worktrees=set(),
        accepted_worktrees=set(),
        epic_worktree_claimed=False,
        worktree_exists={},
        default_base="develop",
    )
    assert action.action == "create-top-level" and action.base_branch == "develop" and action.path is None
    assert claimed is True


def test_resolve_worktree_second_candidate_pending_when_already_claimed() -> None:
    from work_io.orchestrate import _resolve_worktree

    item = _item("other")
    action, claimed = _resolve_worktree(
        item,
        epic_worktree_path=None,
        epic_branch="epic/x",
        live_worktrees=set(),
        accepted_worktrees=set(),
        epic_worktree_claimed=True,
        worktree_exists={},
        default_base="develop",
    )
    assert action is None and claimed is False


def test_epic_worktree_stamp_falls_back_to_stamped_descendant() -> None:
    from work_io.orchestrate import _epic_worktree_stamp

    root_item = _item("epic-x", kind="epic")
    items = [root_item, _item("epic-x-child", parent="epic-x", worktree="/wt/epic", branch="epic/x")]
    assert _epic_worktree_stamp(items, root_item) == ("/wt/epic", "epic/x")


def test_epic_worktree_stamp_none_when_nothing_stamped() -> None:
    from work_io.orchestrate import _epic_worktree_stamp

    root_item = _item("epic-x", kind="epic")
    assert _epic_worktree_stamp([root_item], root_item) is None


AUTO_DRIVE = {"max_parallel": 2, "models": {"execute": "claude-sonnet-5"}, "overrides": []}


def test_plan_terminal_root_is_empty() -> None:
    from work_io.orchestrate import plan

    items = [_item("root", status="resolved")]
    result = plan(
        items,
        "root",
        auto_drive=AUTO_DRIVE,
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert result.terminal is True
    assert result.dispatches == () and result.advances == ()


def test_plan_single_candidate_dispatches_with_prompt_and_mode() -> None:
    from work_io.orchestrate import plan

    items = [_item("bug-x", kind="bug", phase="execute", status="in-progress", affects=["pkg/a"])]
    result = plan(
        items,
        "bug-x",
        auto_drive=AUTO_DRIVE,
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert len(result.dispatches) == 1
    d = result.dispatches[0]
    assert d.key == "bug-x#execute" and d.mode == "autonomous" and d.model == "claude-sonnet-5"
    assert d.worktree.action == "create-top-level"
    assert "Run /graph-wiki:next bug-x." in d.prompt


def test_plan_mode_is_phase_keyed() -> None:
    from work_io.orchestrate import plan

    cases = [
        (_item("a-design", kind="bug", status="open", phase=None, affects=["pkg/a"]), "attend"),
        (_item("b-plan", kind="feature", status="accepted", phase="plan", affects=["pkg/b"]), "autonomous"),
        (_item("c-execute", kind="bug", status="in-progress", phase="execute", affects=["pkg/c"]), "autonomous"),
        (_item("d-finish", kind="feature", status="accepted", phase="finish", affects=["pkg/d"]), "relay"),
    ]
    for item, expected_mode in cases:
        result = plan(
            [item],
            item["slug"],
            auto_drive=AUTO_DRIVE,
            permission_mode="bypassPermissions",
            live=(),
            worktree_exists={},
            workspace="/ws",
            default_base="develop",
        )
        assert len(result.dispatches) == 1, (item["slug"], result.blocked)
        assert result.dispatches[0].mode == expected_mode


def test_plan_capacity_truncates_by_slots_free() -> None:
    from work_io.orchestrate import plan

    items = [
        _item("epic-x", kind="epic", status="accepted", phase="execute", worktree="/wt/epic-x", branch="epic/x"),
        _item(
            "epic-x-a",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-x",
            affects=["pkg/a"],
            opened="2026-08-01",
        ),
        _item(
            "epic-x-b",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-x",
            affects=["pkg/b"],
            opened="2026-08-02",
        ),
        _item(
            "epic-x-c",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-x",
            affects=["pkg/c"],
            opened="2026-08-03",
        ),
    ]
    result = plan(
        items,
        "epic-x",
        auto_drive={**AUTO_DRIVE, "max_parallel": 2},
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert [d.slug for d in result.dispatches] == ["epic-x-a", "epic-x-b"]
    assert [(b.slug, b.kind) for b in result.blocked] == [("epic-x-c", "capacity")]


def test_plan_unknown_live_key_warns_and_still_consumes_a_slot() -> None:
    from work_io.orchestrate import plan

    items = [_item("a", kind="bug", phase="execute", status="in-progress", affects=["pkg/a"])]
    auto_drive = {**AUTO_DRIVE, "max_parallel": 1}
    result = plan(
        items,
        "a",
        auto_drive=auto_drive,
        permission_mode="bypassPermissions",
        live=("ghost#plan",),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert result.warnings == ("--live key 'ghost#plan' matches no known item",)
    assert result.slots_free == 0
    assert any(b.kind == "capacity" for b in result.blocked)


def test_plan_two_overlapping_candidates_serialize_one_dispatches_one_blocks() -> None:
    from work_io.orchestrate import plan

    items = [
        _item("epic-x", kind="epic", status="accepted", phase="execute", worktree="/wt/epic-x", branch="epic/x"),
        _item(
            "epic-x-a",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-x",
            affects=["pkg/a"],
            opened="2026-08-01",
        ),
        _item(
            "epic-x-b",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-x",
            affects=["pkg/a"],
            opened="2026-08-02",
        ),
    ]
    result = plan(
        items,
        "epic-x",
        auto_drive={**AUTO_DRIVE, "max_parallel": 2},
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert [d.slug for d in result.dispatches] == ["epic-x-a"]
    [blocked_b] = [b for b in result.blocked if b.slug == "epic-x-b"]
    assert blocked_b.kind == "affects-overlap"
    assert "pkg/a" in blocked_b.reason


def test_plan_empty_affects_always_overlaps() -> None:
    from work_io.orchestrate import plan

    items = [_item("a", kind="bug", phase="execute", status="in-progress")]  # affects defaults to []
    result = plan(
        items,
        "a",
        auto_drive=AUTO_DRIVE,
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert result.dispatches == ()
    [blocked_a] = result.blocked
    assert blocked_a.kind == "affects-overlap"
    assert blocked_a.reason == "declare affects to allow parallel dispatch"


def test_plan_candidate_overlapping_live_affects_is_blocked() -> None:
    from work_io.orchestrate import plan

    items = [
        _item("live-item", kind="bug", phase="execute", status="in-progress", affects=["pkg/a"]),
        _item("b", kind="bug", phase="execute", status="in-progress", affects=["pkg/a"]),
    ]
    result = plan(
        items,
        "b",
        auto_drive={**AUTO_DRIVE, "max_parallel": 2},
        permission_mode="bypassPermissions",
        live=("live-item#execute",),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert result.dispatches == ()
    [blocked_b] = result.blocked
    assert blocked_b.slug == "b" and blocked_b.kind == "affects-overlap"
    assert "pkg/a" in blocked_b.reason


def test_plan_mitigated_item_blocks_as_human() -> None:
    from work_io.orchestrate import plan

    items = [_item("m", kind="bug", status="mitigated", phase="execute", affects=["pkg/m"])]
    result = plan(
        items,
        "m",
        auto_drive=AUTO_DRIVE,
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert result.dispatches == ()
    [blocked_m] = result.blocked
    assert blocked_m.kind == "human"
    assert "never dispatches" in blocked_m.reason


def test_plan_unsized_test_gap_blocks_as_effort_required() -> None:
    from work_io.orchestrate import plan

    items = [_item("gap-x", kind="test-gap", status="open", phase=None, affects=["pkg/g"])]
    result = plan(
        items,
        "gap-x",
        auto_drive=AUTO_DRIVE,
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert result.dispatches == ()
    [blocked_gap] = result.blocked
    assert blocked_gap.kind == "effort-required"
    assert blocked_gap.reason.startswith("effort required")


def test_plan_worktree_pending_blocks_without_consuming_slot_or_relaxing_claim() -> None:
    """Cold-start with 3 unstamped epic children and ample capacity: only the
    first pick-order candidate gets create-top-level; the rest land in
    blocked/worktree-pending (not dispatched, not capacity), and the claim
    made by the first candidate is never relaxed for later ones in the plan."""
    from work_io.orchestrate import plan

    items = [
        _item("epic-y", kind="epic", status="accepted", phase="execute"),
        _item(
            "epic-y-a",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-y",
            affects=["pkg/a"],
            opened="2026-08-01",
        ),
        _item(
            "epic-y-b",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-y",
            affects=["pkg/b"],
            opened="2026-08-02",
        ),
        _item(
            "epic-y-c",
            kind="bug",
            phase="execute",
            status="in-progress",
            parent="epic-y",
            affects=["pkg/c"],
            opened="2026-08-03",
        ),
    ]
    result = plan(
        items,
        "epic-y",
        auto_drive={**AUTO_DRIVE, "max_parallel": 3},
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert [d.slug for d in result.dispatches] == ["epic-y-a"]
    assert [(b.slug, b.kind) for b in result.blocked] == [
        ("epic-y-b", "worktree-pending"),
        ("epic-y-c", "worktree-pending"),
    ]


def test_plan_echoes_max_parallel_permission_mode_and_live() -> None:
    from work_io.orchestrate import plan

    items = [
        _item("live-item", kind="bug", phase="execute", status="in-progress", affects=["pkg/a"]),
        _item("b", kind="bug", phase="execute", status="in-progress", affects=["pkg/b"]),
    ]
    result = plan(
        items,
        "b",
        auto_drive={**AUTO_DRIVE, "max_parallel": 5},
        permission_mode="acceptEdits",
        live=("live-item#execute",),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert result.max_parallel == 5
    assert result.permission_mode == "acceptEdits"
    assert result.live == ("live-item#execute",)


def test_plan_is_deterministic() -> None:
    from work_io.orchestrate import plan

    items = [_item("a", kind="bug", phase="execute", status="in-progress", affects=["pkg/a"])]
    kwargs = dict(
        auto_drive=AUTO_DRIVE,
        permission_mode="bypassPermissions",
        live=(),
        worktree_exists={},
        workspace="/ws",
        default_base="develop",
    )
    assert plan(items, "a", **kwargs) == plan(items, "a", **kwargs)
