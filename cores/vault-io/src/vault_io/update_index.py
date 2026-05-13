#!/usr/bin/env python3
"""
update_index.py — Regenerate wiki/index.md from the frontmatter of every vault page.

The index is content-oriented: a catalog organized by category, with one-line
summaries read from each page's YAML frontmatter.

Discovers wiki location from the resolved lattice workspace.

Usage:
    python update_index.py
    python update_index.py --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from vault_io._workspace import resolve_wiki_and_repo

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Categories rendered in the main index (navigation backbone only)
MAIN_INDEX_CATEGORIES = ["app", "domain", "package"]

# Keep the full order for category sub-index generation
CATEGORY_ORDER = [
    "architecture",
    "app",
    "package",
    "domain",
    "concept",
    "dependency",
    "work",
    "adr",
    "source",
    "other",
]

# Category sub-index files inside the wiki; folder-scoped categories use <folder>/index.md.
# `work` is intentionally absent — work items live at <workspace>/work/ (sibling of the wiki),
# so its index is written outside the vault. See scan_work() / main().
CATEGORY_INDEX_FILES = {
    "concept":      "concepts/index.md",
    "source":       "sources/index.md",
    "adr":          "adrs/index.md",
    "architecture": "architecture/index.md",
    "dependency":   "dependencies/index.md",
}
GENERATED_FILES = {"index.md", "log.md"} | set(CATEGORY_INDEX_FILES.values())

# Filenames (without .md) that are sub-pages, not main navigation entries
SUBPAGE_STEMS = {"api", "patterns", "issues", "context", "flows", "work"}
CATEGORY_DIRS = {
    "apps": "app",
    "packages": "package",
    "domains": "domain",
    "concepts": "concept",
    "dependencies": "dependency",
    "work": "work",
    "sources": "source",
    "architecture": "architecture",
    "adrs": "adr",
}
CATEGORY_LABELS = {
    "architecture": "Architecture",
    "app": "App",
    "package": "Package",
    "domain": "Domain",
    "concept": "Concept",
    "dependency": "Dependency",
    "work": "Work",
    "adr": "ADR",
    "source": "Source",
    "other": "Other",
}


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def infer_title(path, fm):
    if "title" in fm:
        return fm["title"]
    return path.stem.replace("-", " ").replace("_", " ").title()


def scan_vault(wiki):
    vault = wiki
    if not vault.exists():
        print(f"[error] {vault} not found", file=sys.stderr)
        sys.exit(1)

    pages = defaultdict(list)
    for md in sorted(vault.rglob("*.md")):
        rel = md.relative_to(vault)
        if rel.name in GENERATED_FILES:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        category = fm.get("category")
        if not category and len(rel.parts) > 1:
            category = CATEGORY_DIRS.get(rel.parts[0], "other")
        category = category or "other"
        pages[category].append(
            {
                "path": str(rel).replace("\\", "/"),
                "title": infer_title(md, fm),
                "summary": fm.get("summary", ""),
                "tags": fm.get("tags", ""),
                "sources": fm.get("sources", ""),
                "updated": fm.get("updated", ""),
                "status": fm.get("status", ""),  # issue, roadmap, adr
            }
        )

    for cat in pages:
        pages[cat].sort(key=lambda p: p["title"].lower())
    return pages


def scan_work(workspace):
    """Scan <workspace>/work/ for work-item pages.

    Returns a list of entries shaped like scan_vault() values. Paths are
    workspace-relative (e.g. "work/2026-05-03-foo.md") so they render as
    workspace-rooted wikilinks. Skips the generated work index, dotfiles,
    and the archived/ sub-namespace (owned by lattice-work lifecycle).
    """
    work_dir = workspace / "work"
    if not work_dir.exists():
        return []
    entries = []
    for md in sorted(work_dir.rglob("*.md")):
        rel = md.relative_to(workspace)
        if rel.name == "index.md":
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        if len(rel.parts) >= 2 and rel.parts[1] == "archived":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        entries.append(
            {
                "path": str(rel).replace("\\", "/"),
                "title": infer_title(md, fm),
                "summary": fm.get("summary", ""),
                "tags": fm.get("tags", ""),
                "sources": fm.get("sources", ""),
                "updated": fm.get("updated", ""),
                "status": fm.get("status", ""),
            }
        )
    entries.sort(key=lambda p: p["title"].lower())
    return entries


def _entry_link(path, title):
    """Build an Obsidian wikilink for a page entry.

    Wiki entries have wiki-relative paths (e.g. "concepts/foo.md") and need
    the "wiki/" prefix because the Obsidian vault opens at the workspace root.
    Work entries are scanned from <workspace>/work/ and already arrive as
    workspace-relative paths (e.g. "work/2026-05-03-foo.md") — no prefix.
    """
    stem = path[:-3] if path.endswith(".md") else path
    target = stem if stem.startswith("work/") else f"wiki/{stem}"
    return f"[[{target}|{title}]]"


def render_index(pages, wiki_name, vault_name):
    today = dt.date.today().isoformat()
    nav_total = sum(
        sum(1 for e in pages.get(c, []) if Path(e["path"]).stem not in SUBPAGE_STEMS)
        for c in MAIN_INDEX_CATEGORIES
    )

    lines = [
        f"# Index — {wiki_name}",
        "",
        f"_Auto-generated {today} • {nav_total} navigation pages_",
        "",
        f"> Navigation index for `{vault_name}/`. Updated by `scripts/update_index.py`",
        "> or during `/lattice-wiki:scan` / `/lattice-wiki:ingest`.",
        "> Answer queries by reading this file first, then open relevant package/domain pages.",
        "",
    ]

    for cat in MAIN_INDEX_CATEGORIES:
        entries = pages.get(cat, [])
        if not entries:
            continue
        label = CATEGORY_LABELS.get(cat, cat.capitalize())
        nav_entries = [e for e in entries if Path(e["path"]).stem not in SUBPAGE_STEMS]
        if not nav_entries:
            continue
        lines.append(f"## {label} ({len(nav_entries)})")
        lines.append("")
        for e in nav_entries:
            summary = f" — {e['summary']}" if e["summary"] else ""
            link = _entry_link(e["path"], e["title"])
            lines.append(f"- {link}{summary}")
        lines.append("")

    # ## More — links to category sub-indexes
    # These categories always appear even at 0 pages (browsing entrypoints).
    # "work" stays conditional — it is a workspace namespace, not a wiki entrypoint.
    _ALWAYS_IN_MORE = {"architecture", "source", "concept", "adr", "dependency"}
    more_links = []
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if entries or cat in _ALWAYS_IN_MORE:
            label = CATEGORY_LABELS.get(cat, cat.capitalize())
            stem = fname[:-3]  # strip .md
            more_links.append(f"- [[wiki/{stem}]] — {label} ({len(entries)} pages)")
    # Work index lives at <workspace>/work/index.md (sibling of the wiki),
    # so its wikilink is workspace-rooted, not wiki-rooted.
    work_entries = pages.get("work", [])
    if work_entries:
        more_links.append(
            f"- [[work/index]] — {CATEGORY_LABELS['work']} ({len(work_entries)} pages)"
        )
    if more_links:
        lines.append("## More")
        lines.append("")
        lines.extend(more_links)
        lines.append("")

    return "\n".join(lines)


def render_category_index(entries, category, label, vault_name, location=None):
    """Render a standalone category sub-index file.

    `location` is the directory name shown in the summary text (e.g. "wiki" for
    in-vault sub-indexes, "work" for the workspace-rooted work index).
    Defaults to `vault_name`.
    """
    today = dt.date.today().isoformat()
    loc = location or vault_name
    lines = [
        "---",
        f"title: {label} Index",
        "category: index",
        f"summary: Auto-generated sub-index of all {category} pages in {loc}/.",
        f"updated: {today}",
        "---",
        "",
        f"# {label} Index",
        "",
        f"_Auto-generated {today} • {len(entries)} pages_",
        "",
        f"> Sub-index of all `{category}` pages in `{loc}/`.",
        "> Generated by `scripts/update_index.py`.",
        "",
        f"## {label} ({len(entries)})",
        "",
    ]
    for e in sorted(entries, key=lambda x: x["title"].lower()):
        summary = f" — {e['summary']}" if e["summary"] else ""
        link = _entry_link(e["path"], e["title"])
        meta = []
        if e["status"]:
            meta.append(e["status"])
        if e["sources"]:
            meta.append(f"{e['sources']} sources")
        if e["updated"]:
            meta.append(f"upd {e['updated']}")
        meta_str = f" _({' · '.join(meta)})_" if meta else ""
        lines.append(f"- {link}{summary}{meta_str}")
    lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Regenerate wiki/index.md")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        wiki, _ = resolve_wiki_and_repo()
        pages = scan_vault(wiki)
        # Work items live at <workspace>/work/, sibling of the wiki.
        work_entries = scan_work(wiki.parent)
        if work_entries:
            pages["work"] = work_entries
        vault = wiki
        content = render_index(pages, wiki.name, vault.name)
    except SystemExit:
        raise
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    total = sum(len(v) for v in pages.values())
    summary = {
        "status": "ok",
        "wiki": str(wiki),
        "total_pages": total,
        "by_category": {k: len(v) for k, v in pages.items()},
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        if args.json:
            summary["content_preview"] = content[:500]
            print(json.dumps(summary, indent=2))
        else:
            print(content)
        return

    index_path = wiki / "index.md"
    try:
        index_path.write_text(content, encoding="utf-8")
    except OSError as e:
        if args.json:
            print(json.dumps({"status": "error", "message": f"failed to write {index_path}: {e}"}))
        else:
            print(f"[error] failed to write {index_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # Write category sub-indexes inside the wiki.
    written_cat_indexes = []
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if not entries:
            continue
        label = CATEGORY_LABELS.get(cat, cat.capitalize())
        cat_content = render_category_index(entries, cat, label, vault.name)
        cat_path = vault / fname
        cat_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            cat_path.write_text(cat_content, encoding="utf-8")
        except OSError as e:
            if args.json:
                print(json.dumps({"status": "error", "message": f"failed to write {cat_path}: {e}"}))
            else:
                print(f"[warn] failed to write {cat_path}: {e}", file=sys.stderr)
        else:
            written_cat_indexes.append(fname)
            if not args.json:
                print(f"[ok] wrote {cat_path} ({len(entries)} pages)")

    # Write the work index at <workspace>/work/index.md (sibling of the wiki).
    if work_entries:
        work_index_path = wiki.parent / "work" / "index.md"
        work_index_content = render_category_index(
            work_entries, "work", CATEGORY_LABELS["work"], vault.name, location="work"
        )
        work_index_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            work_index_path.write_text(work_index_content, encoding="utf-8")
        except OSError as e:
            if args.json:
                print(json.dumps({"status": "error", "message": f"failed to write {work_index_path}: {e}"}))
            else:
                print(f"[warn] failed to write {work_index_path}: {e}", file=sys.stderr)
        else:
            written_cat_indexes.append("work/index.md")
            if not args.json:
                print(f"[ok] wrote {work_index_path} ({len(work_entries)} pages)")

    summary["index_path"] = str(index_path)
    summary["category_indexes_written"] = written_cat_indexes
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"[ok] wrote {index_path} ({total} pages)")


if __name__ == "__main__":
    main()
