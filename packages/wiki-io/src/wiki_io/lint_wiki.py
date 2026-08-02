"""
lint_wiki.py — canonical mechanical scanner for a Code Wiki.

mechanical_scan(wiki, stale_days, log_gap_days) walks the wiki tree, builds
the wikilink graph, and detects orphans, broken links, stale pages, missing
frontmatter/tokens, source-path drift, duplicate titles, and log gaps. It is
the single source of truth for the mechanical findings.

The whole-wiki aggregation that consumes it (scan/print_report — code drift,
per-group drift checks, fail-soft parity wrappers) lives in
graph_wiki_core.commands.lint_mechanical, the single lint aggregator shared
by ``gw lint`` and the plugin lint script. Per-group checks live under
``lint/`` (``file_map``, ``domain``, ``package_sync``, ...), each exposing a
``check(...)`` entry point.

Import-only library module; delivery surfaces pass resolved wiki paths.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from pathlib import Path

from wiki_io.entity_writer import ADMITTED_KINDS
from wiki_io.frontmatter import parse as parse_page_frontmatter
from wiki_io.lint.common import (
    LOG_ENTRY_RE,
    WIKILINK_RE,
    strip_code,
    strip_frontmatter,
)

# Every real top-level vault dir under the wiki root. Walking from the wiki
# (not the workspace) means a page's top path-part is its category dir, so
# LINTED_TOPS must enumerate them all to keep the same pages linted as before.
LINTED_TOPS = {"concepts", "adrs", "sources", "entities", "proposals", "work"}
# Tool-schema files (emitted by init_vault.py per the --tool flag). Not wiki
# content pages — exclude at any depth from page enumeration and from the
# index-link parser. See plan 260521-gc0 (decision: any-depth, forward-compat).
SCHEMA_FILENAMES = {"CLAUDE.md", "AGENTS.md"}


def _is_placeholder_target(target: str) -> bool:
    """Check if a wikilink target is a placeholder/template token.

    Placeholder targets contain template tokens like ..., <name>, etc.
    and should not be treated as broken links.

    Args:
        target: The wikilink target string (e.g., "wiki/packages/...")

    Returns:
        True if target contains placeholder markers (..., <, or >), False otherwise.
    """
    return "..." in target or "<" in target or ">" in target


def mechanical_scan(wiki, stale_days, log_gap_days):
    """Canonical mechanical lint pass shared by scan() and graph-wiki-core run_lint().

    Walks the wiki tree, builds the wikilink graph, and detects orphans, broken
    links, stale pages, missing frontmatter, missing tokens, source-path drift,
    duplicate titles, and log gaps. This is the single source of truth for the
    mechanical findings; both delivery surfaces consume its return dict.

    Returns a dict with keys: pages, orphans, broken_links, stale,
    missing_frontmatter, missing_tokens, source_path_drift, duplicate_titles,
    unparseable_frontmatter, log_gap, total_pages.
    """
    pages: dict = {}
    link_targets: set[str] = set()
    inbound: dict[str, set] = defaultdict(set)
    outbound: dict[str, set] = defaultdict(set)

    for md in wiki.rglob("*.md"):
        rel = md.relative_to(wiki)
        # Exclude any path that has a dotdir component (.graph/, .obsidian/, etc.)
        if any(part.startswith(".") for part in rel.parts):
            continue
        # Tool-schema files (CLAUDE.md, AGENTS.md) are not wiki pages and
        # also not wikilink targets — skip before link_targets is populated.
        if rel.name in SCHEMA_FILENAMES:
            continue
        if rel.name in {"log.md"}:
            continue
        top = rel.parts[0] if rel.parts else ""
        key = str(rel).replace("\\", "/")[:-3]
        # Per-item working-dir artifacts (work/<slug>/01-design-spec.md, etc.) are
        # pipeline scratch files referenced only via frontmatter path pointers
        # (spec_doc/plan_doc), never wikilinks -- not wiki pages, not link targets.
        # Only top-level work/<slug>.md pages (and _archive/, handled below) count.
        if top == "work" and len(rel.parts) >= 3 and rel.parts[1] != "_archive":
            continue
        # <dir>/_archive/ items are valid link targets but excluded from orphan/stale checks
        if len(rel.parts) >= 2 and rel.parts[1] == "_archive":
            link_targets.add(key)
            continue
        # Add to link_targets regardless of whether it's an index page
        link_targets.add(key)
        # Skip adding index.md to pages dict for orphan/stale/frontmatter checks
        if rel.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm, fm_error = parse_page_frontmatter(text)
        pages[key] = {
            "path": key + ".md",
            "fm": fm,
            "fm_error": fm_error,
            "text": text,
            "linted": top in LINTED_TOPS,
            "is_work": top == "work",
            "is_proposal": top == "proposals",
        }

    stems = {Path(k).name: k for k in pages}
    for key, page in pages.items():
        scan_text = strip_code(strip_frontmatter(page["text"]))
        for m in WIKILINK_RE.finditer(scan_text):
            target = m.group(1).strip()
            if target.endswith(".md"):
                target = target[:-3]
            if target in link_targets:
                outbound[key].add(target)
                inbound[target].add(key)
            elif (target + "/overview") in link_targets:
                # [[<container>/<name>]] resolves to <container>/<name>/overview.md
                resolved = target + "/overview"
                outbound[key].add(resolved)
                inbound[resolved].add(key)
            elif (target + "/" + Path(target).name) in link_targets:
                # Legacy: [[<container>/<name>]] resolves to <container>/<name>/<name>.md
                # (old naming convention — kept for backwards compat with existing links).
                resolved = target + "/" + Path(target).name
                outbound[key].add(resolved)
                inbound[resolved].add(key)
            elif "/" not in target and Path(target).name in stems:
                # Bare-filename shorthand: [[my-pkg]] resolves to any page named my-pkg.
                # Only applies when target has no path separator — explicit path forms
                # like [[../work/foo]] or [[work/foo]] must match exactly.
                resolved = stems[Path(target).name]
                outbound[key].add(resolved)
                inbound[resolved].add(key)
            else:
                if not _is_placeholder_target(target):
                    outbound[key].add(f"__BROKEN__:{target}")

    # Parse outbound links from index.md files so that:
    # (a) pages only linked from an index are not flagged as orphans, and
    # (b) broken links inside index.md files are reported.
    # Also retain each index.md's text/fm in index_pages so content checks
    # (e.g. obsidian_render) that have no reason to skip index.md can opt in —
    # unlike pages, index.md is intentionally excluded from orphan/stale/
    # frontmatter checks (see the `continue` above).
    index_pages: dict = {}
    for md in wiki.rglob("*.md"):
        rel = md.relative_to(wiki)
        if rel.name != "index.md":
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        # Schema files are excluded symmetrically (defensive — index.md
        # filter above already gates this, but keeps both loops parallel).
        if rel.name in SCHEMA_FILENAMES:
            continue
        if len(rel.parts) >= 2 and rel.parts[1] == "_archive":
            continue
        idx_key = str(rel).replace("\\", "/")[:-3]
        text = md.read_text(encoding="utf-8", errors="replace")
        index_pages[idx_key] = {
            "path": idx_key + ".md",
            "fm": parse_page_frontmatter(text)[0],
            "text": text,
        }
        scan_text = strip_code(strip_frontmatter(text))
        for m in WIKILINK_RE.finditer(scan_text):
            target = m.group(1).strip()
            if target.endswith(".md"):
                target = target[:-3]
            if target in link_targets:
                # Only count inbound from index if target is in pages dict
                # (so index-to-index links don't prevent orphan detection)
                if target in pages:
                    inbound[target].add(idx_key)
            elif (target + "/overview") in link_targets:
                resolved = target + "/overview"
                if resolved in pages:
                    inbound[resolved].add(idx_key)
            elif (target + "/" + Path(target).name) in link_targets:
                resolved = target + "/" + Path(target).name
                # Only count inbound from index if target is in pages dict
                if resolved in pages:
                    inbound[resolved].add(idx_key)
            elif "/" not in target and Path(target).name in stems:
                resolved = stems[Path(target).name]
                inbound[resolved].add(idx_key)
            else:
                if not _is_placeholder_target(target):
                    outbound[idx_key].add(f"__BROKEN__:{target}")

    today = dt.date.today()
    stale_cutoff = today - dt.timedelta(days=stale_days)

    orphans = sorted(
        k for k, p in pages.items() if p["linted"] and not p["is_work"] and not p["is_proposal"] and not inbound.get(k)
    )
    broken_links = []
    for src, targets in outbound.items():
        for t in targets:
            if t.startswith("__BROKEN__:"):
                broken_links.append((src, t.split(":", 1)[1]))
    broken_links.sort()

    stale = []
    missing_fm = []
    missing_tokens = []
    titles: dict[str, list[str]] = defaultdict(list)
    for key, page in pages.items():
        if not page["linted"]:
            continue
        fm = page["fm"]
        title = str(fm.get("title") or Path(key).name)
        titles[title].append(key)
        if fm.get("kind") in ADMITTED_KINDS:
            # Graph-derived entities/ pages use the entity frontmatter contract:
            # uri/kind are required. `title` is intentionally absent — the writer
            # never emits it (the H1 carries the entity name); requiring it here
            # would falsely flag every entity page as missing_frontmatter.
            if not {"uri", "kind"}.issubset(fm.keys()):
                missing_fm.append(key)
        elif page.get("is_proposal"):
            # Proposal contract: machine-written review-queue notes. upsert_proposal
            # always writes kind/mode/target_slug/status; they never carry
            # category/summary. See proposals.py.
            required = {"kind", "mode", "target_slug", "status"}
            if not required.issubset(fm.keys()):
                missing_fm.append(key)
            # Proposals accumulate `tokens` from the token pass; flag the gap so
            # new proposals surface until that pass runs (parity with curated pages).
            if "tokens" not in fm:
                missing_tokens.append(key)
        else:
            required = {"title", "category", "summary"}
            if not required.issubset(fm.keys()):
                missing_fm.append(key)
            if "tokens" not in fm:
                missing_tokens.append(key)
        updated = fm.get("updated")
        if updated:
            try:
                if isinstance(updated, dt.datetime):
                    d = updated.date()
                elif isinstance(updated, dt.date):
                    d = updated
                else:
                    d = dt.date.fromisoformat(str(updated))
                if d < stale_cutoff:
                    stale.append((key, str(updated)))
            except (ValueError, TypeError):
                pass
    duplicate_titles = {t: ks for t, ks in titles.items() if len(ks) > 1}
    unparseable = sorted((k, p["fm_error"]) for k, p in pages.items() if p["linted"] and p.get("fm_error"))

    log_path = wiki / "log.md"
    log_gap = None
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        dates = []
        for m in LOG_ENTRY_RE.findall(log_text):
            try:
                dates.append(dt.date.fromisoformat(m))
            except ValueError:
                pass  # malformed date in log header — skip
        if dates:
            last = max(dates)
            gap = (today - last).days
            if gap > log_gap_days:
                log_gap = {"last_entry": last.isoformat(), "days_ago": gap}
        else:
            log_gap = {"last_entry": None, "days_ago": None}

    # source_path drift: a source page whose workspace-relative raw/ source_path
    # no longer exists on disk (the file was archived). Conservative — skips
    # absolute paths and repo-relative in-repo doc paths (raw-source-archive
    # 2026-06-14).
    workspace_root = wiki.parent
    source_path_drift = []
    for key, page in pages.items():
        if not key.startswith("sources/"):
            continue
        sp = page["fm"].get("source_path")
        if not isinstance(sp, str) or not sp or sp.startswith("/") or not sp.startswith("raw/"):
            continue
        if not (workspace_root / sp).exists():
            source_path_drift.append(key)
    source_path_drift.sort()

    return {
        "pages": pages,
        "index_pages": index_pages,
        "orphans": orphans,
        "broken_links": broken_links,
        "stale": stale,
        "missing_frontmatter": sorted(missing_fm),
        "missing_tokens": sorted(missing_tokens),
        "source_path_drift": source_path_drift,
        "duplicate_titles": duplicate_titles,
        "unparseable_frontmatter": unparseable,
        "log_gap": log_gap,
        "total_pages": len(pages),
    }
