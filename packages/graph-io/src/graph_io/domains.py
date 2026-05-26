"""Domain emitter.

Reads `<repo_root>/domains.yaml` and emits:
  - Domain nodes (one per top-level key)
  - belongs_to_domain edges (Package -> Domain)
  - domain_contains_domain edges (Domain -> Domain, tree)

Cycle detection (Phase 31 D-15) skips ONLY cycle-participating
containment edges; the acyclic remainder is preserved.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import yaml
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import upsert
from graph_io.uri import RepoContext, domain_uri

_LOG = logging.getLogger("graph_io.domains")

_KNOWN_KEYS = frozenset({"packages", "parent", "description", "owner"})
_DOMAIN_KIND = "domain"
_BELONGS_TO_DOMAIN_KIND = "belongs_to_domain"
_DOMAIN_CONTAINS_DOMAIN_KIND = "domain_contains_domain"


class DomainYamlError(Exception):
    """Raised on unrecoverable domains.yaml parse error.

    The CLI surface maps this exception to exit code 4 (D-06,
    consistent with the Phase 28 schema-mismatch exit-code reuse).
    """
    exit_code: int = 4


def _load_domains_yaml(repo_root: Path) -> dict | None:
    """Return parsed domains.yaml as a dict, or None if the file is missing.

    Raises DomainYamlError on parse failure or non-mapping top-level.
    """
    path = repo_root / "domains.yaml"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise DomainYamlError(
            f"domains.yaml: YAML parse error: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise DomainYamlError(
            f"domains.yaml: top-level must be a mapping, got "
            f"{type(data).__name__}"
        )
    return data


def _known_packages(conn: sqlite3.Connection) -> list[tuple[str, str | None]]:
    """Return sorted [(pkg_name, pkg_rel)] from the Package nodes."""
    rows = conn.execute(
        "SELECT name, path FROM nodes WHERE kind='package' ORDER BY name"
    ).fetchall()
    return [(name, path) for name, path in rows]


def _detect_cycles(
    parent_map: dict[str, str],
) -> tuple[list[set[str]], set[str]]:
    """Return (sccs_size_gt_1, self_loops) for the (child -> parent) graph.

    self_loops is the set of domain names where parent_map[name] == name.
    sccs_size_gt_1 is a list of SCCs each containing > 1 distinct nodes.
    Singleton SCCs (the acyclic case) are NOT returned.
    """
    self_loops: set[str] = {
        n for n, p in parent_map.items() if n == p
    }
    # Build adjacency: child -> [parent] (excluding self-loops to keep
    # Tarjan focused on multi-node cycles; self-loops handled separately)
    nodes: set[str] = set()
    adj: dict[str, list[str]] = {}
    for child, parent in parent_map.items():
        if child == parent:
            continue
        nodes.add(child)
        nodes.add(parent)
        adj.setdefault(child, []).append(parent)
        adj.setdefault(parent, [])

    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    counter = [0]
    sccs: list[set[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = counter[0]
        lowlink[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in adj.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            component: set[str] = set()
            while True:
                w = stack.pop()
                on_stack.remove(w)
                component.add(w)
                if w == v:
                    break
            if len(component) > 1:
                sccs.append(component)

    for n in sorted(nodes):   # deterministic iteration
        if n not in index:
            strongconnect(n)

    # Sort SCCs by min member name for deterministic output
    sccs.sort(key=lambda s: min(s))
    return sccs, self_loops


def _emit_containment_edges(
    parent_map: dict[str, str],
    all_domain_names: set[str],
    edges_out: list[GraphEdge],
) -> None:
    """Emit domain_contains_domain edges, skipping cycle-participating
    edges and self-loops (D-15)."""
    sccs, self_loops = _detect_cycles(parent_map)

    # Build SCC membership map for O(1) "are both endpoints in same SCC" check
    scc_of: dict[str, int] = {}
    for i, scc in enumerate(sccs):
        for member in scc:
            scc_of[member] = i

    # Emit one warning per SCC of size > 1
    for scc in sccs:
        intra_count = sum(
            1 for child, parent in parent_map.items()
            if child in scc and parent in scc and child != parent
        )
        members_csv = ", ".join(sorted(scc))
        _LOG.warning(
            "domains.yaml: cycle detected involving domains: %s. "
            "Skipping %d domain_contains_domain edge(s); the acyclic remainder is preserved.",
            members_csv, intra_count,
        )

    # Emit one warning per self-loop
    for name in sorted(self_loops):
        _LOG.warning(
            "domains.yaml: domain '%s' declares itself as parent — skipping containment edge.",
            name,
        )

    # Emit containment edges, skipping cycle-participating ones
    for child, parent in parent_map.items():
        if child == parent:
            continue   # self-loop: warned above, edge skipped
        if child in scc_of and parent in scc_of and scc_of[child] == scc_of[parent]:
            continue   # intra-SCC edge: warned above, edge skipped
        if parent not in all_domain_names:
            _LOG.warning(
                "domains.yaml: domain '%s' has parent '%s' which is not a declared domain — skipping containment edge",
                child, parent,
            )
            continue
        edges_out.append(GraphEdge(
            src=(_DOMAIN_KIND, parent, None),
            dst=(_DOMAIN_KIND, child, None),
            kind=_DOMAIN_CONTAINS_DOMAIN_KIND,
            attrs={},
        ))


def emit(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    ctx: RepoContext,
    skip_dirs: frozenset[str],
) -> None:
    """Emit Domain nodes + belongs_to_domain + domain_contains_domain edges.

    Idempotent: re-running over the same domains.yaml produces the same
    edge set (upsert dedupes on (src, dst, kind)).

    Missing domains.yaml is NOT an error (DOMAIN-04 / D-03).
    """
    data = _load_domains_yaml(repo_root)
    if data is None:
        return

    known_pkgs = _known_packages(conn)
    known_names = {name for name, _rel in known_pkgs}
    known_name_to_rel = {name: rel for name, rel in known_pkgs}
    known_sorted_csv = ", ".join(sorted(known_names))

    nodes_out: list[GraphNode] = []
    edges_out: list[GraphEdge] = []
    parent_map: dict[str, str] = {}    # child -> parent
    all_domain_names: set[str] = set()

    for dom_name, dom_attrs in data.items():
        if not isinstance(dom_attrs, dict):
            _LOG.warning(
                "domains.yaml: domain '%s' must be a mapping, got %s — skipping",
                dom_name, type(dom_attrs).__name__,
            )
            continue
        pkgs = dom_attrs.get("packages")
        if pkgs is None:
            _LOG.warning(
                "domains.yaml: domain '%s' missing required 'packages:' field — skipping",
                dom_name,
            )
            continue
        if not isinstance(pkgs, list):
            _LOG.warning(
                "domains.yaml: domain '%s' has non-list 'packages:' field — skipping",
                dom_name,
            )
            continue

        for key in sorted(set(dom_attrs.keys()) - _KNOWN_KEYS):
            _LOG.warning(
                "domains.yaml: domain '%s' has unknown key '%s' — ignored",
                dom_name, key,
            )

        all_domain_names.add(dom_name)

        # Domain node
        dom_attrs_for_node: dict = {"uri": domain_uri(ctx, dom_name)}
        if "description" in dom_attrs:
            dom_attrs_for_node["description"] = dom_attrs["description"]
        if "owner" in dom_attrs:
            dom_attrs_for_node["owner"] = dom_attrs["owner"]
        nodes_out.append(GraphNode(
            kind=_DOMAIN_KIND,
            name=dom_name,
            path=None,
            line=None,
            attrs=dom_attrs_for_node,
        ))

        # belongs_to_domain edges
        for pkg_name in pkgs:
            if not isinstance(pkg_name, str):
                _LOG.warning(
                    "domains.yaml: domain '%s' has non-string entry in packages: %r — skipping",
                    dom_name, pkg_name,
                )
                continue
            if pkg_name not in known_names:
                _LOG.warning(
                    "domains.yaml: package '%s' (in domain '%s') is not a known package. Known packages: %s",
                    pkg_name, dom_name, known_sorted_csv,
                )
                continue
            pkg_rel = known_name_to_rel.get(pkg_name)
            edges_out.append(GraphEdge(
                src=("package", pkg_name, pkg_rel),
                dst=(_DOMAIN_KIND, dom_name, None),
                kind=_BELONGS_TO_DOMAIN_KIND,
                attrs={},
            ))

        # Queue parent for cycle-detection pass
        parent = dom_attrs.get("parent")
        if parent is not None:
            if not isinstance(parent, str):
                _LOG.warning(
                    "domains.yaml: domain '%s' has non-string parent: %r — skipping containment edge",
                    dom_name, parent,
                )
            else:
                parent_map[dom_name] = parent

    # Containment edges with D-15 cycle-aware skipping
    _emit_containment_edges(parent_map, all_domain_names, edges_out)

    # Single-transaction write
    with conn:
        upsert.upsert_records(
            conn, GraphRecords(nodes=nodes_out, edges=edges_out),
        )
