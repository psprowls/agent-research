"""Batch ingest brief: kind-folder detection + unit enumeration (Bedrock-free)."""

from __future__ import annotations

from pathlib import Path

from wiki_io.ingest_source import (
    BATCH_KIND_FOLDERS,
    build_batch_ingest_brief,
    enumerate_batch_units,
    resolve_batch_root,
)


def _mk_workspace(tmp_path: Path) -> Path:
    (tmp_path / "wiki").mkdir()
    (tmp_path / "raw").mkdir()
    return tmp_path


def _write(p: Path, text: str = "# Doc\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_batch_kind_folders_enum() -> None:
    assert BATCH_KIND_FOLDERS == frozenset({"specs", "articles", "prs", "tickets", "transcripts", "examples", "skills"})


def test_resolve_batch_root_hits_every_kind(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    for kind in sorted(BATCH_KIND_FOLDERS):
        root = ws / "raw" / kind
        root.mkdir()
        assert resolve_batch_root(root, ws) == kind


def test_resolve_batch_root_rejects_non_roots(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    _write(ws / "raw" / "specs" / "nested" / "a.md")
    assert resolve_batch_root(ws / "raw", ws) is None  # raw/ itself
    assert resolve_batch_root(ws / "raw" / "specs" / "nested", ws) is None  # nested dir
    assert resolve_batch_root(ws / "raw" / "specs" / "nested" / "a.md", ws) is None  # a file
    assert resolve_batch_root(ws / "raw" / "_archive", ws) is None  # not a kind
    other = tmp_path / "elsewhere" / "specs"
    other.mkdir(parents=True)
    assert resolve_batch_root(other, ws) is None  # outside workspace


def test_flat_kind_enumerates_files_recursively_sorted(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "specs"
    _write(root / "b.md")
    _write(root / "a.md")
    _write(root / "nested" / "c.md")
    units = enumerate_batch_units("specs", root)
    assert [u["rel"] for u in units] == ["a.md", "b.md", "nested/c.md"]
    assert all(u["unit_type"] == "file" for u in units)
    assert all(Path(u["path"]).is_absolute() for u in units)


def test_skills_enumerates_immediate_subdirs_only(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "skills"
    _write(root / "foo" / "SKILL.md")
    _write(root / "bar" / "SKILL.md")
    _write(root / "loose-note.md")  # loose file: not a unit for skills
    units = enumerate_batch_units("skills", root)
    assert [u["rel"] for u in units] == ["bar", "foo"]
    assert all(u["unit_type"] == "dir" for u in units)


def test_examples_enumerates_subdirs_plus_loose_files(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "examples"
    _write(root / "demo-app" / "index.ts")
    _write(root / "loose.md")
    units = enumerate_batch_units("examples", root)
    by_rel = {u["rel"]: u["unit_type"] for u in units}
    assert by_rel == {"demo-app": "dir", "loose.md": "file"}


def test_archive_assets_and_dotfiles_excluded(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "specs"
    _write(root / "keep.md")
    _write(root / "_archive" / "old.md")
    _write(root / "assets" / "img.md")
    _write(root / ".DS_Store", "junk")
    units = enumerate_batch_units("specs", root)
    assert [u["rel"] for u in units] == ["keep.md"]

    skills_root = ws / "raw" / "skills"
    _write(skills_root / "good" / "SKILL.md")
    (skills_root / "_archive").mkdir()
    (skills_root / ".hidden").mkdir()
    units = enumerate_batch_units("skills", skills_root)
    assert [u["rel"] for u in units] == ["good"]


def test_build_batch_ingest_brief_shape(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "specs"
    _write(root / "a.md")
    brief = build_batch_ingest_brief(source_path=root, wiki=ws / "wiki", repo=ws, workspace_root=ws)
    assert brief is not None
    assert brief["is_batch"] is True
    assert brief["kind_folder"] == "specs"
    assert brief["unit_count"] == 1
    assert brief["units"][0]["rel"] == "a.md"
    assert "state_gate" in brief


def test_build_batch_ingest_brief_empty_folder(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    root = ws / "raw" / "articles"
    root.mkdir()
    brief = build_batch_ingest_brief(source_path=root, wiki=ws / "wiki", repo=ws, workspace_root=ws)
    assert brief is not None
    assert brief["unit_count"] == 0
    assert brief["units"] == []


def test_build_batch_ingest_brief_none_for_non_batch_path(tmp_path: Path) -> None:
    ws = _mk_workspace(tmp_path)
    _write(ws / "raw" / "specs" / "a.md")
    assert (
        build_batch_ingest_brief(
            source_path=ws / "raw" / "specs" / "a.md", wiki=ws / "wiki", repo=ws, workspace_root=ws
        )
        is None
    )
