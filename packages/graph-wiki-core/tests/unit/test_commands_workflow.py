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
