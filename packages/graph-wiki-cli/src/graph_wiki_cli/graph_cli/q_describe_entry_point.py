"""gw graph describe-entry-point <name>

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

import sys

from graph_io import exit_codes, queries, store
from graph_io import render as _render
from workspace_io.paths import graph_dir

from graph_wiki_cli.graph_cli._args import NameArgs


def run(args: NameArgs) -> int:
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
        desc, ambiguous = queries.resolve_entry_point(conn, args.name)
    finally:
        conn.close()
    if ambiguous:
        packages = ", ".join(ambiguous)
        print(
            f"error: entry point not found: {args.name} (ambiguous across packages: {packages}; use 'package:entry')",
            file=sys.stderr,
        )
        return exit_codes.AMBIGUOUS
    if desc is None:
        print(f"error: entry point not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_entry_point(desc, fmt=args.fmt))
    return exit_codes.SUCCESS
