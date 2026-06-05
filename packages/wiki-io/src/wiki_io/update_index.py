"""
update_index.py — Regenerate category sub-indexes from vault page frontmatter.

The index is content-oriented: a catalog organized by category, with one-line
summaries read from each page's YAML frontmatter.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

from wiki_io.wikilinks import vault_wikilink
from workspace_io.paths import wiki_dir, work_dir

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
# `work` is intentionally absent — work items live at <workspace>/wiki/work/ (under the wiki root),
# so its index is written inside the vault. See scan_work() / update_index().
CATEGORY_INDEX_FILES = {
    "concept": "concepts/index.md",
    "source": "sources/index.md",
    "adr": "adrs/index.md",
    "architecture": "architecture/index.md",
}
GENERATED_FILES = {"index.md", "log.md"} | set(CATEGORY_INDEX_FILES.values())

# Filenames (without .md) that are sub-pages, not main navigation entries
SUBPAGE_STEMS = {"api", "patterns", "issues", "context", "flows", "work", "testing"}
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
    """Scan <workspace>/wiki/work/ for work-item pages.

    Returns a list of entries shaped like scan_vault() values. Paths are
    wiki-relative (e.g. "work/2026-05-03-foo.md") so they render as
    wiki-rooted wikilinks. Skips the generated work index, dotfiles,
    and the archived/ sub-namespace (owned by graph-wiki work lifecycle).
    """
    work_root = work_dir(workspace)
    if not work_root.exists():
        return []
    wiki = wiki_dir(workspace)
    entries = []
    for md in sorted(work_root.rglob("*.md")):
        rel = md.relative_to(wiki)
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



def render_index(pages, wiki_name, vault_name):
    today = dt.date.today().isoformat()
    nav_total = sum(
        sum(1 for e in pages.get(c, []) if Path(e["path"]).stem not in SUBPAGE_STEMS) for c in MAIN_INDEX_CATEGORIES
    )

    lines = [
        f"# Index — {wiki_name}",
        "",
        f"_Auto-generated {today} • {nav_total} navigation pages_",
        "",
        f"> Navigation index for `{vault_name}/`. Updated during command-layer scan/ingest flows.",
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
            link = vault_wikilink(e["path"], e["title"])
            lines.append(f"- {link}{summary}")
        lines.append("")

    # ## More — links to category sub-indexes
    # These categories always appear even at 0 pages (browsing entrypoints).
    # "work" stays conditional — it is its own namespace under the wiki.
    _ALWAYS_IN_MORE = {"architecture", "source", "concept", "adr"}
    more_links = []
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if entries or cat in _ALWAYS_IN_MORE:
            label = CATEGORY_LABELS.get(cat, cat.capitalize())
            more_links.append(f"- {vault_wikilink(fname)} — {label} ({len(entries)} pages)")
    # Work index lives under the wiki at work/index.md, so it shares the
    # single wiki-root-relative base with every other page.
    work_entries = pages.get("work", [])
    if work_entries:
        more_links.append(f"- {vault_wikilink('work/index')} — {CATEGORY_LABELS['work']} ({len(work_entries)} pages)")
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
        "> Generated by command-layer index maintenance.",
        "",
        f"## {label} ({len(entries)})",
        "",
    ]
    for e in sorted(entries, key=lambda x: x["title"].lower()):
        summary = f" — {e['summary']}" if e["summary"] else ""
        link = vault_wikilink(e["path"], e["title"])
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


def update_index(wiki: Path) -> None:
    """Regenerate per-folder category sub-indexes from vault frontmatter.

    Library entry point for use by ingest_work_item and other callers.

    Phase 45 D-02: the previous `wiki/index.md` write is removed; that file
    is now owned by `wiki_io.index_generator.generate_index`. This function
    continues to write the per-folder `*/index.md` sub-indexes and the
    workspace-rooted `work/index.md`.
    """
    pages = scan_vault(wiki)
    work_entries = scan_work(wiki.parent)
    if work_entries:
        pages["work"] = work_entries
    vault = wiki
    for cat, fname in CATEGORY_INDEX_FILES.items():
        entries = pages.get(cat, [])
        if not entries:
            continue
        label = CATEGORY_LABELS.get(cat, cat.capitalize())
        cat_content = render_category_index(entries, cat, label, vault.name)
        cat_path = vault / fname
        cat_path.parent.mkdir(parents=True, exist_ok=True)
        cat_path.write_text(cat_content, encoding="utf-8")
    if work_entries:
        work_index_path = work_dir(wiki.parent) / "index.md"
        work_index_content = render_category_index(
            work_entries, "work", CATEGORY_LABELS["work"], vault.name, location="work"
        )
        work_index_path.parent.mkdir(parents=True, exist_ok=True)
        work_index_path.write_text(work_index_content, encoding="utf-8")
