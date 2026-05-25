"""cg exports <path>"""

from __future__ import annotations

import argparse
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store
from graph_io.cli import _format


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path")


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
        records = queries.exports(conn, path=args.path)
    finally:
        conn.close()
    print(_format.render(records, fmt=args.fmt))
    return exit_codes.SUCCESS
