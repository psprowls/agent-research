"""cg domain-clusters — connected-component clusters over package references."""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import cluster, exit_codes, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hub-threshold",
        type=float,
        default=0.5,
        help="exclude packages imported by more than this fraction of others (default 0.5)",
    )


def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH

    try:
        try:
            result = cluster.compute_clusters(conn, hub_threshold=args.hub_threshold)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return exit_codes.GENERIC
    finally:
        conn.close()

    if result.degenerate_warning is not None:
        print(result.degenerate_warning, file=sys.stderr)

    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(result), indent=2, sort_keys=False))
    else:
        _render_human(result)

    return exit_codes.SUCCESS


def _render_human(result: cluster.ClusterResult) -> None:
    """Print a hierarchical markdown-style view to stdout (D-21).

    Sections: header, optional Cross-cutting hubs, optional Cluster N: name
    per cluster. When both sections are empty, write a placeholder to stderr
    instead (D-22).
    """
    if not result.clusters and not result.cross_cutting:
        # D-22 empty-case: write to stderr.
        print("No packages with import edges found.", file=sys.stderr)
        return

    print("# cg domain-clusters")
    print()
    print(
        f"Hub threshold: {result.hub_threshold:g}  ·  "
        f"{result.n_packages_total} packages total"
    )
    print()

    if result.cross_cutting:
        name_w = max(len(h.name) for h in result.cross_cutting)
        print(f"## Cross-cutting hubs ({len(result.cross_cutting)})")
        for h in result.cross_cutting:
            connects = ", ".join(str(i) for i in h.connects_clusters)
            connects_str = f"connects clusters {connects}" if connects else "no clusters"
            print(
                f"  {h.name.ljust(name_w)}  — imported by "
                f"{h.imported_by_count}/{result.n_packages_total} "
                f"({h.imported_by_fraction:.0%}) — {connects_str}"
            )
        print()

    for c in result.clusters:
        print(f"## Cluster {c.id}: {c.name} ({c.size} packages)")
        for m in c.members:
            print(f"  - {m}")
        print()
