"""Proposal reasoner context helpers for ingest-time curated-page suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wiki_io.proposals import list_proposals
from wiki_io.update_index import parse_frontmatter

CURATED_DIRS = ("concepts", "adrs", "architecture", "sources")
FULL_SOURCE_MAX_CHARS = 120_000
SOURCE_CHUNK_CHARS = 20_000
EXCERPT_CHARS = 500


@dataclass(frozen=True)
class SourceChunks:
    full_text: str | None
    chunks: list[str]
    over_budget: bool


def _body_without_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].strip()


def _frontmatter_entry(path: Path, wiki: Path, kind: str) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    metadata = parse_frontmatter(text)
    rel_path = path.relative_to(wiki).as_posix()
    body = _body_without_frontmatter(text)
    excerpt = " ".join(body.split())[:EXCERPT_CHARS]
    entry: dict[str, Any] = {
        "kind": kind,
        "slug": path.stem,
        "path": rel_path,
        "title": metadata.get("title", path.stem.replace("-", " ").replace("_", " ").title()),
        "summary": metadata.get("summary", ""),
        "uri": metadata.get("uri", ""),
        "entity_kind": metadata.get("kind", ""),
        "excerpt": excerpt,
    }
    return entry


def build_wiki_catalog(wiki: Path) -> dict[str, list[dict[str, Any]]]:
    catalog: dict[str, list[dict[str, Any]]] = {name: [] for name in CURATED_DIRS}
    catalog["entities"] = []
    catalog["proposals"] = list_proposals(wiki)

    for dirname in CURATED_DIRS:
        directory = wiki / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == "index.md":
                continue
            entry = _frontmatter_entry(path, wiki, dirname.rstrip("s"))
            if entry is not None:
                catalog[dirname].append(entry)

    entities = wiki / "entities"
    if entities.is_dir():
        for path in sorted(entities.rglob("*.md")):
            if path.name == "index.md":
                continue
            entry = _frontmatter_entry(path, wiki, "entity")
            if entry is not None:
                catalog["entities"].append(entry)

    return catalog


def build_source_chunks(
    source_text: str,
    *,
    max_chars: int = FULL_SOURCE_MAX_CHARS,
    chunk_chars: int = SOURCE_CHUNK_CHARS,
) -> SourceChunks:
    if len(source_text) <= max_chars:
        return SourceChunks(full_text=source_text, chunks=[], over_budget=False)
    chunks = [source_text[start : start + chunk_chars] for start in range(0, len(source_text), chunk_chars)]
    return SourceChunks(full_text=None, chunks=chunks, over_budget=True)
