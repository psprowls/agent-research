"""cg list-domains — list all Domain nodes alphabetically."""

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
        records = queries.list_domains(conn)
    finally:
        conn.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print("No domains configured (domains.yaml missing).", file=sys.stderr)
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(_json.dumps([dataclasses.asdict(r) for r in records], default=str))
    else:
        for r in records:
            print(r.name)
    return exit_codes.SUCCESS
