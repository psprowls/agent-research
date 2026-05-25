"""
ingest_source.py — Library functions for preparing a source for LLM ingestion.

Extracted from lattice-wiki-core's ingest_source.py.
Library functions only — no argparse main(), no version-check, no subprocess calls.

Supported source formats (stdlib only): .md .txt .html .htm .json .csv

Exports:
    slugify(text) -> str
    extract(path) -> tuple[str, str | None]
    guess_source_type(rel_to_wiki, rel_to_repo) -> str
    language_for(path) -> str
    list_folder_files(root) -> list[tuple[str, int]]
    pick_representative(root, entries) -> str | None
    folder_brief(root, rel_to_wiki) -> dict
    _HTMLTextExtractor
"""

from __future__ import annotations

import html.parser
import json
import re
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.layout_io import ensure_subpage
from wiki_io.scan_monorepo import compute_state_gate

PREVIEW_CHARS = 1200
SLUG_RE = re.compile(r"[^a-z0-9]+")

LANGUAGE_BY_EXT = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".py": "python",
    ".go": "go",
    ".rs": "rust",
    ".md": "markdown",
    ".json": "json",
}

REPRESENTATIVE_INDEX_NAMES = [
    "index.ts",
    "index.tsx",
    "index.js",
    "index.py",
    "index.go",
    "index.rs",
]

LARGE_FILE_BYTES = 200 * 1024
WARN_FILE_COUNT = 50
ERROR_FILE_COUNT = 200


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = SLUG_RE.sub("-", text).strip("-")
    return text[:60] or "untitled"


class _HTMLTextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.title = None
        self._in_title = False
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip = True
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = False
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title and self.title is None:
            self.title = data.strip() or None
        else:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self):
        return "\n".join(self.parts)


def extract(path: Path) -> tuple[str, str | None]:
    ext = path.suffix.lower()
    data = path.read_bytes()
    if ext in {".md", ".txt"}:
        text = data.decode("utf-8", errors="replace")
        title = None
        for line in text.splitlines()[:20]:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        return text, title
    if ext in {".html", ".htm"}:
        parser = _HTMLTextExtractor()
        try:
            parser.feed(data.decode("utf-8", errors="replace"))
        except Exception:
            pass
        return parser.text(), parser.title
    if ext == ".json":
        try:
            obj = json.loads(data.decode("utf-8", errors="replace"))
            return json.dumps(obj, indent=2)[:100000], None
        except Exception:
            return data.decode("utf-8", errors="replace"), None
    if ext == ".csv":
        text = data.decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[:50]), None
    try:
        return data.decode("utf-8", errors="replace"), None
    except Exception:
        return "", None


def guess_source_type(rel_to_wiki: Path | None, rel_to_repo: Path | None) -> str:
    """Guess source_type from where the file lives.

    `rel_to_wiki` is the source path relative to the wiki (e.g. raw/specs/x.md)
    when the source lives under <workspace>/raw/. `rel_to_repo` is the repo-relative
    path when the source is an in-repo doc. Either may be None.
    """
    if rel_to_wiki is not None:
        parts = rel_to_wiki.parts
        if "specs" in parts:
            return "spec"
        if "articles" in parts:
            return "article"
        if "prs" in parts:
            return "pr"
        if "tickets" in parts:
            return "ticket"
        if "transcripts" in parts:
            return "transcript"
        if "examples" in parts:
            return "example"
    if rel_to_repo is not None:
        return "doc"
    return "note"


def language_for(path: Path) -> str:
    return LANGUAGE_BY_EXT.get(path.suffix.lower(), "unknown")


def list_folder_files(root: Path) -> list[tuple[str, int]]:
    """Return sorted (rel_path, size) for every regular file under root."""
    entries = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root)
            entries.append((str(rel).replace("\\", "/"), p.stat().st_size))
    return entries


def pick_representative(root: Path, entries: list[tuple[str, int]]) -> str | None:
    """Return rel-path of representative file.
    Priority: README.md (case-insensitive) -> index.{ts,tsx,js,py,go,rs} -> largest.
    """
    by_name_lower = {rel.lower(): rel for rel, _ in entries}
    if "readme.md" in by_name_lower:
        return by_name_lower["readme.md"]
    for cand in REPRESENTATIVE_INDEX_NAMES:
        if cand in by_name_lower:
            return by_name_lower[cand]
    if not entries:
        return None
    sorted_entries = sorted(entries, key=lambda e: (-e[1], e[0]))
    return sorted_entries[0][0]


def folder_brief(root: Path, rel_to_wiki: Path | None) -> dict:
    """Build the folder-mode addendum to the brief.
    Returns dict; if too many files, returns {'_error': ...} so caller can exit non-zero.
    """
    entries = list_folder_files(root)
    file_count = len(entries)
    total_size = sum(sz for _, sz in entries)
    warnings = []
    if file_count > ERROR_FILE_COUNT:
        return {"_error": f"folder has {file_count} files (>{ERROR_FILE_COUNT}); pass a specific file instead"}
    if file_count > WARN_FILE_COUNT:
        warnings.append("folder_size")
    if any(sz > LARGE_FILE_BYTES for _, sz in entries):
        warnings.append("large_file")
    representative = pick_representative(root, entries)
    return {
        "is_folder": True,
        "file_count": file_count,
        "total_size": total_size,
        "files": [{"path": rel, "size": sz, "language": language_for(Path(rel))} for rel, sz in entries],
        "representative_file": representative,
        "warnings": warnings,
    }
