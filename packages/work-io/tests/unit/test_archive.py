from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from work_io.archive import TERMINAL_STATUSES, plan_archive


def _make_item(work_dir: Path, slug: str, status: str = "open", updated_days_ago: int = 0) -> None:
    opened = (date.today() - timedelta(days=updated_days_ago + 1)).isoformat()
    updated = (date.today() - timedelta(days=updated_days_ago)).isoformat()
    content = f"---\ntitle: {slug}\nstatus: {status}\nopened: {opened}\nupdated: {updated}\n---\n"
    (work_dir / f"{opened}-{slug}.md").write_text(content)


def test_sweep_mode_archives_terminal_aged_items(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "resolved-old", status="resolved", updated_days_ago=10)
    _make_item(work_dir, "open-item", status="open", updated_days_ago=10)

    plan = plan_archive(work_dir)

    assert len(plan.actions) == 1
    assert plan.actions[0].slug.endswith("resolved-old")
    assert len(plan.skipped) == 1
    assert plan.skipped[0]["slug"].endswith("open-item")


def test_sweep_mode_skips_terminal_under_min_age(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "resolved-new", status="resolved", updated_days_ago=3)

    plan = plan_archive(work_dir, min_age_days=7)

    assert len(plan.actions) == 0
    assert any("only 3 days old" in s["reason"] for s in plan.skipped)


def test_targeted_mode_bypasses_age_check(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "resolved-new", status="resolved", updated_days_ago=1)
    # Find the actual filename stem
    stems = [f.stem for f in work_dir.glob("*.md")]

    plan = plan_archive(work_dir, slugs=stems)

    assert len(plan.actions) == 1


def test_targeted_mode_non_terminal_goes_to_skipped(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "open-item", status="open", updated_days_ago=30)
    stems = [f.stem for f in work_dir.glob("*.md")]

    plan = plan_archive(work_dir, slugs=stems)

    assert len(plan.actions) == 0
    assert any("not terminal" in s["reason"] for s in plan.skipped)


def test_targeted_mode_missing_slug_goes_to_skipped(tmp_path: Path) -> None:
    work_dir = tmp_path

    plan = plan_archive(work_dir, slugs=["2026-01-01-nonexistent"])

    assert len(plan.actions) == 0
    assert plan.skipped[0]["slug"] == "2026-01-01-nonexistent"
    assert "not found" in plan.skipped[0]["reason"]


def test_archive_dst_is_archive_subdir(tmp_path: Path) -> None:
    work_dir = tmp_path
    _make_item(work_dir, "wontfix-item", status="wontfix", updated_days_ago=8)

    plan = plan_archive(work_dir)

    assert len(plan.actions) == 1
    assert plan.actions[0].dst.parent.name == "archived"
    assert plan.actions[0].dst.name == plan.actions[0].src.name


def test_all_terminal_statuses_eligible(tmp_path: Path) -> None:
    work_dir = tmp_path
    for status in TERMINAL_STATUSES:
        _make_item(work_dir, f"item-{status}", status=status, updated_days_ago=10)

    plan = plan_archive(work_dir)
    assert len(plan.actions) == len(TERMINAL_STATUSES)
