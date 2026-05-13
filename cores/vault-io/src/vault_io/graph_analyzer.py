#!/usr/bin/env python3
"""
graph_analyzer.py — Analyze the wikilink graph of a Code Wiki.

Wiki path is discovered automatically via `lattice-workspace`
(defaults to `<repo>/lattice/wiki/`).

Usage:
    python graph_analyzer.py
    python graph_analyzer.py --json --top 20
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

# Share the scope-normalization helper with scan_monorepo / lint_wiki so
# ``depends_on: [@scope/foo]`` entries resolve to ``packages/foo`` pages.
try:
    from vault_io.scan_monorepo import unscope as _unscope
except ImportError:
    _unscope = lambda n: n  # noqa: E731

from vault_io._workspace import resolve_wiki_and_repo

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LIST_ITEM_RE = re.compile(r"^\s+-\s*[\"']?(.+?)[\"']?\s*$")


def _parse_frontmatter_lists(text, keys):
    """Extract block-list YAML values for ``keys`` from a page's frontmatter.

    The other scripts in this skill use a flat line-based parser that silently
    drops YAML list values. Graph analysis needs ``depends_on`` as actual edges,
    so this helper understands the ``key:\\n  - item\\n  - item`` pattern for
    the requested keys only.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    result = {k: [] for k in keys}
    active = None
    for line in m.group(1).splitlines():
        if active is not None:
            item = LIST_ITEM_RE.match(line)
            if item:
                result[active].append(item.group(1))
                continue
            active = None  # list block ended
        stripped = line.strip()
        if ":" in stripped and not stripped.startswith("#"):
            k, _, v = stripped.partition(":")
            k = k.strip()
            if k in keys and v.strip() == "":
                active = k
    return result


def build_graph(wiki):
    vault = wiki
    if not vault.exists():
        raise SystemExit(f"[error] {vault} not found")
    vault_prefix = vault.name + "/"
    nodes = set()
    out = defaultdict(set)
    inb = defaultdict(set)
    stems = {}

    for md in vault.rglob("*.md"):
        rel = md.relative_to(vault)
        if rel.name in {"index.md", "log.md"}:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        key = str(rel).replace("\\", "/")[:-3]
        nodes.add(key)
        stems[Path(key).name] = key

    for md in vault.rglob("*.md"):
        rel = md.relative_to(vault)
        if any(p.startswith(".") for p in rel.parts):
            continue
        key = str(rel).replace("\\", "/")[:-3]
        is_index = rel.name in {"index.md", "log.md"}
        text = md.read_text(encoding="utf-8", errors="replace")
        for m in WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.endswith(".md"):
                target = target[:-3]
            # Strip workspace-root prefix (e.g. "wiki/") so ADR-0015-form
            # wikilinks like [[wiki/packages/foo/api]] resolve to vault-relative keys.
            if target.startswith(vault_prefix):
                target = target[len(vault_prefix):]

            resolved = None
            if target in nodes:
                resolved = target
            elif (target + "/" + Path(target).name) in nodes:
                # [[<container>/<name>]] resolves to <container>/<name>/<name>.md
                # (folder-shorthand for apps, packages, domains).
                resolved = target + "/" + Path(target).name
            elif Path(target).name in stems:
                resolved = stems[Path(target).name]

            if resolved is None:
                continue
            if not is_index:
                out[key].add(resolved)
            inb[resolved].add(key)

        if is_index:
            continue

        # Treat ``depends_on:`` frontmatter entries as graph edges. Without
        # this, package pages that cross-reference each other only through
        # frontmatter (the convention in this skill) appear as orphans.
        fm_lists = _parse_frontmatter_lists(text, ("depends_on",))
        for dep in fm_lists.get("depends_on", ()):
            slug = _unscope(dep)
            resolved = stems.get(slug)
            if resolved and resolved != key:
                out[key].add(resolved)
                inb[resolved].add(key)

    return nodes, out, inb


def connected_components(nodes, out, inb):
    adj = defaultdict(set)
    for n in nodes:
        adj[n] |= out.get(n, set())
        adj[n] |= inb.get(n, set())
    seen = set()
    components = []
    for n in nodes:
        if n in seen:
            continue
        stack = [n]
        comp = set()
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            comp.add(v)
            stack.extend(adj[v] - seen)
        components.append(comp)
    components.sort(key=len, reverse=True)
    return components


def analyze(wiki, top):
    nodes, out, inb = build_graph(wiki)
    hubs_out = sorted(nodes, key=lambda n: len(out.get(n, set())), reverse=True)[:top]
    hubs_in = sorted(nodes, key=lambda n: len(inb.get(n, set())), reverse=True)[:top]
    orphans = sorted(n for n in nodes if not inb.get(n))
    sinks = sorted(n for n in nodes if not out.get(n))
    comps = connected_components(nodes, out, inb)
    return {
        "total_pages": len(nodes),
        "total_edges": sum(len(v) for v in out.values()),
        "top_outbound_hubs": [{"page": h, "outbound": len(out.get(h, set()))} for h in hubs_out],
        "top_inbound_hubs": [{"page": h, "inbound": len(inb.get(h, set()))} for h in hubs_in],
        "orphans": orphans,
        "sinks": sinks,
        "components": [{"size": len(c), "sample": sorted(c)[:5]} for c in comps[:10]],
        "component_count": len(comps),
    }


def main():
    p = argparse.ArgumentParser(description="Analyze the wikilink graph of a Code Wiki")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    wiki, _ = resolve_wiki_and_repo()
    r = analyze(wiki, args.top)

    if args.json:
        print(json.dumps(r, indent=2, default=list))
        return

    print(f"Code Wiki graph — {r['total_pages']} pages, {r['total_edges']} links")
    print(f"Connected components: {r['component_count']}")
    print()
    print("Top outbound hubs:")
    for h in r["top_outbound_hubs"]:
        print(f"  - {h['page']}  ({h['outbound']} out)")
    print()
    print("Top inbound hubs:")
    for h in r["top_inbound_hubs"]:
        print(f"  - {h['page']}  ({h['inbound']} in)")
    print()
    print(f"Orphans (no inbound): {len(r['orphans'])}")
    for o in r["orphans"][:10]:
        print(f"  - {o}")
    print()
    print(f"Sinks (no outbound): {len(r['sinks'])}")
    for s in r["sinks"][:10]:
        print(f"  - {s}")


if __name__ == "__main__":
    main()
