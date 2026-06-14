"""reconcile_doc_pointers.main: repoints stale work-item spec_doc/plan_doc."""

from __future__ import annotations

import sys
from pathlib import Path

from wiki_io.reconcile_doc_pointers import main


def _work_item(work_dir: Path, slug: str, spec_doc: str) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    md = work_dir / f"{slug}.md"
    md.write_text(
        f"---\ntitle: {slug}\nkind: feature\nstatus: resolved\nphase: done\nspec_doc: {spec_doc}\n---\n\nbody\n",
        encoding="utf-8",
    )
    return md


def test_main_repoints_archived_spec_doc(tmp_path: Path, monkeypatch) -> None:
    ws = tmp_path / "ws"
    (ws / "wiki" / "work").mkdir(parents=True)
    # Source already moved into _archive (raw/specs/<slug>.md is gone).
    archived = ws / "raw" / "_archive" / "specs" / "thing.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("spec\n", encoding="utf-8")
    item = _work_item(ws / "wiki" / "work", "thing", "raw/specs/thing.md")

    monkeypatch.setattr(sys, "argv", ["reconcile_doc_pointers", "--workspace", str(ws)])
    main()

    assert "spec_doc: raw/_archive/specs/thing.md" in item.read_text(encoding="utf-8")


def test_main_leaves_live_pointer_untouched(tmp_path: Path, monkeypatch) -> None:
    ws = tmp_path / "ws"
    (ws / "wiki" / "work").mkdir(parents=True)
    live = ws / "raw" / "specs" / "thing.md"  # source still present
    live.parent.mkdir(parents=True)
    live.write_text("spec\n", encoding="utf-8")
    item = _work_item(ws / "wiki" / "work", "thing", "raw/specs/thing.md")

    monkeypatch.setattr(sys, "argv", ["reconcile_doc_pointers", "--workspace", str(ws)])
    main()

    assert "spec_doc: raw/specs/thing.md" in item.read_text(encoding="utf-8")
