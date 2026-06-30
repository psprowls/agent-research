"""gw graph describe-builtin <uri> — describe a Builtin node by URI (Phase 49 BUILTIN-06)."""

from __future__ import annotations

import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes
from graph_io import render as _render

from graph_wiki_cli.graph_cli._args import BuiltinDescribeArgs


def run(args: BuiltinDescribeArgs) -> int:
    # URI parse — fail fast on malformed input with exit_codes.GENERIC.
    if not args.uri.startswith("builtin:"):
        print(f"error: not a builtin URI: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    rest = args.uri.removeprefix("builtin:")
    if "/" not in rest:
        print(f"error: malformed builtin URI: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    language, module_name = rest.split("/", 1)

    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        desc = reader.describe_builtin(language=language, module_name=module_name)
    finally:
        reader.close()
    if desc is None:
        print(f"error: builtin not found: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_builtin(desc, fmt=args.fmt))
    return exit_codes.SUCCESS
