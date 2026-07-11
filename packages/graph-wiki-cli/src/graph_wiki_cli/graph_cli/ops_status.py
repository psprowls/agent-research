"""gw graph status — print schema version, indexed commit vs HEAD, counts."""

from __future__ import annotations

import json as _json
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import SCHEMA_VERSION, exit_codes

from graph_wiki_cli.graph_cli._args import FormatArgs, RepoWorkspaceArgs


class StatusArgs(RepoWorkspaceArgs, FormatArgs, Protocol):
    pass


def _git_head(repo: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _collect(reader) -> dict:
    last_commit = reader.metadata("last_indexed_commit")
    node_counts = reader.node_counts_by_kind()
    edge_counts = reader.edge_counts_by_kind()
    languages = reader.languages()
    return {
        "schema_version": SCHEMA_VERSION,
        "last_indexed_commit": last_commit,
        "node_counts": node_counts,
        "edge_counts": edge_counts,
        "languages_indexed": languages,
    }


def run(args: StatusArgs) -> int:
    head = _git_head(args.repo)
    if head is None:
        print("error: not in a git repo", file=sys.stderr)
        return exit_codes.NOT_IN_GIT_REPO
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        repo_desc = reader.describe_repository()
        info = _collect(reader)
    finally:
        reader.close()
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
