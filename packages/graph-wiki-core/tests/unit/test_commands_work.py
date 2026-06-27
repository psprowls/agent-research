from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from pathlib import Path

import pytest


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
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=0, resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=True))

    assert result.dry_run is True
    assert len(result.moved) == 1
    assert not (work_dir / "_archive").exists()


def test_run_work_archive_executes_move(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_item(work_dir, "resolved-item", status="resolved", updated_days_ago=0, resolved_in="pr#1")

    result = asyncio.run(run_work_archive(workspace_path=workspace, dry_run=False))

    assert len(result.moved) == 1
    assert (work_dir / "_archive").exists()


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


def test_run_work_file_emits_full_schema_frontmatter(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_file
    from work_io import frontmatter as _frontmatter

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(
        run_work_file(
            workspace_path=workspace,
            title="Migrate the thing",
            kind="tech-debt",
            summary="Rewrite the thing",
            affects=["packages/foo", "packages/bar"],
            effort="small",
            blast_radius="package",
            tags=["cli", "refactor"],
        )
    )

    page = wiki / result.page_path
    fm, _body = _frontmatter.parse(page.read_text(encoding="utf-8"))
    assert fm["category"] == "work"
    assert fm["kind"] == "tech-debt"
    assert fm["effort"] == "small"
    assert fm["blast_radius"] == "package"
    assert fm["affects"] == ["packages/foo", "packages/bar"]
    assert fm["tags"] == ["cli", "refactor"]
    # Unset optional scalars are omitted, not emitted as null placeholders.
    assert "severity" not in fm
    assert "owner" not in fm


def test_run_work_file_omits_optional_scalars_when_unset(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_file
    from work_io import frontmatter as _frontmatter

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(
        run_work_file(
            workspace_path=workspace,
            title="Minimal item",
            kind="bug",
            summary="Just the basics",
        )
    )

    page = wiki / result.page_path
    fm, _body = _frontmatter.parse(page.read_text(encoding="utf-8"))
    assert fm["affects"] == []
    assert fm["tags"] == []
    for k in ("severity", "effort", "blast_radius", "target", "owner"):
        assert k not in fm


def test_run_work_file_writes_parseable_plan_table(tmp_path: Path) -> None:
    """A freshly filed item's body carries the scaffolding sections and an
    (empty) ## Plan table — not the one-line stub."""
    import asyncio

    from graph_wiki_core.commands.work import run_work_file
    from work_io import frontmatter as _frontmatter
    from work_io.plan_table import parse_plan

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(
        run_work_file(
            workspace_path=workspace,
            title="Scaffolded bug",
            kind="bug",
            summary="Something is broken",
        )
    )

    page = wiki / result.page_path
    _fm, body = _frontmatter.parse(page.read_text(encoding="utf-8"))
    assert "## Summary" in body
    assert "## Notes / log" in body
    assert parse_plan(body).state == "empty"


def test_run_work_file_item_passes_accepted_without_plan(tmp_path: Path) -> None:
    """A filed item promoted to accepted does not trip lint rule 4
    (accepted-without-plan) — the real downstream contract."""
    import asyncio

    from graph_wiki_core.commands.work import run_work_file
    from work_io import frontmatter as _frontmatter
    from work_io.lifecycle_lint import run_lint
    from work_io.plan_table import parse_plan

    workspace, wiki = _make_workspace(tmp_path)

    result = asyncio.run(
        run_work_file(
            workspace_path=workspace,
            title="Accepted bug",
            kind="bug",
            summary="Something is broken",
        )
    )

    page = wiki / result.page_path
    fm, body = _frontmatter.parse(page.read_text(encoding="utf-8"))
    fm["status"] = "accepted"
    item = {"slug": "accepted-bug", "fm": fm, "plan": parse_plan(body)}
    findings = run_lint([item], None, None)
    assert "accepted-without-plan" not in {f.rule_id for f in findings}


def test_run_work_file_best_effort_skips_missing_index_and_log(tmp_path: Path) -> None:
    """Filing into a wiki with no index.md/log.md still writes page + sidecar."""
    import asyncio

    from graph_wiki_core.commands.work import run_work_file

    workspace, wiki = _make_workspace(tmp_path)  # no index.md / log.md

    result = asyncio.run(
        run_work_file(
            workspace_path=workspace,
            title="No bootstrap item",
            kind="bug",
            summary="Filed against an un-bootstrapped wiki",
        )
    )

    assert result.status == "ok"
    assert (wiki / result.page_path).exists()
    # Sidecar regen runs regardless of bootstrap state.
    assert (wiki / "work-index.json").exists()


def test_run_work_file_updates_index_and_log_when_present(tmp_path: Path) -> None:
    """When index.md + log.md exist, run_work_file invokes both (the file path
    gains the side-effects the ingest path already had)."""
    import asyncio
    from unittest.mock import patch

    from graph_wiki_core.commands.work import run_work_file

    workspace, wiki = _make_workspace(tmp_path)
    (wiki / "index.md").write_text("", encoding="utf-8")
    (wiki / "log.md").write_text("", encoding="utf-8")

    with (
        patch("graph_wiki_core.commands.work.update_index") as mock_ui,
        patch("graph_wiki_core.commands.work.append_log") as mock_al,
    ):
        result = asyncio.run(
            run_work_file(
                workspace_path=workspace,
                title="Bootstrapped item",
                kind="task",
                summary="Filed against a bootstrapped wiki",
            )
        )

    assert result.status == "ok"
    mock_ui.assert_called_once_with(wiki)
    mock_al.assert_called_once()
    call = mock_al.call_args
    assert call.args[0] == wiki
    assert call.args[1] == "create"
    assert call.args[2] == "Bootstrapped item"
    assert "work/" in call.kwargs.get("detail", "")


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


# ---------------------------------------------------------------------------
# test_run_work_archive_repoints_stale_doc_pointer (backstop)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_work_archive_repoints_stale_doc_pointer(tmp_path: Path) -> None:
    """The archive backstop repoints a stale spec_doc whose source was archived."""
    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    (workspace / "raw" / "_archive" / "specs").mkdir(parents=True)
    (workspace / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")

    # An in-progress item (NOT terminal — so it is repointed but not moved).
    work_item = wiki / "work" / "2026-01-01-foo.md"
    work_item.write_text(
        "---\nstatus: in_progress\nspec_doc: raw/specs/foo.md\n---\n\nbody\n",
        encoding="utf-8",
    )

    result = await run_work_archive(workspace_path=workspace, dry_run=False)

    assert "spec_doc: raw/_archive/specs/foo.md" in work_item.read_text(encoding="utf-8")
    assert result.repointed == ["wiki/work/2026-01-01-foo.md (spec_doc) -> raw/_archive/specs/foo.md"]


@pytest.mark.asyncio
async def test_run_work_archive_dry_run_does_not_write_repoint(tmp_path: Path) -> None:
    """dry_run reports the would-be repoint but leaves the work item untouched."""
    from graph_wiki_core.commands.work import run_work_archive

    workspace, wiki = _make_workspace(tmp_path)
    (workspace / "raw" / "_archive" / "specs").mkdir(parents=True)
    (workspace / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")

    work_item = wiki / "work" / "2026-01-01-foo.md"
    work_item.write_text(
        "---\nstatus: in_progress\nspec_doc: raw/specs/foo.md\n---\n\nbody\n",
        encoding="utf-8",
    )
    before = work_item.read_text(encoding="utf-8")

    result = await run_work_archive(workspace_path=workspace, dry_run=True)

    assert work_item.read_text(encoding="utf-8") == before
    assert len(result.repointed) == 1


# ---------------------------------------------------------------------------
# run_work_next: epic/dep hierarchy gates (live scan population)
# ---------------------------------------------------------------------------


def _write_hierarchy_item(
    work_dir: Path,
    slug: str,
    *,
    kind: str,
    status: str,
    phase: str | None = None,
    parent: str | None = None,
    depends_on: list[str] | None = None,
    plan_doc: str | None = None,
) -> None:
    """Write wiki/work/<slug>.md with hierarchy frontmatter (filename == slug)."""
    lines = ["---", f"title: {slug}", f"kind: {kind}", f"status: {status}"]
    if phase:
        lines.append(f"phase: {phase}")
    if parent:
        lines.append(f"parent: {parent}")
    if depends_on:
        lines.append("depends_on:")
        lines += [f"- {d}" for d in depends_on]
    if plan_doc:
        lines.append(f"plan_doc: {plan_doc}")
    lines += ["opened: 2026-06-26", "updated: 2026-06-26", "---", "body", ""]
    (work_dir / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")


def test_epic_execute_all_terminal_satisfied_gate(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_hierarchy_item(work_dir, "epic-x", kind="epic", status="accepted", phase="execute")
    _write_hierarchy_item(work_dir, "child-a", kind="bug", status="resolved", parent="epic-x")
    _write_hierarchy_item(work_dir, "child-b", kind="bug", status="wontfix", parent="epic-x")

    result = asyncio.run(run_work_next(workspace_path=workspace, slug="epic-x"))

    assert result.action is None
    assert result.blockers == []
    assert result.on_complete is not None
    assert result.on_complete["phase"] == "finish"
    assert result.child_rollup == {"total": 2, "terminal": 2, "open_slugs": []}


def test_epic_execute_partial_waits(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_hierarchy_item(work_dir, "epic-x", kind="epic", status="accepted", phase="execute")
    _write_hierarchy_item(work_dir, "child-a", kind="bug", status="resolved", parent="epic-x")
    _write_hierarchy_item(work_dir, "child-b", kind="bug", status="open", parent="epic-x")

    result = asyncio.run(run_work_next(workspace_path=workspace, slug="epic-x"))

    assert result.action is None
    assert any("child-b" in b for b in result.blockers)
    assert result.child_rollup == {"total": 2, "terminal": 1, "open_slugs": ["child-b"]}


def test_child_with_unmet_dep_blocks(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    work_dir = wiki / "work"
    _write_hierarchy_item(work_dir, "child-a", kind="bug", status="open")
    _write_hierarchy_item(work_dir, "child-b", kind="bug", status="open", depends_on=["child-a"])

    result = asyncio.run(run_work_next(workspace_path=workspace, slug="child-b"))

    assert any("child-a" in b for b in result.blockers)
