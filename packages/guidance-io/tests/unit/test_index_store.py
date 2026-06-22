from __future__ import annotations

from pathlib import Path

from guidance_io.index_store import (
    GuidanceIndex,
    IndexEntry,
    content_hash,
    load_index,
    save_index,
)


def test_content_hash_stable() -> None:
    assert content_hash(b"abc") == content_hash(b"abc")
    assert content_hash(b"abc") != content_hash(b"abd")


def test_load_index_absent_returns_empty(tmp_path: Path) -> None:
    idx = load_index(tmp_path)
    assert idx.vocab_hash == ""
    assert idx.files == {}


def test_save_then_load_roundtrips(tmp_path: Path) -> None:
    idx = GuidanceIndex(
        vocab_hash="deadbeef",
        files={
            "packages/foo/src/foo/bar.py": IndexEntry(
                topics=["python"],
                tags=["retry", "resilience"],
                content_hash="abc123",
                scanned_at="2026-06-22",
            )
        },
    )
    path = save_index(tmp_path, idx)
    assert path.exists()
    assert path == tmp_path / ".graph-wiki" / "guidance-index.json"

    loaded = load_index(tmp_path)
    assert loaded.vocab_hash == "deadbeef"
    entry = loaded.files["packages/foo/src/foo/bar.py"]
    assert entry.topics == ["python"]
    assert entry.tags == ["retry", "resilience"]
    assert entry.content_hash == "abc123"
    assert entry.scanned_at == "2026-06-22"


def test_save_creates_graph_wiki_dir(tmp_path: Path) -> None:
    save_index(tmp_path, GuidanceIndex(vocab_hash="x", files={}))
    assert (tmp_path / ".graph-wiki").is_dir()
