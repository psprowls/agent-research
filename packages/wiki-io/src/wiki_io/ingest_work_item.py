"""
ingest_work_item.py — Library functions for filing a structured work item.

Extracted from lattice-wiki-core's ingest_work_item.py.
Library functions only — no argparse main(), no subprocess calls.

The critical change from the lattice-wiki-core version: subprocess helper calls
are replaced with direct imports of update_index() and append_log().

Exports:
    _err(msg, code, as_json) -> NoReturn
    _slugify(title) -> str
    _parse_frontmatter(yaml_text) -> dict
    _validate(fm) -> list[str]
    _emit_yaml(fm) -> str
    file_work_item(wiki, fm, body, slug, force, pkg_dir, pkg_title) -> dict
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import NoReturn

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.layout_io import ensure_subpage
from wiki_io.update_index import update_index

REQUIRED_FIELDS = (
    "title",
    "category",
    "kind",
    "status",
    "summary",
    "opened",
    "affects",
)
ALLOWED_CATEGORY = "work"
SLUG_RE = re.compile(r"[^a-z0-9]+")


def _err(msg: str, code: int = 2, as_json: bool = False) -> "NoReturn":
    if as_json:
        print(json.dumps({"status": "error", "message": msg}))
    else:
        print(f"[error] {msg}", file=sys.stderr)
    sys.exit(code)


def _slugify(title: str) -> str:
    s = SLUG_RE.sub("-", title.lower()).strip("-")
    return s or "untitled"


def _parse_frontmatter(yaml_text: str) -> dict:
    """Minimal YAML frontmatter parser tailored to work-page schema.

    Supports scalar `key: value` lines and `key:` followed by `  - item` lists.
    Doesn't handle nested mappings — work-page schema doesn't need them.
    """
    out: dict = {}
    cur_key: str | None = None
    cur_list: list | None = None
    for raw in yaml_text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("  - ") and cur_list is not None:
            cur_list.append(line[4:].strip())
            continue
        # End any open list
        if cur_list is not None:
            out[cur_key] = cur_list
            cur_key, cur_list = None, None
        if ":" not in line:
            raise ValueError(f"unparseable line: {line!r}")
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            cur_key, cur_list = key, []
        elif val == "[]":
            out[key] = []
        else:
            out[key] = val
    if cur_list is not None:
        out[cur_key] = cur_list
    return out


def _validate(fm: dict) -> list[str]:
    issues: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in fm:
            issues.append(f"missing required field: {field}")
    if fm.get("category") not in (None, ALLOWED_CATEGORY):
        issues.append(f"category must be 'work' (got {fm.get('category')!r})")
    return issues


def _emit_yaml(fm: dict) -> str:
    """Re-serialize parsed frontmatter to a stable YAML form for writing."""
    lines = ["---"]
    for key, val in fm.items():
        if isinstance(val, list):
            lines.append(f"{key}:" if val else f"{key}: []")
            for item in val:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines)


def file_work_item(
    wiki: Path,
    fm: dict,
    body: str,
    slug: str | None = None,
    force: bool = False,
    pkg_dir: Path | None = None,
    pkg_title: str | None = None,
) -> dict:
    """Write a work-item page and update index + log.

    Extracted from lattice-wiki-core's ingest_work_item.main() body.
    Calls update_index(wiki) and append_log(wiki, ...) directly (no subprocess).

    Args:
        wiki: Path to the wiki directory (e.g. <workspace>/wiki/).
        fm: Parsed frontmatter dict (must pass _validate()).
        body: Markdown body text.
        slug: Page slug; derived from fm['title'] via _slugify() if omitted.
        force: Overwrite existing page if True; raise FileExistsError if False.
        pkg_dir: Optional vault package directory Path for work sub-page linking.
        pkg_title: Display title for the package sub-page template.

    Returns:
        dict with keys: status, page_path (str), slug, title.

    Raises:
        FileExistsError: If the page already exists and force=False.
        OSError: If writing the page fails.
    """
    title = str(fm["title"])
    opened = str(fm["opened"])
    slug = slug or _slugify(title)

    work_root = wiki.parent / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    page_path = work_root / f"{opened}-{slug}.md"

    if page_path.exists() and not force:
        raise FileExistsError(f"page already exists: {page_path}")

    body = body if body.endswith("\n") else body + "\n"
    content = _emit_yaml(fm) + "\n\n" + body
    page_path.write_text(content, encoding="utf-8")

    # Side-effects: refresh index and append log (direct calls, no subprocess).
    update_index(wiki)
    append_log(
        wiki,
        "create",
        title,
        detail=f"work/{page_path.name}",
        silent=True,
        raise_exception=True,
    )

    if pkg_dir is not None:
        vault = wiki
        pkg_title_str = pkg_title or pkg_dir.name
        templates_dir = vault / ".templates"
        try:
            ensure_subpage(pkg_dir, "work", pkg_title_str, templates_dir)
        except FileNotFoundError:
            pass  # templates not installed -- skip silently
        work_sub = pkg_dir / "work.md"
        if work_sub.exists():
            bullet = f"- [[work/{opened}-{slug}]] — {fm.get('summary', '')}\n"
            existing = work_sub.read_text(encoding="utf-8")
            if not existing.endswith("\n"):
                existing += "\n"
            work_sub.write_text(existing + bullet, encoding="utf-8")

    return {"status": "ok", "page_path": str(page_path), "slug": slug, "title": title}
