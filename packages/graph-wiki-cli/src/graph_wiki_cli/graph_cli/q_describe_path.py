"""gw graph describe-path <path>"""

from __future__ import annotations

import sys

from graph_io import exit_codes, queries, store
from graph_io import render as _render
from workspace_io.paths import graph_dir

from graph_wiki_cli.graph_cli._args import PathDescribeArgs


def run(args: PathDescribeArgs) -> int:
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
        desc = queries.describe_path(conn, path=args.path)
        if desc is None:
            print(f"error: path not found in graph: {args.path}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = queries.children_for(conn, kind="file", path=desc.path, depth=getattr(args, "depth", None))
    finally:
        conn.close()
    print(_render.format_path(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS
