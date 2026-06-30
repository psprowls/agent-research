"""gw graph list-domains — list all Domain nodes alphabetically."""

from __future__ import annotations

import dataclasses
import json as _json
import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli._args import FormatArgs


def run(args: FormatArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        records = reader.list_domains()
    finally:
        reader.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print("No domains configured (graph.domains not set in .graph-wiki.yaml).", file=sys.stderr)
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(_json.dumps([dataclasses.asdict(r) for r in records], default=str))
    else:
        for r in records:
            print(r.name)
    return exit_codes.SUCCESS
