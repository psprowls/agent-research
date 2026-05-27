"""Unit + determinism + degenerate tests for graph_io.cluster."""

from __future__ import annotations

import dataclasses
import json
import random
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from graph_io import cluster
from graph_io.cluster import (
    Cluster,
    ClusterResult,
    CrossCuttingHub,
    _UnionFind,
    compute_clusters,
)


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _seed_packages(
    conn: sqlite3.Connection,
    names: list[str],
    *,
    insert_order_seed: int | None = None,
) -> None:
    """INSERT package nodes. Optionally shuffles `names` with a fixed seed first."""
    to_insert = list(names)
    if insert_order_seed is not None:
        random.Random(insert_order_seed).shuffle(to_insert)
    for n in to_insert:
        conn.execute(
            "INSERT INTO nodes (kind, name) VALUES (?, ?)",
            ("package", n),
        )
    conn.commit()


def _seed_references(
    conn: sqlite3.Connection,
    edges: list[tuple[str, str]],
    *,
    insert_order_seed: int | None = None,
) -> None:
    """INSERT references edges between existing package nodes."""
    to_insert = list(edges)
    if insert_order_seed is not None:
        random.Random(insert_order_seed).shuffle(to_insert)
    for src, dst in to_insert:
        src_id = conn.execute(
            "SELECT id FROM nodes WHERE name = ? AND kind = 'package'", (src,)
        ).fetchone()[0]
        dst_id = conn.execute(
            "SELECT id FROM nodes WHERE name = ? AND kind = 'package'", (dst,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO edges (src, dst, kind) VALUES (?, ?, ?)",
            (src_id, dst_id, "references"),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# _UnionFind correctness (D-25 bullet)
# ---------------------------------------------------------------------------


def test_union_find_correctness() -> None:
    uf = _UnionFind(["a", "b", "c", "d", "e"])
    # Singleton: find on never-unioned element is itself.
    assert uf.find("a") == "a"
    assert uf.find("e") == "e"

    uf.union("a", "b")
    uf.union("b", "c")
    # Transitively, a and c share a root.
    assert uf.find("a") == uf.find("c")
    # d, e untouched.
    assert uf.find("d") == "d"
    assert uf.find("e") == "e"

    # Idempotent union doesn't break invariants.
    uf.union("a", "c")
    assert uf.find("a") == uf.find("c")


# ---------------------------------------------------------------------------
# Hub detection threshold boundaries (D-25 bullet)
# ---------------------------------------------------------------------------


def test_hub_detection_threshold_boundary(empty_db: sqlite3.Connection) -> None:
    # 10 packages: P plus P0..P8. P is imported by P0..P4 (5 importers).
    # n_packages = 10; denom = 9; in_degree(P) = 5; ratio = 5/9 ≈ 0.5555.
    names = ["P"] + [f"P{i}" for i in range(9)]
    _seed_packages(empty_db, names)
    _seed_references(empty_db, [(f"P{i}", "P") for i in range(5)])

    # threshold=0.5: 5/9 > 0.5 → P IS a hub.
    r = compute_clusters(empty_db, hub_threshold=0.5)
    assert "P" in {h.name for h in r.cross_cutting}
    assert "P" not in {m for c in r.clusters for m in c.members}

    # threshold=0.56: 5/9 < 0.56 → P is NOT a hub.
    r = compute_clusters(empty_db, hub_threshold=0.56)
    assert "P" not in {h.name for h in r.cross_cutting}
    assert "P" in {m for c in r.clusters for m in c.members}

    # Strict-greater check at the exact rational threshold: 5/9 > 5/9 is False.
    r = compute_clusters(empty_db, hub_threshold=5 / 9)
    assert "P" not in {h.name for h in r.cross_cutting}
    assert "P" in {m for c in r.clusters for m in c.members}


# ---------------------------------------------------------------------------
# Known small graph (D-25 bullet)
# ---------------------------------------------------------------------------


def test_known_small_graph(empty_db: sqlite3.Connection) -> None:
    # 6 packages A,B,C,D,E,F + 1 hub X. X is importED by all 6 (in_degree=6).
    # Clusters from intra-cluster edges A→B, B→C, D→E, plus F as singleton.
    _seed_packages(empty_db, ["A", "B", "C", "D", "E", "F", "X"])
    _seed_references(
        empty_db,
        [
            ("A", "B"),
            ("B", "C"),
            ("D", "E"),
            ("A", "X"),
            ("B", "X"),
            ("C", "X"),
            ("D", "X"),
            ("E", "X"),
            ("F", "X"),
        ],
    )

    r = compute_clusters(empty_db, hub_threshold=0.5)
    # X is hub: in_degree(X) = 6, denom = 6, ratio = 1.0 > 0.5.
    assert {h.name for h in r.cross_cutting} == {"X"}
    # 3 clusters: [A,B,C] size 3, [D,E] size 2, [F] size 1.
    sizes = [c.size for c in r.clusters]
    assert sizes == [3, 2, 1]
    cluster_members = [c.members for c in r.clusters]
    assert ("A", "B", "C") in cluster_members
    assert ("D", "E") in cluster_members
    assert ("F",) in cluster_members
    # X.connects_clusters spans all 3 clusters (ids 0, 1, 2).
    x_hub = r.cross_cutting[0]
    assert x_hub.connects_clusters == (0, 1, 2)
    assert r.degenerate_warning is None  # max 3/7 ≈ 0.43 < 0.8; 3 clusters != 7


# ---------------------------------------------------------------------------
# Degenerate-condition detection (D-25 bullet)
# ---------------------------------------------------------------------------


def test_degenerate_giant(empty_db: sqlite3.Connection) -> None:
    # 5 packages, no hubs, all in one big cluster.
    _seed_packages(empty_db, ["a", "b", "c", "d", "e"])
    _seed_references(
        empty_db,
        [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")],
    )
    r = compute_clusters(empty_db, hub_threshold=0.5)
    # No hubs (each in-degree ≤ 1, denom 4, ratio ≤ 0.25 ≤ 0.5).
    assert r.cross_cutting == ()
    assert len(r.clusters) == 1
    assert r.clusters[0].size == 5
    assert r.degenerate_warning is not None
    assert "cluster '" in r.degenerate_warning
    assert "contains 100% of packages" in r.degenerate_warning


def test_degenerate_all_singletons(empty_db: sqlite3.Connection) -> None:
    # 5 packages, zero edges → 5 singleton clusters → all-singletons warning.
    _seed_packages(empty_db, ["a", "b", "c", "d", "e"])
    r = compute_clusters(empty_db, hub_threshold=0.5)
    assert len(r.clusters) == 5
    assert all(c.size == 1 for c in r.clusters)
    assert r.degenerate_warning is not None
    assert "every package is its own cluster" in r.degenerate_warning


# ---------------------------------------------------------------------------
# Determinism (CLUSTER-05) — D-25 bullets
# ---------------------------------------------------------------------------


def test_determinism_repeated_invocation(empty_db: sqlite3.Connection) -> None:
    # Non-trivial graph: 5 packages, mixed edges, 1 hub.
    _seed_packages(empty_db, ["A", "B", "C", "D", "H"])
    _seed_references(
        empty_db,
        [
            ("A", "B"),
            ("B", "C"),
            ("D", "C"),
            ("A", "H"),
            ("B", "H"),
            ("C", "H"),
            ("D", "H"),
        ],
    )
    r1 = compute_clusters(empty_db, hub_threshold=0.5)
    r2 = compute_clusters(empty_db, hub_threshold=0.5)
    s1 = json.dumps(dataclasses.asdict(r1), sort_keys=False)
    s2 = json.dumps(dataclasses.asdict(r2), sort_keys=False)
    assert s1 == s2


def test_determinism_permuted_insertion(tmp_path) -> None:
    from graph_io.schema import apply_schema

    names = ["alpha", "bravo", "charlie", "delta", "echo", "hub"]
    edges = [
        ("alpha", "bravo"),
        ("bravo", "charlie"),
        ("delta", "echo"),
        ("alpha", "hub"),
        ("bravo", "hub"),
        ("charlie", "hub"),
        ("delta", "hub"),
        ("echo", "hub"),
    ]

    # DB 1: insert in canonical order.
    conn1 = sqlite3.connect(":memory:")
    apply_schema(conn1)
    _seed_packages(conn1, names)
    _seed_references(conn1, edges)

    # DB 2: insert in a shuffled order.
    conn2 = sqlite3.connect(":memory:")
    apply_schema(conn2)
    _seed_packages(conn2, names, insert_order_seed=42)
    _seed_references(conn2, edges, insert_order_seed=42)

    r1 = compute_clusters(conn1, hub_threshold=0.5)
    r2 = compute_clusters(conn2, hub_threshold=0.5)

    s1 = json.dumps(dataclasses.asdict(r1), sort_keys=False)
    s2 = json.dumps(dataclasses.asdict(r2), sort_keys=False)
    assert s1 == s2, "permuted insertion changed clustering output"

    conn1.close()
    conn2.close()


# ---------------------------------------------------------------------------
# Validation (D-25 bullet)
# ---------------------------------------------------------------------------


def test_hub_threshold_out_of_range(empty_db: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        compute_clusters(empty_db, hub_threshold=0.0)
    with pytest.raises(ValueError):
        compute_clusters(empty_db, hub_threshold=-0.1)
    with pytest.raises(ValueError):
        compute_clusters(empty_db, hub_threshold=1.001)
    # 1.0 is the inclusive upper bound (D-06) — does NOT raise.
    compute_clusters(empty_db, hub_threshold=1.0)


# ---------------------------------------------------------------------------
# Empty graph (D-25 bullet)
# ---------------------------------------------------------------------------


def test_empty_graph(empty_db: sqlite3.Connection) -> None:
    r = compute_clusters(empty_db)
    assert r.n_packages_total == 0
    assert r.clusters == ()
    assert r.cross_cutting == ()
    assert r.degenerate_warning is None


# ---------------------------------------------------------------------------
# Singleton survives when isolated (D-03)
# ---------------------------------------------------------------------------


def test_singleton_cluster_present_when_isolated(empty_db: sqlite3.Connection) -> None:
    _seed_packages(empty_db, ["A", "B", "C"])
    _seed_references(empty_db, [("A", "B")])
    r = compute_clusters(empty_db, hub_threshold=0.5)
    assert len(r.clusters) == 2
    sizes = sorted([c.size for c in r.clusters], reverse=True)
    assert sizes == [2, 1]


# ---------------------------------------------------------------------------
# Cluster naming via intra-cluster in-degree (D-10)
# ---------------------------------------------------------------------------


def test_cluster_name_intra_in_degree_picks_central(empty_db: sqlite3.Connection) -> None:
    # A,B,C with edges A→B, A→C, B→C. Intra in-degree: A=0, B=1, C=2 → name=C.
    _seed_packages(empty_db, ["A", "B", "C"])
    _seed_references(empty_db, [("A", "B"), ("A", "C"), ("B", "C")])
    # threshold=1.0 inclusive: C's ratio is 2/2=1.0; 1.0 > 1.0 is False → not a hub.
    r = compute_clusters(empty_db, hub_threshold=1.0)
    assert len(r.clusters) == 1
    assert r.clusters[0].name == "C"


# ---------------------------------------------------------------------------
# Hub-to-hub edges are excluded from connects_clusters (D-08)
# ---------------------------------------------------------------------------


def test_connects_clusters_skips_hub_to_hub_edges(empty_db: sqlite3.Connection) -> None:
    # 4 packages: X, Y (both become hubs), A, B (a cluster).
    # Edges:
    #   A→X, B→X (X imported by 2/3 → hub at threshold 0.5)
    #   A→Y, B→Y (Y imported by 2/3 → hub at threshold 0.5)
    #   X→Y, Y→X (hub-to-hub)
    #   A→B (A,B cluster)
    _seed_packages(empty_db, ["A", "B", "X", "Y"])
    _seed_references(
        empty_db,
        [
            ("A", "X"),
            ("B", "X"),
            ("A", "Y"),
            ("B", "Y"),
            ("X", "Y"),
            ("Y", "X"),
            ("A", "B"),
        ],
    )
    r = compute_clusters(empty_db, hub_threshold=0.5)
    assert {h.name for h in r.cross_cutting} == {"X", "Y"}
    # Single cluster: [A, B].
    assert len(r.clusters) == 1
    # Each hub's connects_clusters should be (0,) — hub-to-hub edges excluded
    # because the other endpoint is not in any cluster.
    for h in r.cross_cutting:
        assert h.connects_clusters == (0,), f"hub {h.name} connects {h.connects_clusters}"


# ---------------------------------------------------------------------------
# CLI tests (Plan 47-02): subprocess against `cg domain-clusters`.
# Use `python -m graph_io.cli.main` to avoid PATH dependence.
# ---------------------------------------------------------------------------


def _cg_cmd() -> list[str]:
    return [sys.executable, "-m", "graph_io.cli.main"]


def _seed_workspace(
    tmp_path: Path,
    names: list[str],
    edges: list[tuple[str, str]],
) -> Path:
    """Build a minimal workspace + initialised code.db with the given graph."""
    from graph_io.schema import apply_schema
    from workspace_io.config import resolve
    from workspace_io.paths import graph_dir

    ws = resolve(tmp_path, require_manifest=False).workspace
    gd = graph_dir(ws)
    gd.mkdir(parents=True, exist_ok=True)
    db_path = gd / "code.db"
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
        _seed_packages(conn, names)
        _seed_references(conn, edges)
    finally:
        conn.close()
    return ws


def test_cli_subcommand_registered() -> None:
    """CLUSTER-04: `cg --help` lists domain-clusters."""
    result = subprocess.run(
        [*_cg_cmd(), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "domain-clusters" in result.stdout


def test_cli_human_format(tmp_path: Path) -> None:
    _seed_workspace(
        tmp_path,
        ["A", "B", "C", "D"],
        [("A", "B"), ("B", "C")],
    )
    result = subprocess.run(
        [
            *_cg_cmd(),
            "--mode",
            "test",
            "--repo",
            str(tmp_path),
            "--fmt",
            "human",
            "domain-clusters",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert "# cg domain-clusters" in result.stdout
    assert "## Cluster 0:" in result.stdout


def test_cli_json_format(tmp_path: Path) -> None:
    _seed_workspace(
        tmp_path,
        ["A", "B", "C", "D"],
        [("A", "B"), ("B", "C")],
    )
    result = subprocess.run(
        [
            *_cg_cmd(),
            "--mode",
            "test",
            "--repo",
            str(tmp_path),
            "--fmt",
            "json",
            "domain-clusters",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    payload = json.loads(result.stdout)
    # D-20: JSON key order locked.
    assert list(payload.keys()) == [
        "hub_threshold",
        "n_packages_total",
        "degenerate_warning",
        "clusters",
        "cross_cutting",
    ]


def test_cli_hub_threshold_validation(tmp_path: Path) -> None:
    _seed_workspace(tmp_path, ["A", "B"], [("A", "B")])
    for bad in ("0.0", "1.5"):
        result = subprocess.run(
            [
                *_cg_cmd(),
                "--mode",
                "test",
                "--repo",
                str(tmp_path),
                "domain-clusters",
                "--hub-threshold",
                bad,
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "hub_threshold" in result.stderr


def test_cli_not_initialized(tmp_path: Path) -> None:
    # No DB seeded.
    result = subprocess.run(
        [
            *_cg_cmd(),
            "--mode",
            "test",
            "--repo",
            str(tmp_path),
            "domain-clusters",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3  # exit_codes.NOT_INITIALIZED
    assert "graph DB not found" in result.stderr


def test_cli_emits_degenerate_warning_to_stderr(tmp_path: Path) -> None:
    _seed_workspace(tmp_path, ["A", "B", "C", "D", "E"], [])
    result = subprocess.run(
        [
            *_cg_cmd(),
            "--mode",
            "test",
            "--repo",
            str(tmp_path),
            "--fmt",
            "json",
            "domain-clusters",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "every package is its own cluster" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["degenerate_warning"] is not None
