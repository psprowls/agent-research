"""Unit tests for scripts/fix_stale_spec_doc_pointers.py — the stale spec_doc sweep."""

import sys
from pathlib import Path

# Root pytest runs in --import-mode=importlib, which does NOT add the test file's
# directory to sys.path. Insert it so we can import the sibling script by name.
sys.path.insert(0, str(Path(__file__).parent))

from fix_stale_spec_doc_pointers import archived_target, sweep  # noqa: E402


def _make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "wiki" / "work" / "_archive").mkdir(parents=True)
    (ws / "raw" / "specs").mkdir(parents=True)
    (ws / "raw" / "_archive" / "specs").mkdir(parents=True)
    (ws / "raw" / "plans").mkdir(parents=True)
    return ws


def _work(ws: Path, subpath: str, body: str) -> Path:
    p = ws / "wiki" / "work" / subpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_rewrites_stale_archived_pointer(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    item = _work(ws, "_archive/x.md", "---\ntitle: X\nspec_doc: raw/specs/a.md\n---\nbody\n")
    report = sweep(ws, dry_run=False)
    assert report["rewrote"] == ["wiki/work/_archive/x.md -> raw/_archive/specs/a.md"]
    assert "spec_doc: raw/_archive/specs/a.md" in item.read_text(encoding="utf-8")


def test_idempotent_second_run_no_edits(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    _work(ws, "_archive/x.md", "---\ntitle: X\nspec_doc: raw/specs/a.md\n---\nbody\n")
    sweep(ws, dry_run=False)
    report2 = sweep(ws, dry_run=False)
    assert report2["rewrote"] == []
    assert report2["ok"] == ["wiki/work/_archive/x.md"]


def test_active_pointer_that_resolves_is_left_alone(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "specs" / "live.md").write_text("spec", encoding="utf-8")
    item = _work(ws, "live-item.md", "---\nspec_doc: raw/specs/live.md\n---\n")
    report = sweep(ws, dry_run=False)
    assert report["ok"] == ["wiki/work/live-item.md"]
    assert "spec_doc: raw/specs/live.md" in item.read_text(encoding="utf-8")


def test_plan_doc_and_body_mentions_untouched(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    body = (
        "---\n"
        "spec_doc: raw/specs/a.md\n"
        "plan_doc: raw/plans/a.md\n"
        "---\n"
        "Body mentions `spec_doc: raw/specs/a.md` and must not change.\n"
    )
    item = _work(ws, "_archive/y.md", body)
    sweep(ws, dry_run=False)
    text = item.read_text(encoding="utf-8")
    assert "plan_doc: raw/plans/a.md" in text  # plan_doc untouched
    assert "Body mentions `spec_doc: raw/specs/a.md`" in text  # body untouched
    assert "spec_doc: raw/_archive/specs/a.md" in text  # frontmatter rewritten


def test_missing_with_no_counterpart_is_unfixable(tmp_path):
    ws = _make_ws(tmp_path)
    item = _work(ws, "_archive/z.md", "---\nspec_doc: raw/specs/gone.md\n---\n")
    report = sweep(ws, dry_run=False)
    assert report["unfixable"] == ["wiki/work/_archive/z.md (spec_doc=raw/specs/gone.md)"]
    assert "spec_doc: raw/specs/gone.md" in item.read_text(encoding="utf-8")  # left as-is


def test_items_without_spec_doc_are_skipped(tmp_path):
    ws = _make_ws(tmp_path)
    no_key_body = "---\ntitle: No Pointer\nstatus: resolved\n---\nbody\n"
    no_fm_body = "# Just a heading\n\nsome text\n"
    no_key = _work(ws, "_archive/no-key.md", no_key_body)
    no_fm = _work(ws, "_archive/no-fm.md", no_fm_body)
    report = sweep(ws, dry_run=False)
    for bucket in ("rewrote", "ok", "unfixable"):
        joined = " ".join(report[bucket])
        assert "no-key.md" not in joined
        assert "no-fm.md" not in joined
    assert no_key.read_text(encoding="utf-8") == no_key_body  # unchanged on disk
    assert no_fm.read_text(encoding="utf-8") == no_fm_body  # unchanged on disk


def test_dry_run_does_not_write(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("spec", encoding="utf-8")
    item = _work(ws, "_archive/x.md", "---\nspec_doc: raw/specs/a.md\n---\n")
    report = sweep(ws, dry_run=True)
    assert report["rewrote"] == ["wiki/work/_archive/x.md -> raw/_archive/specs/a.md"]
    assert "spec_doc: raw/specs/a.md" in item.read_text(encoding="utf-8")  # unchanged on disk


def test_archived_target_helper(tmp_path):
    ws = _make_ws(tmp_path)
    (ws / "raw" / "_archive" / "specs" / "a.md").write_text("x", encoding="utf-8")
    assert archived_target(ws, "raw/specs/a.md") == "raw/_archive/specs/a.md"
    (ws / "raw" / "specs" / "b.md").write_text("x", encoding="utf-8")
    assert archived_target(ws, "raw/specs/b.md") is None  # resolves -> no rewrite
    assert archived_target(ws, "raw/specs/none.md") is None  # missing, no counterpart
