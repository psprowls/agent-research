"""gw graph dump — raw SQL dump for debugging."""

from __future__ import annotations

import sys

import graph_io
from graph_io import GraphNotInitializedError, SchemaMismatchError, exit_codes

from graph_wiki_cli.graph_cli._args import WorkspaceArgs


def run(args: WorkspaceArgs) -> int:
    try:
        reader = graph_io.open_reader(args.workspace)
    except GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        for line in reader.dump_sql():
            print(line)
    finally:
        reader.close()
    return exit_codes.SUCCESS
