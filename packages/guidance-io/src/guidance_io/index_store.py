"""Sidecar file->vocabulary index at .graph-wiki/guidance-index.json.

Keyed by repo-root-relative POSIX file path. A file is re-scanned when its
content_hash changes or it is new; when the header vocab_hash differs from the
stored one, the whole index is rebuilt (the closed set the model chose from
changed). JSON for v1; may graduate to sqlite if it grows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from guidance_io.paths import guidance_index_path


@dataclass
class IndexEntry:
    topics: list[str]
    tags: list[str]
    content_hash: str
    scanned_at: str


@dataclass
class GuidanceIndex:
    vocab_hash: str = ""
    files: dict[str, IndexEntry] = field(default_factory=dict)


def content_hash(data: bytes) -> str:
    """Hex sha256 of raw file bytes."""
    return hashlib.sha256(data).hexdigest()


def load_index(workspace: Path) -> GuidanceIndex:
    """Load the sidecar index; return an empty index if absent or unparseable."""
    path = guidance_index_path(workspace)
    if not path.is_file():
        return GuidanceIndex()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return GuidanceIndex()
    files = {
        key: IndexEntry(
            topics=list(entry.get("topics", [])),
            tags=list(entry.get("tags", [])),
            content_hash=str(entry.get("content_hash", "")),
            scanned_at=str(entry.get("scanned_at", "")),
        )
        for key, entry in (raw.get("files") or {}).items()
    }
    return GuidanceIndex(vocab_hash=str(raw.get("vocab_hash", "")), files=files)


def save_index(workspace: Path, index: GuidanceIndex) -> Path:
    """Write the index sidecar (pretty JSON); return its path."""
    path = guidance_index_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "vocab_hash": index.vocab_hash,
        "files": {key: asdict(entry) for key, entry in index.files.items()},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
