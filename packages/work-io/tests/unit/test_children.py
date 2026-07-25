from __future__ import annotations

from pathlib import Path

from work_io.children import refresh_children
from work_io.frontmatter import parse


def _write(work_dir: Path, slug: str, kind: str = "feature", parent: str | None = None, **extra) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"title: {slug}",
        f"kind: {kind}",
        "status: open",
        "affects: []",
    ]
    if parent:
        lines.append(f"parent: {parent}")
    for k, v in extra.items():
        lines.append(f"{k}: {v}")
    lines += ["opened: '2026-07-01'", "updated: '2026-07-01'", "---", "", "## Summary", "body text", ""]
    path = work_dir / f"{slug}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_refresh_writes_children_after_affects(tmp_path: Path) -> None:
    work = tmp_path / "work"
    parent_page = _write(work, "p")
    _write(work, "c1", kind="bug", parent="p")

    assert refresh_children(work) == ["p"]
    fm, body = parse(parent_page.read_text(encoding="utf-8"))
    assert fm["children"] == ["c1"]
    keys = list(fm)
    assert keys.index("children") == keys.index("affects") + 1
    assert "body text" in body


def test_refresh_is_idempotent(tmp_path: Path) -> None:
    work = tmp_path / "work"
    _write(work, "p")
    _write(work, "c1", kind="bug", parent="p")
    refresh_children(work)
    assert refresh_children(work) == []


def test_refresh_overwrites_hand_edits_and_removes_empty(tmp_path: Path) -> None:
    work = tmp_path / "work"
    page = _write(work, "p", children="[ghost]")
    assert refresh_children(work) == ["p"]
    fm, _ = parse(page.read_text(encoding="utf-8"))
    assert "children" not in fm


def test_refresh_counts_archived_children_but_freezes_archived_parents(tmp_path: Path) -> None:
    work = tmp_path / "work"
    parent_page = _write(work, "p")
    archived_parent = _write(work / "_archive", "old-p", children="[stale]")
    _write(work / "_archive", "done-c", kind="bug", parent="p")

    assert refresh_children(work) == ["p"]
    fm, _ = parse(parent_page.read_text(encoding="utf-8"))
    assert fm["children"] == ["done-c"]
    fm_arch, _ = parse(archived_parent.read_text(encoding="utf-8"))
    assert fm_arch["children"] == ["stale"]  # archived pages are frozen


def test_refresh_preserves_human_keys(tmp_path: Path) -> None:
    work = tmp_path / "work"
    page = _write(work, "p", owner="pat", notes="keep me")
    _write(work, "c1", kind="bug", parent="p")
    refresh_children(work)
    fm, _ = parse(page.read_text(encoding="utf-8"))
    assert fm["owner"] == "pat" and fm["notes"] == "keep me"


def test_refresh_inserts_after_positionally_last_anchor(tmp_path: Path) -> None:
    """affects/parent/depends_on all present, in that order: depends_on is last."""
    work = tmp_path / "work"
    work.mkdir(parents=True)
    parent_page = work / "p.md"
    parent_page.write_text(
        "---\n"
        "title: p\n"
        "kind: feature\n"
        "status: open\n"
        "affects: []\n"
        "parent: q\n"
        "depends_on: []\n"
        "opened: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n\n"
        "## Summary\nbody text\n",
        encoding="utf-8",
    )
    _write(work, "c1", kind="bug", parent="p")

    assert refresh_children(work) == ["p"]
    fm, _ = parse(parent_page.read_text(encoding="utf-8"))
    keys = list(fm)
    assert keys.index("children") == keys.index("depends_on") + 1


def test_refresh_preserves_formatting_of_other_keys(tmp_path: Path) -> None:
    """Flow-style tags and an indented block-style affects list survive untouched.

    Only the children lines are added; every other byte of the frontmatter and
    body is byte-identical to the original.
    """
    work = tmp_path / "work"
    work.mkdir(parents=True)
    parent_page = work / "p.md"
    original = (
        "---\n"
        "title: p\n"
        "kind: feature\n"
        "status: open\n"
        "affects:\n"
        "  - packages/foo\n"
        "  - packages/bar\n"
        "tags: [alpha, beta]\n"
        "opened: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n\n"
        "## Summary\nbody text\n"
    )
    parent_page.write_text(original, encoding="utf-8")
    _write(work, "c1", kind="bug", parent="p")

    assert refresh_children(work) == ["p"]

    expected = original.replace(
        "tags: [alpha, beta]",
        "children:\n- c1\ntags: [alpha, beta]",
    )
    assert parent_page.read_text(encoding="utf-8") == expected


def test_refresh_splices_crlf_page(tmp_path: Path) -> None:
    """A CRLF-saved parent page still gets its children spliced (not silently skipped).

    _frontmatter_span requires an exact "---\\n" fence; a page saved with "\\r\\n"
    line endings never matches it unless refresh_children first normalizes the
    text, so this pins that normalization happens before spanning/splicing.
    """
    work = tmp_path / "work"
    work.mkdir(parents=True)
    parent_page = work / "p.md"
    original_lf = (
        "---\n"
        "title: p\n"
        "kind: feature\n"
        "status: open\n"
        "affects: []\n"
        "opened: '2026-07-01'\n"
        "updated: '2026-07-01'\n"
        "---\n\n"
        "## Summary\nbody text\n"
    )
    parent_page.write_bytes(original_lf.replace("\n", "\r\n").encode("utf-8"))
    _write(work, "c1", kind="bug", parent="p")

    assert refresh_children(work) == ["p"]
    fm, _ = parse(parent_page.read_text(encoding="utf-8"))
    assert fm["children"] == ["c1"]
