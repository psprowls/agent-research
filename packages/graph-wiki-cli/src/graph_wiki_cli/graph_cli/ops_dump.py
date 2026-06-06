"""gw graph dump — raw SQL dump for debugging."""

from __future__ import annotations

import sys

from graph_io import exit_codes, store
from workspace_io.paths import graph_dir

from graph_wiki_cli.graph_cli._args import WorkspaceArgs


def run(args: WorkspaceArgs) -> int:
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
        for line in conn.iterdump():
            print(line)
    finally:
        conn.close()
    return exit_codes.SUCCESS
