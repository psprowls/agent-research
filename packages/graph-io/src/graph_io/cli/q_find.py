"""cg find --name X [--kind KIND] [--in-package PKG]"""

from __future__ import annotations

import argparse
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, render as _render, store
from graph_io.queries import _VALID_KINDS


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--name",
        default=None,
        help="Filter by node name (exact match). Combines with other filters via AND.",
    )
    parser.add_argument(
        "--kind",
        default=None,
        choices=sorted(_VALID_KINDS),
        help="Filter by node kind. Combines with other filters via AND.",
    )
    parser.add_argument(
        "--in-package",
        dest="in_package",
        default=None,
        help=(
            "Filter results to nodes contained in the named package "
            "(case-insensitive exact match). Combines with other filters via AND."
        ),
    )


def run(args: argparse.Namespace) -> int:
    # D-01: at least one filter required.
    if args.name is None and args.kind is None and args.in_package is None:
        args._parser.error(
            "cg find requires at least one of --name, --kind, --in-package"
        )
        # parser.error() raises SystemExit(2); the next line is unreachable.

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
        records = queries.find(
            conn,
            name=args.name,
            kind=args.kind,
            in_package=args.in_package,
        )
    finally:
        conn.close()

    # D-07: --in-package non-match → exit 1 (silent zero-result distinct from
    # name/kind zero, which preserves historical SUCCESS for those filters).
    if args.in_package is not None and not records:
        return exit_codes.GENERIC

    def _notice(shown: int, total: int) -> None:
        print(f"... showing {shown} of {total} (truncated)", file=sys.stderr)

    print(_render.render(records, fmt=args.fmt, cap=50, on_truncate=_notice))
    return exit_codes.SUCCESS
