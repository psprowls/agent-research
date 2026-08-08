from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    (wiki / "work").mkdir(parents=True)
    return workspace, wiki


def _write_item(
    work_dir: Path, name: str, status: str = "open", kind: str = "bug", body: str = "## Summary\ncontent\n", **extra_fm
) -> str:
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


def test_orchestrate_fails_loud_on_invalid_auto_drive_enum(tmp_path: Path) -> None:
    # workspace_io.manifest's structural read() only checks match values are
    # non-empty strings — it can't import work-io's phase enum (see manifest.py's
    # _validate_auto_drive docstring). A bogus phase value passes that structural
    # check and must be caught by run_work_orchestrate's own validate_auto_drive()
    # call — this is exactly the "hand-edited manifest bypasses gw config set"
    # case the design spec calls out.
    from graph_wiki_core.commands.orchestrate import run_work_orchestrate

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "fix-x", kind="bug", status="in-progress", phase="execute")
    manifest_path = workspace / ".graph-wiki.yaml"
    manifest_path.write_text(
        "version: 2\n"
        "workflow:\n"
        "  auto_drive:\n"
        "    overrides:\n"
        "      - match: {phase: bogus-phase}\n"
        "        model: claude-sonnet-5\n"
    )

    import pytest

    with pytest.raises(RuntimeError, match="workflow.auto_drive"):
        asyncio.run(run_work_orchestrate(workspace_path=workspace, slug=slug))


def test_orchestrate_dispatches_ready_epic_children(tmp_path: Path) -> None:
    from graph_wiki_core.commands.orchestrate import run_work_orchestrate

    workspace, wiki = _make_workspace(tmp_path)
    epic = _write_item(wiki / "work", "epic-x", kind="epic", status="accepted", phase="execute")
    _write_item(
        wiki / "work",
        "epic-x-a",
        kind="bug",
        status="in-progress",
        phase="execute",
        parent=epic,
        affects="[pkg/a]",
    )

    result = asyncio.run(run_work_orchestrate(workspace_path=workspace, slug=epic))

    assert result.terminal is False
    assert len(result.dispatches) == 1
    assert result.dispatches[0]["slug"].endswith("epic-x-a")
    assert result.dispatches[0]["worktree"]["action"] == "create-top-level"


def test_orchestrate_default_base_degrades_without_git(tmp_path: Path) -> None:
    from graph_wiki_core.commands.orchestrate import _default_base

    assert _default_base(None) == "develop"
    assert _default_base(tmp_path / "not-a-repo") == "develop"


def test_orchestrate_archived_dependency_counts_as_met(tmp_path: Path) -> None:
    from graph_wiki_core.commands.orchestrate import run_work_orchestrate

    workspace, wiki = _make_workspace(tmp_path)
    (wiki / "work" / "_archive").mkdir()
    dep_slug = "2026-07-01-old-dep"
    archive_content = (
        "---\n"
        "title: old dep\n"
        "status: resolved\n"
        "kind: bug\n"
        "opened: 2026-07-01\n"
        "updated: 2026-07-01\n"
        "---\n\n"
        "## Summary\nx\n"
    )
    (wiki / "work" / "_archive" / f"{dep_slug}.md").write_text(archive_content)
    slug = _write_item(
        wiki / "work",
        "needs-dep",
        kind="bug",
        status="in-progress",
        phase="execute",
        depends_on=f"[{dep_slug}]",
        affects="[pkg/a]",
    )

    result = asyncio.run(run_work_orchestrate(workspace_path=workspace, slug=slug))

    assert len(result.dispatches) == 1
