"""Unit tests for work_io.doc_pointers.sweep (stale spec_doc/plan_doc repair)."""

from __future__ import annotations

from pathlib import Path

from work_io.doc_pointers import sweep


def _ws(tmp_path: Path) -> Path:
    """Lay out an empty workspace: wiki/work + raw/{specs,plans,_archive/...}."""
    (tmp_path / "wiki" / "work").mkdir(parents=True)
    (tmp_path / "raw" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "plans").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "_archive" / "plans").mkdir(parents=True)
    return tmp_path


def _work_item(ws: Path, slug: str, **fm: str) -> Path:
    lines = "\n".join(f"{k}: {v}" for k, v in fm.items())
    md = ws / "wiki" / "work" / f"{slug}.md"
    md.write_text(f"---\n{lines}\n---\n\nbody\n", encoding="utf-8")
    return md


def test_spec_doc_stale_rewritten_to_archive(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("spec", encoding="utf-8")
    md = _work_item(ws, "2026-01-01-foo", status="resolved", spec_doc="raw/specs/foo.md")

    report = sweep(ws, dry_run=False)

    assert "spec_doc: raw/_archive/specs/foo.md" in md.read_text(encoding="utf-8")
    assert report.rewrote == ["wiki/work/2026-01-01-foo.md (spec_doc) -> raw/_archive/specs/foo.md"]
    assert report.ok == []
    assert report.unfixable == []


def test_plan_doc_stale_rewritten_to_archive(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "plans" / "bar.md").write_text("plan", encoding="utf-8")
    md = _work_item(ws, "2026-01-02-bar", status="resolved", plan_doc="raw/plans/bar.md")

    report = sweep(ws, dry_run=False)

    assert "plan_doc: raw/_archive/plans/bar.md" in md.read_text(encoding="utf-8")
    assert report.rewrote == ["wiki/work/2026-01-02-bar.md (plan_doc) -> raw/_archive/plans/bar.md"]


def test_both_pointers_stale_rewritten_in_one_pass(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "baz.md").write_text("s", encoding="utf-8")
    (ws / "raw" / "_archive" / "plans" / "baz.md").write_text("p", encoding="utf-8")
    md = _work_item(
        ws,
        "2026-01-03-baz",
        status="resolved",
        spec_doc="raw/specs/baz.md",
        plan_doc="raw/plans/baz.md",
    )

    report = sweep(ws, dry_run=False)

    text = md.read_text(encoding="utf-8")
    assert "spec_doc: raw/_archive/specs/baz.md" in text
    assert "plan_doc: raw/_archive/plans/baz.md" in text
    assert len(report.rewrote) == 2


def test_pointer_that_resolves_left_untouched(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "specs" / "live.md").write_text("s", encoding="utf-8")
    md = _work_item(ws, "2026-01-04-live", status="in_progress", spec_doc="raw/specs/live.md")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []
    assert report.ok == ["wiki/work/2026-01-04-live.md (spec_doc)"]


def test_missing_with_no_counterpart_unfixable(tmp_path):
    ws = _ws(tmp_path)
    md = _work_item(ws, "2026-01-05-gone", status="resolved", spec_doc="raw/specs/gone.md")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []
    assert report.unfixable == ["wiki/work/2026-01-05-gone.md (spec_doc=raw/specs/gone.md)"]


def test_dry_run_reports_without_writing(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    md = _work_item(ws, "2026-01-06-foo", status="resolved", spec_doc="raw/specs/foo.md")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=True)

    assert md.read_text(encoding="utf-8") == before
    assert len(report.rewrote) == 1


def test_idempotent_second_run_zero_rewrites(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    _work_item(ws, "2026-01-07-foo", status="resolved", spec_doc="raw/specs/foo.md")

    sweep(ws, dry_run=False)
    report2 = sweep(ws, dry_run=False)

    assert report2.rewrote == []
    assert report2.ok == ["wiki/work/2026-01-07-foo.md (spec_doc)"]


def test_body_mention_and_missing_key_not_matched(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    md = ws / "wiki" / "work" / "2026-01-08-doc.md"
    md.write_text(
        "---\nstatus: resolved\n---\n\nWe set `- spec_doc: raw/specs/foo.md` in the body.\n",
        encoding="utf-8",
    )
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []


def test_index_md_skipped(tmp_path):
    ws = _ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "foo.md").write_text("s", encoding="utf-8")
    md = ws / "wiki" / "work" / "index.md"
    md.write_text("---\nspec_doc: raw/specs/foo.md\n---\n", encoding="utf-8")
    before = md.read_text(encoding="utf-8")

    report = sweep(ws, dry_run=False)

    assert md.read_text(encoding="utf-8") == before
    assert report.rewrote == []
