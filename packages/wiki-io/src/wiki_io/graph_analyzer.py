"""
graph_analyzer.py — Analyze the wikilink graph of a Code Wiki.

Import-only library module used by plugin and CLI delivery surfaces.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from wiki_io.frontmatter import parse as parse_page_frontmatter

# Share the scope-normalization helper with scan_monorepo / lint_wiki so
# ``depends_on: [@scope/foo]`` entries resolve to ``packages/foo`` pages.
try:
    from wiki_io.scan_monorepo import unscope as _unscope
except ImportError:
    _unscope = lambda n: n  # noqa: E731

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


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
            # wikilinks like [[packages/foo/api]] resolve to vault-relative keys.
            if target.startswith(vault_prefix):
                target = target[len(vault_prefix) :]

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
        fm, _err = parse_page_frontmatter(text)
        deps = fm.get("depends_on") or []
        if isinstance(deps, str):
            deps = [deps]
        for dep in deps:
            slug = _unscope(str(dep))
            resolved = stems.get(slug)
            if resolved and resolved != key:
                out[key].add(resolved)
                inb[resolved].add(key)

    return nodes, out, inb


def connected_components(nodes, out, inb):
    adj = defaultdict(set)
    for n in nodes:
        adj[n] |= out.get(n, set()) & nodes  # only follow edges to real nodes
        adj[n] |= inb.get(n, set()) & nodes  # only accept inbound from real nodes
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
