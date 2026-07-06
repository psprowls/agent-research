# packages/graph-io/src/graph_io/repo_context.py
"""Derive a repo's `(org, repo)` identity from its git remote.

Public entry point for callers outside graph-io (e.g. graph-wiki-core's
multi-repo gate helpers) that need a repo's identity without reaching into
graph-io's internal `update` module.
"""

from __future__ import annotations

from pathlib import Path

from graph_io.update import NotInGitRepoError, _git
from graph_io.uri import RepoContext, parse_remote_url


def repo_context(repo_root: Path) -> RepoContext:
    """Derive `(org, repo)` from `git remote get-url origin`, falling back to local.

    D-04: try `git remote get-url origin` only — no upstream/fork probing.
    D-05: on any failure (non-zero exit, unparseable URL), fall back to
    `RepoContext(org='local', repo=repo_root.name)` — literal `'local'`
    sentinel, no underscore prefix.
    """
    try:
        remote_url = _git(["remote", "get-url", "origin"], cwd=repo_root).strip()
    except NotInGitRepoError:
        return RepoContext(org="local", repo=repo_root.name)
    parsed = parse_remote_url(remote_url)
    if parsed is None:
        return RepoContext(org="local", repo=repo_root.name)
    org, repo = parsed
    return RepoContext(org=org, repo=repo)
