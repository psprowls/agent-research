"""cg describe-repo — describe the single Repository node in the graph."""

from __future__ import annotations

import argparse
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, render as _render, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> int:
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
        desc = queries.describe_repository(conn)
    finally:
        conn.close()
    if desc is None:
        print("error: not found: repository", file=sys.stderr)
        return exit_codes.GENERIC
    print(_render.format_repo(desc, fmt=args.fmt))
    return exit_codes.SUCCESS
