"""gw graph describe-dependency <name> [--ecosystem pypi]"""

from __future__ import annotations

import sys
from typing import cast

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes
from graph_io import render as _render

from graph_wiki_cli.graph_cli._args import DependencyDescribeArgs


def run(args: DependencyDescribeArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        desc = reader.describe_dependency(ecosystem=cast(str, args.ecosystem), name=args.name)
    finally:
        reader.close()
    if desc is None:
        print(
            f"error: dependency not found: {args.ecosystem}/{args.name}",
            file=sys.stderr,
        )
        return exit_codes.GENERIC
    print(_render.format_dependency(desc, fmt=args.fmt))
    return exit_codes.SUCCESS
