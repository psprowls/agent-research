"""Scanner-derived `## Referenced in wiki` backlink regeneration (Slice 4).

Ingest writes durable forward-links (`entity_uri:` + `[[entities/<stem>]]`) into
preserved pages; this module derives the inverse — for each entity page, the
sorted list of preserved pages that link it. It is the backlink half of the
Slice 4 core principle: *ingest writes forward-links; the scanner derives
backlinks; ingest never edits entities/ pages.*

`## Referenced in wiki` is scanner-owned in the same sense as `## Narrative`
(D-16): the H2 heading is a hard convention, the body region is rewritten on
every scan, and everything outside it is preserved verbatim. Pure Python, no
Bedrock — runs in both narrated and `narrate=False` scans.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import frontmatter
from workspace_io.paths import work_dir

# Match the heading at column 0 followed only by optional trailing whitespace.
_HEADING_RE = re.compile(r"^## Referenced in wiki[ \t]*\n", re.MULTILINE)
# Next H2 at column 0 — bounds the rewritable body region.
_NEXT_H2_RE = re.compile(r"^## ", re.MULTILINE)
# A [[entities/<stem>]] wikilink, tolerating an Obsidian |alias or #anchor.
_ENTITY_LINK_RE = re.compile(r"\[\[entities/([^\]|#\n]+?)(?:[|#][^\]\n]*)?\]\]")

# Empty-state body (deterministic, idempotent).
_EMPTY_BODY = "_No wiki pages reference this entity yet._"

# Preserved categories (folder name -> category label used in the bullet link).
# `work` lives at <workspace>/work (sibling of wiki); handled separately.
_PRESERVED_WIKI_DIRS = ("sources", "concepts", "adrs", "architecture")


def inject_referenced_in_wiki(page_path: Path, body: str) -> None:
    """Replace the body of the `## Referenced in wiki` section with `body`.

    Locates the FIRST `## Referenced in wiki` H2 at column 0; replaces the
    region from end-of-heading up to the next H2 (or EOF) with `body.strip()`.
    Writes atomically (temp-file + os.replace). Idempotent.

    Returns without writing (no error) when the page lacks the heading —
    entity templates always carry it after Task 4.

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")
    match = _HEADING_RE.search(text)
    if match is None:
        return
    body_start = match.end()
    next_h2 = _NEXT_H2_RE.search(text, body_start)
    body_end = next_h2.start() if next_h2 is not None else len(text)
    cleaned = body.strip()
    new_body = f"\n{cleaned}\n\n" if cleaned else "\n\n"
    new_content = text[:body_start] + new_body + text[body_end:]
    if new_content == text:
        return
    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)


def _iter_preserved_pages(wiki: Path):
    """Yield (category, page_path) for every preserved page that may carry
    [[entities/...]] forward-links."""
    for folder in _PRESERVED_WIKI_DIRS:
        d = wiki / folder
        if d.is_dir():
            for p in sorted(d.rglob("*.md")):
                if p.name == "index.md":
                    continue
                yield folder, p
    # work/ lives under the wiki (wiki-rooted, like every other category).
    work_root = work_dir(wiki.parent)
    if work_root.is_dir():
        for p in sorted(work_root.rglob("*.md")):
            if p.name == "index.md":
                continue
            yield "work", p


def _format_bullet(category: str, slug: str, post) -> str:
    """Render one backlink bullet: `- [[<cat>/<slug>]] — <title> (<type>, <date>)`."""
    md = post.metadata if hasattr(post, "metadata") else {}
    title = str(md.get("title") or slug)
    stype = md.get("source_type")
    date = md.get("source_date") or md.get("date") or md.get("updated")
    suffix = ""
    parts = [str(p) for p in (stype, date) if p]
    if parts:
        suffix = " (" + ", ".join(parts) + ")"
    return f"- [[{category}/{slug}]] — {title}{suffix}"


def build_entity_backlink_map(wiki: Path) -> dict[str, list[tuple[str, str, Path]]]:
    """entity_stem -> [(category, slug, page_path)] for every [[entities/<stem>]]
    wikilink across the preserved wiki dirs.

    The inverse map ``regenerate_referenced_in_wiki`` builds internally, exposed
    as a value. A malformed referencing page is skipped (never fatal). Each
    referencing page contributes a given entity at most once (de-duped per page).
    """
    refs: dict[str, list[tuple[str, str, Path]]] = {}
    for category, page_path in _iter_preserved_pages(wiki):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort the map
            continue
        slug = page_path.stem
        seen_here: set[str] = set()
        for m in _ENTITY_LINK_RE.finditer(post.content):
            stem = m.group(1).strip().removesuffix(".md")
            if stem in seen_here:
                continue
            seen_here.add(stem)
            refs.setdefault(stem, []).append((category, slug, page_path))
    return refs


def regenerate_referenced_in_wiki(wiki: Path) -> list[str]:
    """Rebuild `## Referenced in wiki` on every entity page from the
    `[[entities/<stem>]]` wikilinks found across preserved pages.

    Backlinks key off body wikilinks (not the singular `entity_uri:` field), so
    a source touching several entities backlinks from all of them. Deterministic
    sort (by category, then slug). Idempotent. Returns the list of entity stems
    whose pages were (re)written.
    """
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return []

    refs = build_entity_backlink_map(wiki)

    updated: list[str] = []
    for page_path in sorted(entities_dir.glob("*.md")):
        stem = page_path.stem
        entries = refs.get(stem, [])
        if entries:
            entries_sorted = sorted(entries, key=lambda e: (e[0], e[1]))
            body = "\n".join(
                _format_bullet(cat, slug, frontmatter.load(pp))
                for cat, slug, pp in entries_sorted
            )
        else:
            body = _EMPTY_BODY
        inject_referenced_in_wiki(page_path, body)
        updated.append(stem)
    return updated
