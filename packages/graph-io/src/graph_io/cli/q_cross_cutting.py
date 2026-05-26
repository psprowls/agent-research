"""cg cross-cutting — D-12 cross-cutting packages ranked by SUM(usage_count)."""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


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
        records = queries.cross_cutting_packages(conn)
    finally:
        conn.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print("No zero-domain packages in graph.", file=sys.stderr)
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(
            _json.dumps(
                [
                    {
                        "name": desc.name,
                        "score": score,
                        "package": dataclasses.asdict(desc),
                    }
                    for desc, score in records
                ],
                default=str,
            )
        )
    else:
        name_w = max(len(desc.name) for desc, _ in records)
        for desc, score in records:
            print(f"{desc.name.ljust(name_w)}  score={score}")
    return exit_codes.SUCCESS
