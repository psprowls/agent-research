"""cg status — print schema version, indexed commit vs HEAD, counts."""

from __future__ import annotations

import argparse
import json as _json
import sqlite3
import subprocess
import sys
from pathlib import Path

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, schema, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def _git_head(repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _collect(conn: sqlite3.Connection) -> dict:
    last = conn.execute(
        "SELECT value FROM metadata WHERE key='last_indexed_commit'"
    ).fetchone()
    last_commit = last[0] if last else None
    node_counts = dict(
        conn.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind").fetchall()
    )
    edge_counts = dict(
        conn.execute("SELECT kind, COUNT(*) FROM edges GROUP BY kind").fetchall()
    )
    languages = sorted(
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT json_extract(attrs_json, '$.language') "
            "FROM nodes WHERE attrs_json IS NOT NULL "
            "AND json_extract(attrs_json, '$.language') IS NOT NULL"
        ).fetchall()
    )
    return {
        "schema_version": schema.SCHEMA_VERSION,
        "last_indexed_commit": last_commit,
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "languages_indexed": languages,
    }


def run(args: argparse.Namespace) -> int:
    head = _git_head(args.repo)
    if head is None:
        print("error: not in a git repo", file=sys.stderr)
        return exit_codes.NOT_IN_GIT_REPO
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
        repo_desc = queries.describe_repository(conn)
        info = _collect(conn)
    finally:
        conn.close()
    info["repository"] = repo_desc.uri if repo_desc else None
    info["head"] = head
    info["stale"] = info["last_indexed_commit"] != head

    if args.fmt == "json":
        print(_json.dumps(info))
    else:
        print(f"repository:          {info['repository'] if info['repository'] else '(none)'}")
        print(f"schema_version:      {info['schema_version']}")
        print(f"last_indexed_commit: {info['last_indexed_commit']}   (HEAD: {head})")
        print(f"stale:               {info['stale']}")
        print(f"node_counts:         {info['node_counts']}")
        print(f"edge_counts:         {info['edge_counts']}")
        print(f"languages_indexed:   {info['languages_indexed']}")
    return exit_codes.STALE if info["stale"] else exit_codes.SUCCESS
