"""gw graph describe-agent-plugin <name>"""

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
        desc = queries.describe_agent_plugin(conn, name=args.name)
    finally:
        conn.close()
    if desc is None:
        print(f"error: agent_plugin not found: {args.name}", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_agent_plugin(desc, fmt=args.fmt))
    return exit_codes.SUCCESS
