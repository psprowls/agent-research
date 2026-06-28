"""Tests for the pure guidance-archive planner."""

from __future__ import annotations

from pathlib import Path

from guidance_io.archive import plan_guidance_archive


def _write_page(wiki: Path, topic: str, slug: str, body: str = "x") -> Path:
    p = wiki / "guidance" / topic / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {slug}\ntopic: {topic}\n---\n\n{body}\n", encoding="utf-8")
    return p


def test_resolves_valid_token_to_archive_dst(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write_page(wiki, "python", "old-pattern")

    plan = plan_guidance_archive(wiki, ["python/old-pattern"])

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.slug == "python/old-pattern"
    assert action.src == wiki / "guidance" / "python" / "old-pattern.md"
    assert action.dst == wiki / "guidance" / "python" / "_archive" / "old-pattern.md"
    assert plan.skipped == []


def test_skips_unqualified_token(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write_page(wiki, "python", "old-pattern")

    plan = plan_guidance_archive(wiki, ["old-pattern"])

    assert plan.actions == []
    assert len(plan.skipped) == 1
    assert plan.skipped[0]["slug"] == "old-pattern"
    assert "unqualified" in plan.skipped[0]["reason"]


def test_skips_missing_file(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"

    plan = plan_guidance_archive(wiki, ["python/nope"])

    assert plan.actions == []
    assert len(plan.skipped) == 1
    assert "not found" in plan.skipped[0]["reason"]


def test_malformed_page_does_not_abort_plan(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    # Unreadable page: a directory where a file is expected would raise on read;
    # instead simulate a malformed page that still resolves as a path.
    bad = wiki / "guidance" / "python" / "broken.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\nnot: [valid: yaml\n---\n", encoding="utf-8")
    _write_page(wiki, "python", "good")

    plan = plan_guidance_archive(wiki, ["python/broken", "python/good"])

    # The good slug is still planned regardless of the malformed sibling.
    assert any(a.slug == "python/good" for a in plan.actions)


def test_multiple_slugs(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write_page(wiki, "python", "a")
    _write_page(wiki, "rust", "b")

    plan = plan_guidance_archive(wiki, ["python/a", "rust/b"])

    assert {a.slug for a in plan.actions} == {"python/a", "rust/b"}
