"""Derived-edge computation.

Runs AFTER resolve.sweep and AFTER _enforce_strict_tree_invariant
(Phase 30 D-19). In a single transaction (D-17):

  1. DELETE all 'references' / 'depends_on' edges
  2. DELETE 'tests' edges whose dst is a Domain
  3. Recompute references and depends_on in one shared traversal
  4. Recompute TestSuite -> Domain 'tests' edges

Trivially idempotent — second cg update produces identical edge set.
Test files are EXCLUDED from references / depends_on derivation
(Phase 31 D-11); their imports flow through Phase 30's TestSuite->Package
edges and (here) TestSuite->Domain edges.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from source_parser.projections.graph import GraphEdge, GraphRecords

from graph_io import upsert
from graph_io.import_scan import scan_package_imports
from graph_io.uri import RepoContext

_REFERENCES_KIND = "references"
_DEPENDS_ON_KIND = "depends_on"
_TESTS_KIND = "tests"
_DOMAIN_KIND = "domain"
_PACKAGE_KIND = "package"
# Phase 50 D-04: apps participate in domain membership and test coverage the
# same way packages do. Use this tuple in `kind IN (...)` filters when the
# query is "any manifest-defined node," not "strictly a Package."
_MANIFEST_KINDS = ("package", "app")
_TEST_SUITE_KIND = "test_suite"
_BELONGS_TO_DOMAIN_KIND = "belongs_to_domain"


def compute(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    ctx: RepoContext,
) -> None:
    """Recompute references / depends_on / TestSuite→Domain edges.

    Single transaction — delete-then-recompute per D-17. Trivially
    idempotent: a second invocation produces the same edge set.
    """
    with conn:
        # Step 1: clear prior pass's derived edges
        conn.execute(
            "DELETE FROM edges WHERE kind IN (?, ?)",
            (_REFERENCES_KIND, _DEPENDS_ON_KIND),
        )
        conn.execute(
            "DELETE FROM edges WHERE kind=? AND dst IN "
            "(SELECT id FROM nodes WHERE kind=?)",
            (_TESTS_KIND, _DOMAIN_KIND),
        )

        # Step 2: recompute
        _compute_references_and_depends_on(conn, repo_root, ctx)
        _compute_testsuite_domain(conn, ctx)


def _compute_references_and_depends_on(
    conn: sqlite3.Connection,
    repo_root: Path,
    ctx: RepoContext,
) -> None:
    # Load all Domain names
    domain_rows = conn.execute(
        "SELECT name FROM nodes WHERE kind=?", (_DOMAIN_KIND,),
    ).fetchall()
    domain_names = [row[0] for row in domain_rows]
    if not domain_names:
        return   # zero-domain mode — nothing to derive

    # Load all Package/App rows (name, path, kind). Phase 50 D-04: apps count too.
    pkg_rows = conn.execute(
        "SELECT name, path, kind FROM nodes WHERE kind IN ('package', 'app')"
    ).fetchall()
    all_pkg_keys: list[tuple[str, str | None]] = [
        (name, path) for name, path, _kind in pkg_rows
    ]
    # Phase 50 D-04: (name, path) -> actual kind so dst tuples of derived edges
    # (e.g. references) resolve to the existing row instead of inserting a stub.
    pkg_key_to_kind: dict[tuple[str, str | None], str] = {
        (name, path): kind for name, path, kind in pkg_rows
    }

    # domain_pkgs: Domain.name -> set of Package keys directly in it
    domain_pkgs: dict[str, set[tuple[str, str | None]]] = defaultdict(set)
    # pkg_domains: Package key -> set of Domain names directly containing it
    pkg_domains: dict[tuple[str, str | None], set[str]] = defaultdict(set)

    membership_rows = conn.execute(
        "SELECT pkg.name, pkg.path, dom.name FROM edges e "
        "JOIN nodes pkg ON e.src=pkg.id "
        "JOIN nodes dom ON e.dst=dom.id "
        "WHERE e.kind=? AND pkg.kind IN ('package', 'app') AND dom.kind=?",
        (_BELONGS_TO_DOMAIN_KIND, _DOMAIN_KIND),
    ).fetchall()
    for pkg_name, pkg_path, dom_name in membership_rows:
        pkg_key = (pkg_name, pkg_path)
        domain_pkgs[dom_name].add(pkg_key)
        pkg_domains[pkg_key].add(dom_name)

    # pkg_imports: Package key -> set of imported Package keys
    # Only scan Packages that are domain members; non-domain packages
    # cannot be the SOURCE of a references / depends_on edge.
    pkg_imports: dict[tuple[str, str | None], set[tuple[str, str | None]]] = {}
    for pkg_name, pkg_path in all_pkg_keys:
        if (pkg_name, pkg_path) not in pkg_domains:
            continue
        pkg_imports[(pkg_name, pkg_path)] = scan_package_imports(
            conn, repo_root, pkg_name, pkg_path, include_test_files=False,
        )

    # Single traversal
    ref_buckets: dict[
        tuple[str, tuple[str, str | None]], set[tuple[str, str | None]],
    ] = defaultdict(set)   # (D, tgt_pkg_key) -> {src_pkg_keys}
    dep_buckets: dict[
        tuple[str, str], set[tuple[tuple[str, str | None], tuple[str, str | None]]],
    ] = defaultdict(set)   # (A, B) -> {(src_pkg_key, tgt_pkg_key)}

    for d_name, src_pkgs in domain_pkgs.items():
        for src_key in src_pkgs:
            for tgt_key in pkg_imports.get(src_key, ()):
                tgt_domains = pkg_domains.get(tgt_key, set())
                # references criterion (D-08): D does NOT directly contain tgt
                if d_name not in tgt_domains:
                    ref_buckets[(d_name, tgt_key)].add(src_key)
                # depends_on criterion (D-09): for each Domain B containing tgt, B != d_name
                for b_name in tgt_domains:
                    if b_name != d_name:
                        dep_buckets[(d_name, b_name)].add((src_key, tgt_key))

    # Materialize edges
    edges_out: list[GraphEdge] = []
    for (d_name, tgt_key), src_set in ref_buckets.items():
        tgt_name, tgt_path = tgt_key
        # Phase 50 D-04: use actual stored kind so the references-edge dst
        # resolves to the existing Package or App row.
        tgt_kind = pkg_key_to_kind.get(tgt_key, _PACKAGE_KIND)
        edges_out.append(GraphEdge(
            src=(_DOMAIN_KIND, d_name, None),
            dst=(tgt_kind, tgt_name, tgt_path),
            kind=_REFERENCES_KIND,
            attrs={"usage_count": len(src_set)},
        ))
    for (a_name, b_name), pair_set in dep_buckets.items():
        edges_out.append(GraphEdge(
            src=(_DOMAIN_KIND, a_name, None),
            dst=(_DOMAIN_KIND, b_name, None),
            kind=_DEPENDS_ON_KIND,
            attrs={"usage_count": len(pair_set)},
        ))

    if edges_out:
        upsert.upsert_records(
            conn, GraphRecords(nodes=[], edges=edges_out),
        )


def _compute_testsuite_domain(
    conn: sqlite3.Connection,
    ctx: RepoContext,
) -> None:
    # Build (suite_id, suite_name, suite_path) -> set of Package keys
    suite_pkg_rows = conn.execute(
        "SELECT ts.id, ts.name, ts.path, pkg.name, pkg.path FROM edges e "
        "JOIN nodes ts ON e.src=ts.id "
        "JOIN nodes pkg ON e.dst=pkg.id "
        "WHERE e.kind=? AND ts.kind=? AND pkg.kind IN ('package', 'app')",
        (_TESTS_KIND, _TEST_SUITE_KIND),
    ).fetchall()
    suite_pkgs: dict[
        tuple[int, str, str | None],
        set[tuple[str, str | None]],
    ] = defaultdict(set)
    for ts_id, ts_name, ts_path, pkg_name, pkg_path in suite_pkg_rows:
        suite_pkgs[(ts_id, ts_name, ts_path)].add((pkg_name, pkg_path))

    # Build Package key -> set of Domain names
    pkg_domains: dict[tuple[str, str | None], set[str]] = defaultdict(set)
    membership_rows = conn.execute(
        "SELECT pkg.name, pkg.path, dom.name FROM edges e "
        "JOIN nodes pkg ON e.src=pkg.id "
        "JOIN nodes dom ON e.dst=dom.id "
        "WHERE e.kind=? AND pkg.kind IN ('package', 'app') AND dom.kind=?",
        (_BELONGS_TO_DOMAIN_KIND, _DOMAIN_KIND),
    ).fetchall()
    for pkg_name, pkg_path, dom_name in membership_rows:
        pkg_domains[(pkg_name, pkg_path)].add(dom_name)

    edges_out: list[GraphEdge] = []
    for (ts_id, ts_name, ts_path), pkg_keys in suite_pkgs.items():
        if len(pkg_keys) < 2:
            continue   # D-12: single-package suites get no Domain edge

        domain_sets = [pkg_domains.get(p, set()) for p in pkg_keys]
        if not all(domain_sets):
            continue   # any package with zero Domains -> skip

        intersection = set.intersection(*domain_sets)
        if len(intersection) != 1:
            continue   # D-13: multi-domain spans get no Domain edge
        # All packages must belong to EXACTLY the intersection set
        if any(ds != intersection for ds in domain_sets):
            continue   # some package has additional Domain memberships beyond the intersection

        (target_domain,) = intersection
        edges_out.append(GraphEdge(
            src=(_TEST_SUITE_KIND, ts_name, ts_path),
            dst=(_DOMAIN_KIND, target_domain, None),
            kind=_TESTS_KIND,
            attrs={},
        ))

    if edges_out:
        upsert.upsert_records(
            conn, GraphRecords(nodes=[], edges=edges_out),
        )
