from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from pathlib import Path


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace, wiki). Creates wiki/work/ structure."""
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    work_dir = wiki / "work"
    work_dir.mkdir(parents=True)
    return workspace, wiki


def _write_item(
    work_dir: Path, slug: str, status: str = "open", kind: str = "bug", updated_days_ago: int = 0, **extra_fm
) -> None:
    opened = (date.today() - timedelta(days=updated_days_ago + 1)).isoformat()
    updated = (date.today() - timedelta(days=updated_days_ago)).isoformat()
    fm_lines = [
        "---",
        f"title: {slug}",
        f"status: {status}",
        f"kind: {kind}",
        f"opened: {opened}",
        f"updated: {updated}",
    ]
    for k, v in extra_fm.items():
        fm_lines.append(f"{k}: {v}")
    fm_lines += ["---", "", "## Summary", "content", ""]
    (work_dir / f"{opened}-{slug}.md").write_text("\n".join(fm_lines))


def test_run_work_regen_index_creates_sidecar(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_regen_index

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "bug-1", status="open")

    result = asyncio.run(run_work_regen_index(workspace_path=workspace))

    assert result.item_count == 1
    assert (wiki / "work-index.json").exists()


def test_run_work_regen_index_idempotent(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_regen_index

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "bug-1")

    asyncio.run(run_work_regen_index(workspace_path=workspace))
    result = asyncio.run(run_work_regen_index(workspace_path=workspace))

    assert result.item_count == 1


def test_run_work_lint_returns_findings(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_lint

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "bad-item", status="open", updated_days_ago=40)

    result = asyncio.run(run_work_lint(workspace_path=workspace))

    assert result.total_items == 1
    rule_ids = {f["rule_id"] for f in result.findings}
    assert "stuck-open" in rule_ids
    assert "sidecar-missing" in rule_ids


def test_run_work_status_missing_sidecar(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_status

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(run_work_status(workspace_path=workspace))

    assert result.sidecar_missing is True


def test_run_work_status_with_sidecar(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_regen_index, run_work_status

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "in-prog", status="in-progress", owner="pat")
    _write_item(work_dir, "stuck", status="open", updated_days_ago=35)

    asyncio.run(run_work_regen_index(workspace_path=workspace))
    result = asyncio.run(run_work_status(workspace_path=workspace))

    assert result.sidecar_missing is False
    assert len(result.in_flight) == 1
    assert len(result.stuck) >= 1


def test_run_work_archive_dry_run(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=10, resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=True))

    assert result.dry_run is True
    assert len(result.moved) == 1
    assert not (wiki / "work" / "archived").exists()


def test_run_work_archive_executes_move(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=10, resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=False))

    assert len(result.moved) == 1
    assert (work_dir / "archived").exists()


def test_run_work_file_returns_ingest_result(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_file

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(
        run_work_file(
            workspace_path=workspace,
            title="Test bug",
            kind="bug",
            summary="Something is broken",
            affects=["packages/foo"],
        )
    )

    assert result.status == "ok"
    assert "work" in result.page_path


def test_work_result_dataclasses_importable() -> None:
    from graph_wiki_core.commands.work import (
        WorkArchiveResult,
        WorkLintResult,
        WorkRegenResult,
        WorkStatusResult,
    )

    assert dataclasses.is_dataclass(WorkLintResult)
    assert dataclasses.is_dataclass(WorkArchiveResult)
    assert dataclasses.is_dataclass(WorkStatusResult)
    assert dataclasses.is_dataclass(WorkRegenResult)
