"""cg list-scripts — union of executable files + executable entry points.

Output is deduped by file path with annotations indicating signal source(s):
declared (via EntryPoint declares_entry_point) and/or conventional
(File.is_executable=true). D-05/D-06/D-07.
"""

from __future__ import annotations

import argparse
import json as _json
import sys
from collections import defaultdict

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
        records = queries.list_scripts(conn)
        # Single annotation lookup: path -> [(pkg, callable), ...].
        declared_lookup: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
        ann_rows = conn.execute(
            "SELECT pkg.name, ep.path, json_extract(ep.attrs_json, '$.callable') "
            "FROM nodes pkg "
            "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
            "JOIN nodes ep ON ep.id = de.dst "
            "WHERE ep.kind='entry_point' AND ep.path IS NOT NULL"
        ).fetchall()
        for pkg_name, path, callable_ in ann_rows:
            declared_lookup[path].append((pkg_name, callable_))
    finally:
        conn.close()

    # Sort each declared entry list by package name for determinism.
    for path in declared_lookup:
        declared_lookup[path].sort(key=lambda t: t[0])

    # Build path-level dedup keyed by record path. Track which source kinds
    # contributed.
    declared_paths: set[str] = set()
    conventional_paths: set[str] = set()
    for r in records:
        if r.path is None:
            continue
        if r.kind == "file":
            conventional_paths.add(r.path)
        elif r.kind == "entry_point":
            declared_paths.add(r.path)

    all_paths = sorted(declared_paths | conventional_paths)

    if not all_paths:
        if args.fmt == "json":
            print("[]")
        else:
            print("No declared or conventional scripts in graph.", file=sys.stderr)
        return exit_codes.SUCCESS

    if args.fmt == "json":
        out = []
        for path in all_paths:
            declared = [
                {"package": pkg, "callable": call}
                for pkg, call in declared_lookup.get(path, [])
            ]
            out.append(
                {
                    "path": path,
                    "declared": declared,
                    "conventional": path in conventional_paths,
                }
            )
        print(_json.dumps(out, default=str))
    else:
        path_w = max(len(p) for p in all_paths)
        for path in all_paths:
            annotations: list[str] = []
            if path in declared_paths:
                declared_strs = [
                    f"{pkg}={call}" if call else f"{pkg}=(unresolved)"
                    for pkg, call in declared_lookup.get(path, [])
                ]
                annotations.append("declared: " + ", ".join(declared_strs))
            if path in conventional_paths:
                annotations.append("conventional")
            print(f"{path.ljust(path_w)}  [{', '.join(annotations)}]")
    return exit_codes.SUCCESS
