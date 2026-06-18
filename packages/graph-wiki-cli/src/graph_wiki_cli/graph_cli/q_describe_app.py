"""gw graph describe-app <name> (Phase 50 APP-05 / D-10 / D-11).

Looks up an App node by name and prints its attributes plus joined
counts/files/domains/entry_points/test_suites. Mirrors
`gw graph describe-package` with two added lines for `app_kind` and `signals`.
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
        desc = queries.describe_app(conn, name=args.name)
        if desc is None:
            print(f"error: app not found: {args.name}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = queries.children_for(conn, kind="app", name=desc.name, depth=getattr(args, "depth", None))
    finally:
        conn.close()
    print(_render.format_app(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS
