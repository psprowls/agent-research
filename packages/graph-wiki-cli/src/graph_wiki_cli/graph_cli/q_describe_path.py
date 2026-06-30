"""gw graph describe-path <path>"""

from __future__ import annotations

import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes
from graph_io import render as _render

from graph_wiki_cli.graph_cli._args import PathDescribeArgs


def run(args: PathDescribeArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        desc = reader.describe_path(path=args.path)
        if desc is None:
            print(f"error: path not found in graph: {args.path}", file=sys.stderr)
            return exit_codes.GENERIC
        children, eff = reader.children_for(kind="file", path=desc.path, depth=getattr(args, "depth", None))
    finally:
        reader.close()
    print(_render.format_path(desc, fmt=args.fmt, children=children, effective_depth=eff))
    return exit_codes.SUCCESS
