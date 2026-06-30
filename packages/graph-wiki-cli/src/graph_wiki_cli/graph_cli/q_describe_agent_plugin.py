"""gw graph describe-agent-plugin <name>"""

from __future__ import annotations

import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes
from graph_io import render as _render

from graph_wiki_cli.graph_cli._args import NameArgs


def run(args: NameArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        desc = reader.describe_agent_plugin(name=args.name)
    finally:
        reader.close()
    if desc is None:
        print(f"error: agent_plugin not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_agent_plugin(desc, fmt=args.fmt))
    return exit_codes.SUCCESS
