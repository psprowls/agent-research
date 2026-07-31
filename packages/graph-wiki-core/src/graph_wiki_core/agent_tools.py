"""Reusable bounded tool and context helpers for graph-wiki agent roles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from wiki_io.proposals import read_proposal
from wiki_io.update_index import parse_frontmatter

from graph_wiki_core.text_utils import truncate_text  # noqa: F401 — re-exported for existing callers

CURATED_CATALOG_BUCKETS = ("concepts", "adrs", "sources")
DEFAULT_EXCERPT_CHARS = 500


@dataclass(frozen=True)
class SourceChunks:
    full_text: str | None
    chunks: list[str]
    over_budget: bool


def body_without_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].strip()


def _frontmatter_entry(path: Path, wiki: Path, kind: str, *, excerpt_chars: int) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    metadata = parse_frontmatter(text)
    rel_path = path.relative_to(wiki).as_posix()
    body = body_without_frontmatter(text)
    excerpt = " ".join(body.split())[:excerpt_chars]
    return {
        "kind": kind,
        "slug": path.stem,
        "path": rel_path,
        "title": metadata.get("title", path.stem.replace("-", " ").replace("_", " ").title()),
        "summary": metadata.get("summary", ""),
        "uri": metadata.get("uri", ""),
        "entity_kind": metadata.get("kind", ""),
        "excerpt": excerpt,
    }


def _resolved_path_under_wiki(path: Path, wiki_root: Path) -> Path | None:
    try:
        resolved = path.resolve()
        resolved.relative_to(wiki_root)
    except (OSError, ValueError):
        return None
    return resolved


def _list_safe_proposals(wiki_root: Path) -> list[dict[str, Any]]:
    proposal_dir = wiki_root / "proposals"
    if not proposal_dir.is_dir():
        return []
    proposals: list[dict[str, Any]] = []
    for path in sorted(proposal_dir.glob("*.md")):
        proposal_path = _resolved_path_under_wiki(path, wiki_root)
        if proposal_path is None:
            continue
        try:
            proposals.append(read_proposal(proposal_path))
        except Exception:  # noqa: BLE001 - match list_proposals() malformed-note behavior.
            continue
    return proposals


def build_wiki_catalog(
    wiki: Path,
    buckets: tuple[str, ...] = CURATED_CATALOG_BUCKETS,
    *,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
) -> dict[str, list[dict[str, Any]]]:
    catalog: dict[str, list[dict[str, Any]]] = {name: [] for name in buckets}
    catalog["entities"] = []
    wiki_root = wiki.resolve()
    catalog["proposals"] = _list_safe_proposals(wiki_root)

    for dirname in buckets:
        try:
            directory = (wiki_root / dirname).resolve()
            directory.relative_to(wiki_root)
        except (OSError, ValueError):
            continue
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == "index.md":
                continue
            page = _resolved_path_under_wiki(path, wiki_root)
            if page is None:
                continue
            entry = _frontmatter_entry(page, wiki_root, dirname.rstrip("s"), excerpt_chars=excerpt_chars)
            if entry is not None:
                catalog[dirname].append(entry)

    entities = wiki_root / "entities"
    if entities.is_dir():
        for path in sorted(entities.rglob("*.md")):
            if path.name == "index.md":
                continue
            page = _resolved_path_under_wiki(path, wiki_root)
            if page is None:
                continue
            entry = _frontmatter_entry(page, wiki_root, "entity", excerpt_chars=excerpt_chars)
            if entry is not None:
                catalog["entities"].append(entry)

    return catalog


def read_bounded_wiki_page(wiki: Path, rel_path: str, *, max_chars: int = DEFAULT_EXCERPT_CHARS) -> str:
    try:
        wiki_root = wiki.resolve()
        page = (wiki_root / rel_path).resolve()
        page.relative_to(wiki_root)
    except ValueError:
        return "ERROR: path is outside wiki"
    except OSError as exc:
        return f"ERROR: {exc}"

    if page.suffix != ".md":
        return "ERROR: only markdown wiki pages may be read"
    if not page.is_file():
        return f"ERROR: wiki page not found: {rel_path}"

    try:
        text = page.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"ERROR: {exc}"

    metadata = parse_frontmatter(text)
    body = body_without_frontmatter(text)
    title = str(metadata.get("title") or page.stem.replace("-", " ").replace("_", " ").title())
    content = f"# {title}\n\n{body}" if body else f"# {title}"
    return truncate_text(content, max_chars)


def _flatten_catalog(catalog: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, entries in catalog.items():
        for entry in entries:
            if isinstance(entry, dict):
                row = dict(entry)
                row.setdefault("bucket", bucket)
                rows.append(row)
    return rows


def _catalog_bucket_matches(bucket: str, entry: dict[str, Any], kind: str | None) -> bool:
    if not kind:
        return True
    normalized = kind.lower().strip()
    if normalized == bucket or normalized == bucket.rstrip("s"):
        return True
    entry_kind = str(entry.get("kind", "")).lower()
    return normalized == entry_kind or normalized == f"{entry_kind}s"


def search_wiki_catalog(
    catalog: dict[str, list[dict[str, Any]]],
    query: str,
    *,
    kind: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    query_lc = query.lower().strip()
    matches: list[dict[str, Any]] = []
    for row in _flatten_catalog(catalog):
        bucket = str(row.get("bucket", ""))
        if not _catalog_bucket_matches(bucket, row, kind):
            continue
        fields = [
            str(row.get("title", "")),
            str(row.get("summary", "")),
            str(row.get("slug", "")),
            str(row.get("target_slug", "")),
        ]
        haystack = " ".join(fields).lower()
        if not query_lc or query_lc in haystack:
            matches.append(row)
        if len(matches) >= limit:
            break
    return matches


def chunk_text(text: str, *, max_chars: int, chunk_chars: int) -> SourceChunks:
    if len(text) <= max_chars:
        return SourceChunks(full_text=text, chunks=[], over_budget=False)
    chunks = [text[start : start + chunk_chars] for start in range(0, len(text), chunk_chars)]
    return SourceChunks(full_text=None, chunks=chunks, over_budget=True)


def filter_graph_tools(graph_tools: list[BaseTool], allowed_names: set[str]) -> list[BaseTool]:
    return [graph_tool for graph_tool in graph_tools if graph_tool.name in allowed_names]
