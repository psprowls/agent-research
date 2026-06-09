"""
ingest_source.py — Library functions for preparing a source for LLM ingestion.

Extracted from lattice-wiki-core's ingest_source.py.
Library functions only — no argparse main(), no version-check, no subprocess calls.

Supported source formats (stdlib only): .md .txt .html .htm .json .csv

Exports:
    slugify(text) -> str
    extract(path) -> tuple[str, str | None]
    guess_source_type(rel_to_workspace, rel_to_repo) -> str
    SOURCE_TYPE_ENUM, RAW_FOLDER_TYPES   (closed source_type enum + raw-folder subset)
    language_for(path) -> str
    list_folder_files(root) -> list[tuple[str, int]]
    pick_representative(root, entries) -> str | None
    folder_brief(root, rel_to_wiki) -> dict
    build_folder_ingest_brief(source_path, wiki, repo) -> dict
    build_ingest_brief(source_path, wiki, repo, workspace_root) -> dict
    resolve_skill_anchor(source_path) -> Path | None
    SkillBundle   (dataclass — directory-aware skill ingest)
    gather_skill_sources(anchor) -> SkillBundle
    _HTMLTextExtractor
"""

from __future__ import annotations

import datetime
import html.parser
import json
import re
from dataclasses import dataclass
from pathlib import Path

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


# Source-type model (source-type-consolidation design 2026-06-05). One closed
# enum on every Source page; `note` is the catch-all (no `unknown`, no `rfc`).
SOURCE_TYPE_ENUM = frozenset({"spec", "article", "pr", "ticket", "transcript", "example", "doc", "note", "skill"})
# The subset a `raw/<type>/` folder produces authoritatively. The LLM cannot
# override these — see run_ingest_source / build_ingest_brief.
RAW_FOLDER_TYPES = frozenset({"spec", "article", "pr", "ticket", "transcript", "example", "skill"})


def guess_source_type(rel_to_workspace: Path | None, rel_to_repo: Path | None) -> str:
    """Guess source_type from where the file lives.

    `rel_to_workspace` is the source path relative to the WORKSPACE root (e.g.
    `raw/specs/x.md`) when the source lives under `<workspace>/raw/`. `raw/` is a
    sibling of `wiki/`, so this must be measured from the workspace root, NOT the
    wiki dir. `rel_to_repo` is the repo-relative path for an in-repo doc. Either
    may be None.
    """
    if rel_to_workspace is not None:
        parts = rel_to_workspace.parts
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
        if "skill" in parts:
            return "skill"
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


def _resolve_source_path(source_path: Path, repo: Path) -> Path:
    if source_path.is_absolute():
        return source_path
    candidate = repo / source_path
    return candidate if candidate.exists() else source_path.resolve()


def build_folder_ingest_brief(source_path: Path, wiki: Path, repo: Path) -> dict:
    source_path = _resolve_source_path(source_path, repo)
    rel_to_wiki = None
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        pass
    brief: dict = {
        "is_folder": True,
        **folder_brief(source_path, rel_to_wiki),
        "state_gate": compute_state_gate(repo, workspace=wiki.parent),
    }
    return brief


def build_ingest_brief(source_path: Path, wiki: Path, repo: Path, workspace_root: Path) -> dict:
    source_path = _resolve_source_path(source_path, repo)
    text, title = extract(source_path)
    title_guess = title or source_path.stem.replace("-", " ").title()
    slug = slugify(title_guess)

    rel_to_wiki = None
    rel_to_repo = None
    rel_to_workspace = None
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        pass
    try:
        rel_to_repo = source_path.relative_to(repo)
    except ValueError:
        pass
    try:
        rel_to_workspace = source_path.relative_to(workspace_root)
    except ValueError:
        pass
    # raw/<type>/ folders are authoritative; guess from the WORKSPACE-relative
    # path because raw/ is a sibling of wiki/ (not under it). `in_repo_doc`
    # keeps its wiki-relative semantics below — drift behavior is unchanged.
    source_type = guess_source_type(rel_to_workspace, rel_to_repo)

    preview = text[:PREVIEW_CHARS]
    if len(text) > PREVIEW_CHARS:
        preview += "\n[TRUNCATED]"

    month = datetime.date.today().strftime("%Y-%m")
    suggested = f"sources/{month}-{slug}.md"
    page_exists = (wiki / suggested).exists()
    in_repo_doc = rel_to_repo is not None and rel_to_wiki is None

    return {
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
        "state_gate": compute_state_gate(repo, workspace=workspace_root),
    }


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


