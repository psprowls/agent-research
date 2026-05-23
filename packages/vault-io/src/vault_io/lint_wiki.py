#!/usr/bin/env python3
"""
lint_wiki.py — Health-check a Code Wiki.

Mechanical checks:
  - orphans, broken wikilinks, stale pages, missing frontmatter
  - duplicate titles, log gaps
  - code-drift (monorepo-specific): packages on disk vs. in the vault

Discovers wiki and repo locations from the resolved graph-wiki workspace.

This file is a thin dispatcher. Per-group checks live under ``lint/``:
``container``, ``file_map``, ``domain``, ``source_sync``, ``package_sync``.
Each module exposes a ``check(...)`` entry point and a ``GROUP`` constant.

Usage:
    python lint_wiki.py
    python lint_wiki.py --stale-days 60 --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

# Import discover_workspaces from sibling scan_monorepo
try:
    from vault_io.scan_monorepo import discover_workspaces as _scan_discover
    from vault_io.scan_monorepo import unscope as _unscope
except ImportError:
    _scan_discover = None
    _unscope = lambda n: n  # noqa: E731 — fallback, code-drift check is skipped anyway

from vault_io._workspace import resolve_wiki_and_repo
from vault_io.layout_io import read_layout
from vault_io.lint.common import (
    LOG_ENTRY_RE,
    WIKILINK_RE,
    parse_frontmatter,
    strip_code,
    strip_frontmatter,
)
from vault_io.lint.container import check as check_container_drift
from vault_io.lint.dependency import check as check_dependency_layer
from vault_io.lint.domain import check as check_domain_placement
from vault_io.lint.file_map import check as check_file_map_drift
from vault_io.lint.package_sync import check as check_package_sync_drift
from vault_io.lint.source_sync import check as check_source_sync_drift
from vault_io.lint.workflow_hints import check as check_workflow_hints

_SKIPPED: dict = {"skipped": True}

OPTIONAL_GROUPS = {"dependency_layer"}
LINTED_TOPS = {"wiki", "work"}
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


def scan(wiki, stale_days, log_gap_days, repo_path=None, optional_checks=None):
    if not wiki.exists():
        raise SystemExit(f"[error] {wiki} not found")
    workspace = wiki.parent

    pages = {}
    link_targets = set()
    inbound = defaultdict(set)
    outbound = defaultdict(set)

    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
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
        # work/archived/ items are valid link targets but excluded from orphan/stale checks
        if top == "work" and len(rel.parts) >= 2 and rel.parts[1] == "archived":
            link_targets.add(key)
            continue
        # Add to link_targets regardless of whether it's an index page
        link_targets.add(key)
        # Skip adding index.md to pages dict for orphan/stale/frontmatter checks
        if rel.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        pages[key] = {
            "path": key + ".md",
            "fm": fm,
            "text": text,
            "linted": top in LINTED_TOPS,
            "is_work": top == "work",
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
            elif (target + "/" + Path(target).name) in link_targets:
                # [[<container>/<name>]] resolves to <container>/<name>/<name>.md
                # (the folder-shorthand form for apps, packages, domains).
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
    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
        if rel.name != "index.md":
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        # Schema files are excluded symmetrically (defensive — index.md
        # filter above already gates this, but keeps both loops parallel).
        if rel.name in SCHEMA_FILENAMES:
            continue
        top = rel.parts[0] if rel.parts else ""
        if top == "work" and len(rel.parts) >= 2 and rel.parts[1] == "archived":
            continue
        idx_key = str(rel).replace("\\", "/")[:-3]
        text = md.read_text(encoding="utf-8", errors="replace")
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

    orphans = sorted(k for k, p in pages.items() if p["linted"] and not p["is_work"] and not inbound.get(k))
    broken_links = []
    for src, targets in outbound.items():
        for t in targets:
            if t.startswith("__BROKEN__:"):
                broken_links.append((src, t.split(":", 1)[1]))
    broken_links.sort()

    stale = []
    missing_fm = []
    missing_tokens = []
    titles = defaultdict(list)
    for key, page in pages.items():
        if not page["linted"]:
            continue
        fm = page["fm"]
        title = fm.get("title") or Path(key).name
        titles[title].append(key)
        required = {"title", "category", "summary"}
        if not required.issubset(fm.keys()):
            missing_fm.append(key)
        if "tokens" not in fm:
            missing_tokens.append(key)
        updated = fm.get("updated")
        if updated:
            try:
                d = dt.date.fromisoformat(updated)
                if d < stale_cutoff:
                    stale.append((key, updated))
            except ValueError:
                pass
    duplicate_titles = {t: ks for t, ks in titles.items() if len(ks) > 1}

    log_path = wiki / "log.md"
    log_gap = None
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        dates = [dt.date.fromisoformat(m) for m in LOG_ENTRY_RE.findall(log_text)]
        if dates:
            last = max(dates)
            gap = (today - last).days
            if gap > log_gap_days:
                log_gap = {"last_entry": last.isoformat(), "days_ago": gap}
        else:
            log_gap = {"last_entry": None, "days_ago": None}

    # Code-drift check
    code_drift = _SKIPPED
    if repo_path and _scan_discover:
        try:
            layout = read_layout(wiki / "CLAUDE.md")
            pinned_containers = layout.get("containers") if layout else None
            workspaces = _scan_discover(repo_path, pinned_containers=pinned_containers)
            # Normalize scoped names (``@psprowls/foo`` -> ``foo``) so the diff
            # compares like-for-like against vault slugs/titles.
            disk_names = {_unscope(w["name"]) for w in workspaces}
            vault_pkg_pages = {
                k: p
                for k, p in pages.items()
                if p["fm"].get("category") in ("package", "app") and Path(k).name == "overview.md"
            }
            vault_names = {Path(k).name for k, p in vault_pkg_pages.items()}
            # Pages declaring ``status: planned`` are deliberately seeded
            # before the workspace exists on disk (e.g. ``graph-graph``).
            # Surface them
            # separately under ``planned_in_vault`` instead of drowning real
            # drift under false positives.
            planned_names = {Path(k).name for k, p in vault_pkg_pages.items() if p["fm"].get("status") == "planned"}
            code_drift = {
                "packages_on_disk": len(disk_names),
                "packages_in_vault": len(vault_names),
                "missing_in_vault": sorted(disk_names - vault_names),
                "orphaned_in_vault": sorted((vault_names - disk_names) - planned_names),
                "planned_in_vault": sorted(planned_names),
            }
            # Check exports drift (apps usually don't define exports, so skip them)
            name_to_ws = {_unscope(w["name"]): w for w in workspaces}
            exports_drift = []
            for k, p in vault_pkg_pages.items():
                if p["fm"].get("category") == "app":
                    continue
                title = Path(k).name
                ws = name_to_ws.get(title)
                if not ws:
                    continue
                vault_exports = p["fm"].get("exports", "").strip()
                disk_exports = ws.get("exports", [])
                if vault_exports and disk_exports:
                    # Naive: if frontmatter is set but differs in count
                    vault_list = [x.strip() for x in vault_exports.strip("[]").split(",") if x.strip()]
                    if len(vault_list) != len(disk_exports):
                        exports_drift.append(
                            {
                                "page": k,
                                "vault_count": len(vault_list),
                                "disk_count": len(disk_exports),
                            }
                        )
            code_drift["exports_drift"] = exports_drift
        except Exception as e:
            code_drift = {"error": str(e)}

    container_drift = _SKIPPED
    source_sync_drift = _SKIPPED
    file_map_drift = _SKIPPED
    if repo_path:
        container_drift = check_container_drift(repo_path, wiki)
        source_sync_drift = check_source_sync_drift(repo_path, wiki)
        file_map_drift = check_file_map_drift(repo_path, pages)

    package_sync_drift = check_package_sync_drift(repo_path, wiki) if repo_path else _SKIPPED

    domain_placement = check_domain_placement(pages)
    workflow_hints_issues = check_workflow_hints(pages, workspace)

    # Optional check groups (gated behind --check). Default off; pass
    # --check dependency_layer to enable.
    enabled_optional = optional_checks or set()
    workspaces_for_lint = None
    if "dependency_layer" in enabled_optional and repo_path and _scan_discover:
        try:
            layout = read_layout(wiki / "CLAUDE.md")
            pinned_containers = layout.get("containers") if layout else None
            workspaces_for_lint = _scan_discover(repo_path, pinned_containers=pinned_containers)
        except Exception:
            workspaces_for_lint = None

    dependency_layer = (
        check_dependency_layer(pages, workspaces=workspaces_for_lint)
        if "dependency_layer" in enabled_optional
        else None
    )

    return {
        "wiki": str(wiki),
        "total_pages": len(pages),
        "orphans": orphans,
        "broken_links": broken_links,
        "stale": stale,
        "missing_frontmatter": sorted(missing_fm),
        "missing_tokens": sorted(missing_tokens),
        "duplicate_titles": duplicate_titles,
        "log_gap": log_gap,
        "code_drift": code_drift,
        "container_drift": container_drift,
        "source_sync_drift": source_sync_drift,
        "file_map_drift": file_map_drift,
        "package_sync_drift": package_sync_drift,
        "domain_placement": domain_placement,
        "dependency_layer": dependency_layer,
        "workflow_hints": workflow_hints_issues,
    }


def print_report(r):
    print(f"Code Wiki health check — {r['wiki']}")
    print(f"Total pages: {r['total_pages']}")
    print()

    def header(label, count):
        sym = "OK" if count == 0 else "WARN"
        print(f"[{sym}] {label}: {count}")

    header("orphan pages", len(r["orphans"]))
    for p in r["orphans"][:20]:
        print(f"   - {p}")
    print()

    header("broken wikilinks", len(r["broken_links"]))
    for src, tgt in r["broken_links"][:20]:
        print(f"   - {src} -> [[{tgt}]]")
    print()

    header("stale pages", len(r["stale"]))
    for p, d in r["stale"][:20]:
        print(f"   - {p} (updated {d})")
    print()

    header("pages missing frontmatter", len(r["missing_frontmatter"]))
    for p in r["missing_frontmatter"][:20]:
        print(f"   - {p}")
    print()

    header("pages missing tokens field", len(r["missing_tokens"]))
    for p in r["missing_tokens"][:20]:
        print(f"   - {p}")
    if r["missing_tokens"]:
        print("   Run: python -m vault_io.update_tokens")
    print()

    header("duplicate titles", len(r["duplicate_titles"]))
    for title, keys in list(r["duplicate_titles"].items())[:10]:
        print(f"   - '{title}': {keys}")
    print()

    gap = r["log_gap"]
    if gap:
        print(f"[WARN] log gap: last entry {gap['last_entry']} ({gap['days_ago']} days ago)")
    else:
        print("[OK] log gap: recent")
    print()

    cd = r.get("code_drift")
    if isinstance(cd, dict) and cd.get("skipped"):
        print("[SKIP] code drift check (no repo root discovered)")
    elif cd:
        if cd.get("error"):
            print(f"[WARN] code drift check failed: {cd['error']}")
        else:
            print(f"Code drift: {cd['packages_on_disk']} packages on disk, {cd['packages_in_vault']} in vault")
            mw = cd.get("missing_in_vault", [])
            print(f"[{'WARN' if mw else 'OK'}] packages missing from vault: {len(mw)}")
            for n in mw[:10]:
                print(f"   + {n}  (run /graph-wiki:scan)")
            ow = cd.get("orphaned_in_vault", [])
            print(f"[{'WARN' if ow else 'OK'}] vault pages for non-existent packages: {len(ow)}")
            for n in ow[:10]:
                print(f"   - {n}  (archive or delete)")
            ed = cd.get("exports_drift", [])
            print(f"[{'WARN' if ed else 'OK'}] exports-frontmatter drift: {len(ed)}")
            for d in ed[:10]:
                print(f"   ~ {d['page']} (vault: {d['vault_count']}, disk: {d['disk_count']})")
    print()

    cdrift = r.get("container_drift")
    if isinstance(cdrift, dict) and cdrift.get("skipped"):
        print("[SKIP] container drift check (no repo root discovered)")
    else:
        header("container drift issues", len(cdrift))
        for issue in cdrift[:20]:
            print(f"   - {issue}")
    print()

    ddrift = r.get("source_sync_drift")
    if isinstance(ddrift, dict) and ddrift.get("skipped"):
        print("[SKIP] source sync drift check (no repo root discovered)")
    else:
        header("source sync drift issues", len(ddrift))
        for issue in ddrift[:20]:
            print(f"   - {issue}")
    print()

    fmdrift = r.get("file_map_drift")
    if isinstance(fmdrift, dict) and fmdrift.get("skipped"):
        print("[SKIP] file map drift check (no repo root discovered)")
    else:
        header("file map drift issues", len(fmdrift))
        for issue in fmdrift[:20]:
            print(f"   - {issue}")
    print()

    psd = r.get("package_sync_drift")
    if isinstance(psd, dict) and psd.get("skipped"):
        print("[SKIP] package sync drift check (no repo root discovered)")
    else:
        header("package sync drift", len(psd))
        for issue in psd[:20]:
            print(f"   - {issue}")
    print()

    dplace = r.get("domain_placement", [])
    header("domain placement issues", len(dplace))
    for issue in dplace[:20]:
        print(f"   - {issue}")
    print()

    wh = r.get("workflow_hints", [])
    header("workflow_hints missing sub-pages", len(wh))
    for issue in wh[:20]:
        print(f"   - {issue}")
    print()

    findings = r.get("dependency_layer")
    if findings is None:
        print("[SKIP] dependency_layer (pass --check dependency_layer to enable)")
    else:
        header("dependency_layer findings", len(findings))
        for f in findings[:20]:
            print(f"   - {f}")
    print()


def main():
    p = argparse.ArgumentParser(description="Lint a Code Wiki (with code-drift detection)")
    p.add_argument("--stale-days", type=int, default=90)
    p.add_argument("--log-gap-days", type=int, default=14)
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--check",
        default="",
        help=(
            "Comma-separated optional check groups to enable in addition to the "
            "default set. Available: " + ",".join(sorted(OPTIONAL_GROUPS))
        ),
    )
    args = p.parse_args()

    optional_checks: set[str] = set()
    if args.check:
        for name in args.check.split(","):
            name = name.strip()
            if not name:
                continue
            if name not in OPTIONAL_GROUPS:
                print(
                    f"[error] unknown --check group '{name}' (known: {','.join(sorted(OPTIONAL_GROUPS))})",
                    file=sys.stderr,
                )
                sys.exit(2)
            optional_checks.add(name)

    wiki, repo_path = resolve_wiki_and_repo()
    report = scan(
        wiki,
        stale_days=args.stale_days,
        log_gap_days=args.log_gap_days,
        repo_path=repo_path,
        optional_checks=optional_checks,
    )
    if args.json:
        print(json.dumps(report, indent=2, default=list))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
