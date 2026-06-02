"""gw graph describe-agent-plugin <name>"""

from __future__ import annotations

import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def run(args: object) -> int:
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
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"name:        {desc.name}")
        print(f"ecosystem:   {desc.ecosystem}")
        print(f"version:     {desc.version}")
        print(f"uri:         {desc.uri}")
        print(f"commands:    {len(desc.commands)}")
        print(f"agents:      {len(desc.agents)}")
        print(f"skills:      {len(desc.skills)}")
        print(f"scripts:     {len(desc.scripts)}")
        print(f"hooks:       {len(desc.hooks)}")
        print(f"mcp_servers: {len(desc.mcp_servers)}")
    return exit_codes.SUCCESS