# ---------------------------------------------------------------------------
# Directory-aware skill ingest (2026-06-09 design).
#
# A skill is frequently a directory: a SKILL.md that links out to companion
# reference markdown. These pure, Bedrock-free helpers gather SKILL.md plus all
# transitively-linked companion .md into one combined text and report the
# non-markdown files that were excluded. The combined text is fed unchanged to
# the existing two-pass skill branch in graph-wiki-core.
# ---------------------------------------------------------------------------


@dataclass
class SkillBundle:
    """Result of gathering a skill directory into one combined markdown blob.

    Fields:
        combined_text:   SKILL.md, then linked companion files in DFS link order,
                         each prefixed with an `<!-- skill-file: <rel> -->` marker.
        skill_dir:       the resolved directory containing the anchor SKILL.md.
        anchor:          the resolved SKILL.md the bundle is anchored on.
        title:           SKILL.md frontmatter `name:` → first `# ` heading → None.
        included_files:  skill_dir-relative POSIX paths, SKILL.md first, DFS order.
        excluded_files:  every non-.md file under skill_dir (POSIX rel, sorted).
        scripts_dominant: True when a top-level `scripts/` dir exists OR there are
                         more excluded files than included.
    """

    combined_text: str
    skill_dir: Path
    anchor: Path
    title: str | None
    included_files: list[str]
    excluded_files: list[str]
    scripts_dominant: bool


def resolve_skill_anchor(source_path: Path) -> Path | None:
    """Return the SKILL.md to anchor a skill ingest on, or None.

    - a directory containing `SKILL.md` -> `<dir>/SKILL.md`
    - a file named `SKILL.md`           -> the file itself
    - anything else                     -> None (caller falls back to today's path)
    """
    if source_path.is_dir():
        candidate = source_path / "SKILL.md"
        return candidate if candidate.is_file() else None
    if source_path.is_file() and source_path.name == "SKILL.md":
        return source_path
    return None


def _skill_title(anchor_text: str) -> str | None:
    """Title from a SKILL.md: frontmatter `name:` → first `# ` heading → None.

    Stdlib-only (this module avoids a yaml dependency): the frontmatter `name:`
    is read line-by-line from the leading `---`-fenced block.
    """
    stripped = anchor_text.lstrip()
    if stripped.startswith("---"):
        after = stripped[3:].lstrip("\n")
        end = after.find("\n---")
        if end != -1:
            for line in after[:end].splitlines():
                if line.strip().startswith("name:"):
                    value = line.split(":", 1)[1].strip().strip("\"'")
                    if value:
                        return value
    for line in anchor_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def gather_skill_sources(anchor: Path) -> SkillBundle:
    """Gather a skill directory into one combined markdown blob.

    Reads `anchor` (a SKILL.md) plus every companion `.md` it links to,
    transitively, and concatenates them with `<!-- skill-file: <rel> -->`
    markers. Non-markdown files under the skill directory are recorded in
    `excluded_files` (not read). Pure / Bedrock-free.
    """
    skill_dir = anchor.parent.resolve()

    # DFS preorder from the anchor, visited-set keyed by resolved abs path so
    # cycles terminate and each file is included at most once. (Link-following
    # recursion is wired in a later step; here we visit the anchor only.)
    visited: set[Path] = set()
    included: list[tuple[Path, str]] = []  # (resolved_abs_path, content), DFS order

    def visit(md_file: Path) -> None:
        resolved = md_file.resolve()
        if resolved in visited:
            return
        visited.add(resolved)
        content = resolved.read_text(encoding="utf-8", errors="replace")
        included.append((resolved, content))

    visit(anchor)

    parts = []
    for abs_path, content in included:
        rel = abs_path.relative_to(skill_dir).as_posix()
        parts.append(f"<!-- skill-file: {rel} -->\n{content}")
    combined_text = "\n\n".join(parts)

    included_files = [abs_path.relative_to(skill_dir).as_posix() for abs_path, _ in included]
    excluded_files = sorted(
        p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob("*") if p.is_file() and p.suffix.lower() != ".md"
    )
    scripts_dominant = (skill_dir / "scripts").is_dir() or len(excluded_files) > len(included_files)

    return SkillBundle(
        combined_text=combined_text,
        skill_dir=skill_dir,
        anchor=anchor.resolve(),
        title=_skill_title(included[0][1]),
        included_files=included_files,
        excluded_files=excluded_files,
        scripts_dominant=scripts_dominant,
    )
