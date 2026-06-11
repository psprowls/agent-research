from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace, wiki). Creates wiki/work/ structure."""
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    (wiki / "work").mkdir(parents=True)
    return workspace, wiki


def _write_item(
    work_dir: Path, name: str, status: str = "open", kind: str = "bug", body: str = "## Summary\ncontent\n", **extra_fm
) -> str:
    """Write a work item; returns the slug (file stem, date-prefixed like real items)."""
    opened = (date.today() - timedelta(days=1)).isoformat()
    fm_lines = [
        "---",
        f"title: {name}",
        f"status: {status}",
        f"kind: {kind}",
        f"opened: {opened}",
        f"updated: {date.today().isoformat()}",
    ]
    for k, v in extra_fm.items():
        fm_lines.append(f"{k}: {v}")
    slug = f"{opened}-{name}"
    (work_dir / f"{slug}.md").write_text("\n".join(fm_lines) + "\n---\n\n" + body)
    return slug


# --- run_work_next ---


def test_next_fresh_bug_routes_to_systematic_debugging(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "fix-login-timeout", kind="bug")

    result = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))

    assert result.blockers == []
    assert result.action == {"skill": "systematic-debugging", "reason": "bug entering the pipeline at design"}
    assert result.phase == "design"
    assert result.artifact == {"path": str(workspace / "raw" / "specs" / f"{slug}.md")}
    assert result.on_dispatch == {"phase": "design", "status": "open", "requires": []}
    assert result.on_complete == {"phase": "plan-or-execute", "status": "open", "requires": ["effort"]}


def test_next_unknown_slug_blocks(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, _wiki = _make_workspace(tmp_path)

    result = asyncio.run(run_work_next(workspace_path=workspace, slug="no-such-item"))

    assert result.action is None
    assert result.blockers


def test_next_terminal_item_blocks(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "old-bug", status="resolved", resolved_in="pr#9")

    result = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))

    assert result.action is None
    assert result.blockers


def test_next_execute_with_plan_doc_carries_dispatch_transition(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work",
        "feat",
        kind="feature",
        status="accepted",
        phase="execute",
        plan_doc="raw/plans/feat.md",
        body="## Plan\n\n| Action | Done when | Rationale |\n| --- | --- | --- |\n| x | y | z |\n",
    )

    result = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))

    assert result.action["skill"] == "subagent-driven-development"
    assert result.phase == "execute"
    assert result.on_dispatch == {"phase": None, "status": "in-progress", "requires": ["owner"]}
    assert result.artifact is None


def test_next_broken_yaml_frontmatter_blocks(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = "2026-06-08-broken-yaml"
    (wiki / "work" / f"{slug}.md").write_text("---\ntitle: broken\nbad: [unclosed\n---\n\n## Summary\ncontent\n")

    result = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))

    assert result.action is None
    assert result.blockers


def test_lint_passes_workspace_root_for_artifact_rule(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_lint

    workspace, wiki = _make_workspace(tmp_path)
    _write_item(wiki / "work", "with-ghost-spec", spec_doc="raw/specs/ghost.md")

    result = asyncio.run(run_work_lint(workspace_path=workspace))

    assert "artifact-doc-missing" in {f["rule_id"] for f in result.findings}


# --- run_work_advance ---


def _read_fm(wiki: Path, slug: str) -> dict:
    from work_io import frontmatter

    fm, _body = frontmatter.parse((wiki / "work" / f"{slug}.md").read_text())
    return fm


def test_advance_fresh_feature_enters_design(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "new-feature", kind="feature")

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "design"
    assert fm["status"] == "open"
    assert fm["updated"] == date.today().isoformat()  # `date` imported at module top
    assert result.phase == "design"
    assert result.applied["phase"] == [None, "design"]
    assert (wiki / "work-index.json").exists()  # sidecar regenerated


def test_advance_design_complete_without_effort_errors(tmp_path: Path) -> None:
    import asyncio

    import pytest
    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "sized-later", kind="bug", phase="design")

    with pytest.raises(ValueError, match="effort"):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_advance_design_complete_small_bug_shortcuts_to_execute(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "small-bug", kind="bug", phase="design")
    (workspace / "raw" / "specs").mkdir(parents=True)
    (workspace / "raw" / "specs" / f"{slug}.md").write_text("# findings\n")

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, effort="small"))

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "execute"
    assert fm["status"] == "open"  # shortcut skips accepted
    assert fm["effort"] == "small"
    assert fm["spec_doc"] == f"raw/specs/{slug}.md"
    assert result.stamped["spec_doc"] == f"raw/specs/{slug}.md"


def test_advance_plan_complete_sets_accepted_and_syncs_plan_table(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance
    from work_io import frontmatter, plan_table

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "big-feature", kind="feature", phase="plan")
    (workspace / "raw" / "plans").mkdir(parents=True)
    (workspace / "raw" / "plans" / f"{slug}.md").write_text("# plan\n")

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))

    fm, body = frontmatter.parse((wiki / "work" / f"{slug}.md").read_text())
    assert fm["status"] == "accepted"
    assert fm["phase"] == "execute"
    assert fm["plan_doc"] == f"raw/plans/{slug}.md"
    parsed = plan_table.parse_plan(body)
    assert parsed.state == "ok"  # rule 4 passes by construction
    assert any(f"raw/plans/{slug}.md" in row["action"] for row in parsed.rows)
    assert "accepted-without-plan" not in {f["rule_id"] for f in result.findings}


def test_advance_execute_dispatch_requires_owner(tmp_path: Path) -> None:
    import asyncio

    import pytest
    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "exec-me", kind="bug", phase="execute", effort="small")

    with pytest.raises(ValueError, match="owner"):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_advance_execute_dispatch_sets_in_progress(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "exec-me", kind="bug", phase="execute", effort="small")

    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, owner="pat"))

    fm = _read_fm(wiki, slug)
    assert fm["status"] == "in-progress"
    assert fm["owner"] == "pat"
    assert fm["phase"] == "execute"  # phase unchanged by the dispatch transition


def test_advance_execute_complete_moves_to_finish(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work", "executing", kind="bug", status="in-progress", phase="execute", effort="small", owner="pat"
    )

    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "finish"
    assert fm["status"] == "in-progress"


def test_advance_finish_requires_resolved_in(tmp_path: Path) -> None:
    import asyncio

    import pytest
    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work", "finishing", kind="bug", status="in-progress", phase="finish", effort="small", owner="pat"
    )

    with pytest.raises(ValueError, match="resolved"):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_advance_finish_complete_resolves(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work", "finishing", kind="bug", status="in-progress", phase="finish", effort="small", owner="pat"
    )

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, resolved_in="pr#42"))

    fm = _read_fm(wiki, slug)
    assert fm["status"] == "resolved"
    assert fm["phase"] == "done"
    assert fm["resolved_in"] == "pr#42"
    assert result.status == "resolved"


def test_advance_terminal_item_errors(tmp_path: Path) -> None:
    import asyncio

    import pytest
    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "done-item", kind="bug", status="resolved", resolved_in="pr#1")

    with pytest.raises(ValueError):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_full_feature_pipeline_walk(tmp_path: Path) -> None:
    """open/no-phase -> design -> plan -> execute(accepted) -> in-progress -> finish -> done."""
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance, run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "walk", kind="feature")
    (workspace / "raw" / "specs").mkdir(parents=True)
    (workspace / "raw" / "specs" / f"{slug}.md").write_text("# spec\n")
    (workspace / "raw" / "plans").mkdir(parents=True)
    (workspace / "raw" / "plans" / f"{slug}.md").write_text("# plan\n")

    def next_skill() -> str | None:
        r = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))
        return r.action["skill"] if r.action else None

    assert next_skill() == "brainstorming"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # -> design
    assert next_skill() == "brainstorming"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # design done -> plan
    assert next_skill() == "writing-plans"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # plan done -> execute/accepted
    assert next_skill() == "subagent-driven-development"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, owner="pat"))  # dispatch -> in-progress
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # execute done -> finish
    assert next_skill() == "finishing-a-development-branch"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, resolved_in="pr#7"))  # -> done

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "done"
    assert fm["status"] == "resolved"


def test_advance_with_bystander_item_succeeds_and_scopes_findings(tmp_path: Path) -> None:
    """A hand-edited bystander with unquoted YAML dates (parsed as datetime.date)
    and its own lint issue must not crash the post-write lint, and its findings
    must not leak into the advanced item's result."""
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "advance-me", kind="feature")
    # _write_item emits unquoted `opened:`/`updated:` dates — YAML parses them
    # as datetime.date. The bystander is never re-written, so its dates stay
    # date objects through the post-advance lint. Its ghost spec_doc produces
    # an artifact-doc-missing finding of its own.
    bystander = _write_item(wiki / "work", "bystander", kind="bug", spec_doc="raw/specs/ghost.md")

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))

    assert result.phase == "design"
    assert all(f["slug"] == slug for f in result.findings)
    assert bystander not in {f["slug"] for f in result.findings}
