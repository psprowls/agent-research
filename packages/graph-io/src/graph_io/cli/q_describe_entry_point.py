"""cg describe-entry-point <name>

Looks up an EntryPoint by name. Accepts either a bare entry-point name
(unique across all packages) or a qualified ``package:entry`` form. The bare
form resolves by scanning all packages declaring an EntryPoint with that name;
if multiple matches are found, returns AMBIGUOUS with the candidates listed.

Note: Phase 38 RESEARCH §3 documented the underlying ``queries.describe_entry_point``
as ``(conn, name=...)`` but the actual signature is
``(conn, package_name=..., entry_name=...)``. This module bridges the gap so the
agent-side dispatch table can pass a single identifier (D-09) while the
underlying query still receives both fields it needs.
"""

from __future__ import annotations

import argparse
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, render as _render, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "name",
        help="Entry-point name. Use 'package:entry' to disambiguate when bare name is shared across packages.",
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
        raw = args.name
        if ":" in raw:
            package_name, entry_name = raw.split(":", 1)
            desc = queries.describe_entry_point(
                conn, package_name=package_name, entry_name=entry_name
            )
        else:
            # Bare entry name: scan all packages that declare an EntryPoint by this name.
            rows = conn.execute(
                "SELECT pkg.name "
                "FROM nodes pkg "
                "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
                "JOIN nodes ep ON ep.id = de.dst AND ep.kind='entry_point' "
                # Phase 50 D-04: include apps too — apps declare entry points
                # via the same manifest fields as packages.
                "WHERE pkg.kind IN ('package', 'app') AND ep.name = ?",
                (raw,),
            ).fetchall()
            if not rows:
                desc = None
            elif len(rows) > 1:
                packages = ", ".join(r[0] for r in rows)
                print(
                    f"error: entry point not found: {raw} (ambiguous across packages: {packages}; use 'package:entry')",
                    file=sys.stderr,
                )
                return exit_codes.AMBIGUOUS
            else:
                desc = queries.describe_entry_point(
                    conn, package_name=rows[0][0], entry_name=raw
                )
    finally:
        conn.close()
    if desc is None:
        print(f"error: entry point not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_entry_point(desc, fmt=args.fmt))
    return exit_codes.SUCCESS
