"""cg list-entry-points <package> [--kind {executable,library}]"""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("package")
    parser.add_argument("--kind", choices=("executable", "library"), default=None)


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
        entries = queries.entry_points_for_package(conn, package_name=args.package)
    finally:
        conn.close()

    if args.kind is not None:
        entries = [d for d in entries if d.kind == args.kind]

    if not entries:
        if args.fmt == "json":
            print("[]")
        else:
            print(
                f"Package '{args.package}' has no declared entry points.",
                file=sys.stderr,
            )
        return exit_codes.SUCCESS

    if args.fmt == "json":
        print(_json.dumps([dataclasses.asdict(d) for d in entries], default=str))
    else:
        if args.kind is not None:
            for d in entries:
                print(d.name)
        else:
            for d in entries:
                impl = d.implemented_by_path if d.implemented_by_path else "(unresolved)"
                print(f"{d.name}  [{d.kind}]  -> {impl}")
    return exit_codes.SUCCESS
