"""gw graph find --name X [--kind KIND] [--in-package PKG]"""

from __future__ import annotations

import sys

from graph_io import exit_codes, queries, store
from graph_io import render as _render
from workspace_io.paths import graph_dir


def run(args: object) -> int:
    # D-01: at least one filter required.
    if args.name is None and args.kind is None and args.in_package is None:
        return exit_codes.GENERIC

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
