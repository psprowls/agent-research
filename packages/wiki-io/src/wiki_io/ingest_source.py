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


def _build_entity_match(workspace_root: Path, repo: Path, source_path: Path, title_guess: str) -> dict:
    """Resolve the entity a source belongs to and the on-disk entity filename.

    Bedrock-free. Opens a read-only graph conn; returns
    {"uri": None, "entity_filename": None} when the graph is missing or no
    entity matches (the harness agent proceeds without a link in that case).
    """
    from graph_io.store import GraphNotInitializedError, read_only_connect
    from workspace_io.paths import graph_dir

    from wiki_io.entity_lookup import (
        entity_filename_for_uri,
        lookup_entity_by_name,
        lookup_entity_by_path,
    )

    empty = {"uri": None, "entity_filename": None}
    try:
        conn = read_only_connect(graph_dir(workspace_root) / "code.db")
    except GraphNotInitializedError:
        return empty
    try:
        match = lookup_entity_by_path(conn, repo, source_path)
        if match is None:
            match = lookup_entity_by_name(conn, title_guess)
        if match is None:
            return empty
        uri = match[0]
        return {"uri": uri, "entity_filename": entity_filename_for_uri(uri, conn)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    """Emit the ingest prep brief (JSON) consumed by the harness ingestor agent.

    Bedrock-free: builds on this module's library functions plus the shared
    `wiki_io.entity_lookup`. Never imports model_adapter / subagent_runtime.
    """
    import argparse
    import datetime
    import json as _json
    import sys

    parser = argparse.ArgumentParser(description="Prepare a source for ingestion.")
    parser.add_argument("source", nargs="?", default=None, help="Path to the source file/folder")
    parser.add_argument("--source", dest="source_opt", default=None, help="Path to the source (alt form)")
    parser.add_argument("--workspace", default="", help="Workspace path (default: env / git heuristic)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON brief")
    args = parser.parse_args()

    source_arg = args.source_opt or args.source
    if not source_arg:
        print("[error] no source path given", file=sys.stderr)
        sys.exit(1)
    source_path = Path(source_arg)

    workspace_path = Path(args.workspace) if args.workspace else None
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    if repo is None:
        repo = Path.cwd()
    workspace_root = workspace_path if workspace_path is not None else wiki.parent

    # Resolve a relative source_path against repo root so relative_to() works below.
    if not source_path.is_absolute():
        candidate = repo / source_path
        source_path = candidate if candidate.exists() else source_path.resolve()

    # Folder ingest (raw/examples/<dir>/).
    if source_path.is_dir():
        rel_to_wiki = None
        try:
            rel_to_wiki = source_path.relative_to(wiki)
        except ValueError:
            pass
        brief: dict = {
            "is_folder": True,
            **folder_brief(source_path, rel_to_wiki),
            "state_gate": compute_state_gate(repo),
        }
        if "_error" in brief:
            print(f"[error] {brief['_error']}", file=sys.stderr)
            sys.exit(1)
        if args.json_output:
            print(_json.dumps(brief, indent=2))
        return

    # Single-file ingest.
    text, title = extract(source_path)
    title_guess = title or source_path.stem.replace("-", " ").title()
    slug = slugify(title_guess)

    rel_to_wiki = None
    rel_to_repo = None
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        pass
    try:
        rel_to_repo = source_path.relative_to(repo)
    except ValueError:
        pass
    source_type = guess_source_type(rel_to_wiki, rel_to_repo)

    preview = text[:PREVIEW_CHARS]
    if len(text) > PREVIEW_CHARS:
        preview += "\n[TRUNCATED]"

    month = datetime.date.today().strftime("%Y-%m")
    suggested = f"sources/{month}-{slug}.md"
    page_exists = (wiki / suggested).exists()

    in_repo_doc = rel_to_repo is not None and rel_to_wiki is None

    brief = {
        "source_path": str(source_path),
        "title": title_guess,
        "source_type": source_type,
        "slug": slug,
        "preview": preview,
        "word_count": len(text.split()),
        "suggested_summary_path": suggested,
        "merge_mode": page_exists,
        "in_repo_doc": in_repo_doc,
        "entity_match": _build_entity_match(workspace_root, repo, source_path, title_guess),
        "state_gate": compute_state_gate(repo),
    }
    if args.json_output:
        print(_json.dumps(brief, indent=2))
    else:
        print(f"Title: {brief['title']}")
        print(f"Source type: {brief['source_type']}")
        print(f"Suggested summary: {brief['suggested_summary_path']}")
        em = brief["entity_match"]
        if em["uri"]:
            print(f"Entity match: {em['uri']} -> [[entities/{em['entity_filename']}]]")


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
