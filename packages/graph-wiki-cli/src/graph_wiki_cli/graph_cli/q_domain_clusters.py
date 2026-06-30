"""gw graph domain-clusters — connected-component clusters over package/app dependencies."""

from __future__ import annotations

import dataclasses
import json as _json
import sys
from typing import Protocol

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli._args import FormatArgs


class DomainClustersArgs(FormatArgs, Protocol):
    hub_threshold: float


def run(args: DomainClustersArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH

    try:
        try:
            result = reader.domain_clusters(hub_threshold=args.hub_threshold)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return exit_codes.GENERIC
    finally:
        reader.close()

    if result.degenerate_warning is not None:
        print(result.degenerate_warning, file=sys.stderr)

    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(result), indent=2, sort_keys=False))
    else:
        _render_human(result)

    return exit_codes.SUCCESS


def _render_human(result) -> None:
    """Print a hierarchical markdown-style view to stdout (D-21).

    Sections: header, optional Cross-cutting hubs, optional Cluster N: name
    per cluster. When both sections are empty, write a placeholder to stderr
    instead (D-22).
    """
    if not result.clusters and not result.cross_cutting:
        # D-22 empty-case: write to stderr.
        print("No members with import edges found.", file=sys.stderr)
        return

    print("# gw graph domain-clusters")
    print()
    print(f"Hub threshold: {result.hub_threshold:g}  ·  {result.n_members_total} members total")
    print()

    if result.cross_cutting:
        name_w = max(len(h.name) for h in result.cross_cutting)
        print(f"## Cross-cutting hubs ({len(result.cross_cutting)})")
        for h in result.cross_cutting:
            connects = ", ".join(str(i) for i in h.connects_clusters)
            connects_str = f"connects clusters {connects}" if connects else "no clusters"
            print(
                f"  {h.name.ljust(name_w)}  — imported by "
                f"{h.imported_by_count}/{result.n_members_total} "
                f"({h.imported_by_fraction:.0%}) — {connects_str}"
            )
        print()

    for c in result.clusters:
        print(f"## Cluster {c.id}: {c.name} ({c.size} members)")
        for m in c.members:
            print(f"  - {m}")
        print()
