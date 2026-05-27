"""Deterministic connected-component domain clustering over the code graph.

This module implements undirected weakly-connected-components clustering over
`references` edges between `package` nodes, with hub-node exclusion preprocessing.
A *hub* is a package whose in-degree fraction exceeds ``hub_threshold`` — those
packages are removed from the working node and edge set before union-find runs,
so utility libraries (logging, click, pytest, etc.) do not silently merge every
otherwise-separable cluster into one giant component.

Determinism guarantee (CLUSTER-05): ``compute_clusters`` is byte-identically
deterministic. The implementation enforces this by:

- Sorting at every level (D-09): outer clusters by ``(-size, members[0])``,
  inner ``members`` alphabetically, ``cross_cutting`` by name, and inner
  ``connects_clusters`` ascending integer.
- Loading all input via ``ORDER BY``-suffixed SQL — no dependence on SQLite
  iteration order.
- Treating set-derived intermediates as inputs to sorted-by-construction
  collections only.

Two successive invocations of ``compute_clusters`` on the same database, and
two invocations on databases populated in different insertion orders, both
produce identical ``ClusterResult`` instances whose
``json.dumps(asdict(...), sort_keys=False)`` is byte-identical.

Public API:

- ``compute_clusters(conn, *, hub_threshold=0.5) -> ClusterResult``

The frozen dataclasses ``Cluster``, ``CrossCuttingHub``, and ``ClusterResult``
are the contract Phase 48's LLM-proposal layer consumes via ``--fmt json``.

Pure stdlib (D-24): no ``networkx``, no ``python-louvain``, no third-party deps.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

_DEFAULT_HUB_THRESHOLD: float = 0.5
_DEGENERATE_GIANT_RATIO: float = 0.8
_REFERENCES_KIND: str = "references"
_PACKAGE_KIND: str = "package"


@dataclass(frozen=True)
class Cluster:
    id: int
    name: str
    members: tuple[str, ...]
    size: int


@dataclass(frozen=True)
class CrossCuttingHub:
    name: str
    imported_by_count: int
    imported_by_fraction: float
    connects_clusters: tuple[int, ...]


@dataclass(frozen=True)
class ClusterResult:
    hub_threshold: float
    n_packages_total: int
    degenerate_warning: str | None
    clusters: tuple[Cluster, ...]
    cross_cutting: tuple[CrossCuttingHub, ...]


class _UnionFind:
    """Union-find with union-by-rank and path compression. Items are strings."""

    def __init__(self, items: Iterable[str]) -> None:
        self._parent: dict[str, str] = {x: x for x in items}
        self._rank: dict[str, int] = {x: 0 for x in self._parent}

    def find(self, x: str) -> str:
        # Iterative path compression to avoid recursion limits.
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # Compress.
        cur = x
        while self._parent[cur] != root:
            nxt = self._parent[cur]
            self._parent[cur] = root
            cur = nxt
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # Attach smaller-rank tree under larger-rank root.
        if self._rank[ra] < self._rank[rb]:
            self._parent[ra] = rb
        elif self._rank[ra] > self._rank[rb]:
            self._parent[rb] = ra
        else:
            self._parent[rb] = ra
            self._rank[ra] += 1


def _load_package_names(conn: sqlite3.Connection) -> list[str]:
    """Return all package node names, sorted alphabetically (D-15)."""
    rows = conn.execute(
        "SELECT name FROM nodes WHERE kind = ? ORDER BY name",
        (_PACKAGE_KIND,),
    ).fetchall()
    return [r[0] for r in rows]


def _load_reference_edges(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return all ``references`` edges between two ``package`` nodes (D-15).

    Sorted by ``(src, dst)`` at the SQL level for determinism.
    """
    rows = conn.execute(
        """
        SELECT src.name, dst.name
        FROM edges e
        JOIN nodes src ON src.id = e.src
        JOIN nodes dst ON dst.id = e.dst
        WHERE e.kind = ? AND src.kind = ? AND dst.kind = ?
        ORDER BY src.name, dst.name
        """,
        (_REFERENCES_KIND, _PACKAGE_KIND, _PACKAGE_KIND),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _compute_hubs(
    adjacency_in: dict[str, set[str]],
    names: list[str],
    threshold: float,
) -> set[str]:
    """Return the set of package names classified as hubs (D-04).

    A package ``n`` is a hub when ``in_degree(n) / (n_packages - 1) > threshold``
    (strictly greater). With ``n_packages <= 1`` there is no denominator, so
    no node can be a hub.
    """
    n_packages = len(names)
    if n_packages <= 1:
        return set()
    denom = n_packages - 1
    hubs: set[str] = set()
    for n in names:
        in_degree = len(adjacency_in.get(n, ()))
        if in_degree / denom > threshold:
            hubs.add(n)
    return hubs


def _compute_intra_in_degree(
    members: set[str],
    original_edges: list[tuple[str, str]],
) -> dict[str, int]:
    """Return ``{member: count_of_edges_dst==member_AND_src_in_members}`` (D-10)."""
    counts: dict[str, int] = {m: 0 for m in members}
    for src, dst in original_edges:
        if dst in members and src in members and src != dst:
            counts[dst] += 1
    return counts


def _pick_cluster_name(
    members_sorted: list[str],
    intra_in_degree: dict[str, int],
) -> str:
    """Pick the member with the highest intra-cluster in-degree (D-10).

    Ties broken alphabetically (members_sorted is already alphabetical so the
    first encountered with the max wins).
    """
    best_name = members_sorted[0]
    best_count = intra_in_degree.get(best_name, 0)
    for m in members_sorted[1:]:
        c = intra_in_degree.get(m, 0)
        if c > best_count:
            best_name = m
            best_count = c
    return best_name


def _compute_connects_clusters(
    hub: str,
    original_edges: list[tuple[str, str]],
    name_to_cluster_id: dict[str, int],
) -> tuple[int, ...]:
    """Return cluster ids reachable via ``hub``'s excluded edges (D-08).

    Iterates over every edge touching ``hub`` (as src or dst), maps the other
    endpoint to its cluster id if it is in a cluster (hub-to-hub edges are
    skipped because the other endpoint is not in ``name_to_cluster_id``).
    Deduplicated, sorted ascending.
    """
    ids: set[int] = set()
    for src, dst in original_edges:
        if src == hub and dst != hub:
            cid = name_to_cluster_id.get(dst)
            if cid is not None:
                ids.add(cid)
        elif dst == hub and src != hub:
            cid = name_to_cluster_id.get(src)
            if cid is not None:
                ids.add(cid)
    return tuple(sorted(ids))


def _detect_degenerate(
    clusters: tuple[Cluster, ...],
    n_packages_total: int,
    threshold: float,
) -> str | None:
    """Detect degenerate clusterings (D-11/D-12/D-13/D-14).

    First-match-wins: giant component checked before all-singletons. ``None``
    when neither condition fires.
    """
    if n_packages_total <= 0:
        return None
    if clusters:
        max_size = max(c.size for c in clusters)
        if max_size / n_packages_total > _DEGENERATE_GIANT_RATIO:
            # Find the cluster with that max size (sort spec guarantees ties
            # break by members[0]; clusters is already sorted, so first match
            # is the deterministic pick).
            giant = next(c for c in clusters if c.size == max_size)
            pct = max_size / n_packages_total
            return (
                f"warning: domain clustering degenerate — cluster '{giant.name}' "
                f"contains {pct:.0%} of packages.\n"
                f"Likely cause: hub threshold too high (currently {threshold:g}), "
                f"too few packages, or sparse imports.\n"
                f"Try: cg domain-clusters --hub-threshold 0.3"
            )
    if clusters and len(clusters) == n_packages_total:
        return (
            f"warning: domain clustering degenerate — every package is its own cluster.\n"
            f"Likely cause: hub threshold too aggressive (currently {threshold:g}) "
            f"or no inter-package imports.\n"
            f"Try: cg domain-clusters --hub-threshold 0.7"
        )
    return None


def compute_clusters(
    conn: sqlite3.Connection,
    *,
    hub_threshold: float = _DEFAULT_HUB_THRESHOLD,
) -> ClusterResult:
    """Compute deterministic domain clusters with hub-exclusion preprocessing.

    See module docstring for the determinism contract and D-02 for the algorithm
    steps. ``hub_threshold`` must be in ``(0.0, 1.0]`` (D-06).
    """
    if not (0.0 < hub_threshold <= 1.0):
        raise ValueError(
            f"hub_threshold must be in (0.0, 1.0], got {hub_threshold}"
        )

    names = _load_package_names(conn)
    n_packages_total = len(names)

    if n_packages_total == 0:
        return ClusterResult(
            hub_threshold=hub_threshold,
            n_packages_total=0,
            degenerate_warning=None,
            clusters=(),
            cross_cutting=(),
        )

    edges = _load_reference_edges(conn)

    adjacency_in: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        if src != dst:
            adjacency_in[dst].add(src)

    hubs = _compute_hubs(adjacency_in, names, hub_threshold)

    remaining_names = [n for n in names if n not in hubs]
    remaining_edges = [
        (s, d) for s, d in edges if s not in hubs and d not in hubs
    ]

    uf = _UnionFind(remaining_names)
    for src, dst in remaining_edges:
        uf.union(src, dst)

    # Group remaining names by their union-find root.
    groups: dict[str, list[str]] = defaultdict(list)
    for n in remaining_names:
        groups[uf.find(n)].append(n)

    # Build a pre-sort list of (members_sorted, intra-derived name, size).
    pre_sort: list[dict[str, object]] = []
    for members in groups.values():
        members_sorted = sorted(members)
        intra = _compute_intra_in_degree(set(members_sorted), edges)
        cluster_name = _pick_cluster_name(members_sorted, intra)
        pre_sort.append(
            {
                "name": cluster_name,
                "members_sorted": tuple(members_sorted),
                "size": len(members_sorted),
            }
        )

    # Outer sort by (-size, members[0]).
    pre_sort.sort(key=lambda c: (-c["size"], c["members_sorted"][0]))

    clusters_list: list[Cluster] = []
    name_to_cluster_id: dict[str, int] = {}
    for idx, c in enumerate(pre_sort):
        members_t: tuple[str, ...] = c["members_sorted"]  # type: ignore[assignment]
        clusters_list.append(
            Cluster(
                id=idx,
                name=c["name"],  # type: ignore[arg-type]
                members=members_t,
                size=c["size"],  # type: ignore[arg-type]
            )
        )
        for m in members_t:
            name_to_cluster_id[m] = idx

    clusters_tuple: tuple[Cluster, ...] = tuple(clusters_list)

    # Build cross-cutting hubs, iterating sorted(hubs) — final tuple is
    # therefore alphabetical by name (D-09).
    denom = n_packages_total - 1
    cross_cutting_list: list[CrossCuttingHub] = []
    for h in sorted(hubs):
        imported_by_count = len(adjacency_in.get(h, ()))
        imported_by_fraction = (imported_by_count / denom) if denom > 0 else 0.0
        cross_cutting_list.append(
            CrossCuttingHub(
                name=h,
                imported_by_count=imported_by_count,
                imported_by_fraction=imported_by_fraction,
                connects_clusters=_compute_connects_clusters(
                    h, edges, name_to_cluster_id
                ),
            )
        )

    degenerate_warning = _detect_degenerate(
        clusters_tuple, n_packages_total, hub_threshold
    )

    return ClusterResult(
        hub_threshold=hub_threshold,
        n_packages_total=n_packages_total,
        degenerate_warning=degenerate_warning,
        clusters=clusters_tuple,
        cross_cutting=tuple(cross_cutting_list),
    )
