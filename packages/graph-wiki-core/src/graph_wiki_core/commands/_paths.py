"""Shared path-resolution helper for graph-wiki-core commands.

Single source of truth for `_resolve_paths` — both `graph.py` and
`propose_domains.py` import from here so they can never diverge.
(todo 260530-iqr: DRY convergence after hxy fixed graph.py)

`resolve_wiki_and_repo` is the public re-export delivery surfaces
(graph-wiki-cli, subagent-cli, ...) must use instead of importing
wiki_io._workspace directly.
"""

from __future__ import annotations

from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo as _wiki_resolve_wiki_and_repo


def resolve_wiki_and_repo(
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Public re-export of wiki_io._workspace.resolve_wiki_and_repo.

    Delivery surfaces must call this rather than importing wiki_io._workspace
    directly — see 2026-07-05-thin-the-delivery-surfaces-route-graph-wiki-cli-and-subagent-cli-through-graph-wiki-core.
    """
    return _wiki_resolve_wiki_and_repo(workspace_path, repo_path)


def _resolve_paths(workspace_arg: str) -> tuple[Path, Path]:
    """Resolve (repo_root, workspace_root) from --workspace arg or GRAPH_WIKI_WORKSPACE env.

    Delegates to resolve_wiki_and_repo — the same helper scan uses — so repo_root
    is always resolved from cwd (the source repo), not from the workspace dir.
    This fixes the repo≠workspace layout where the workspace is its own git repo:
    previously resolve_config(workspace_arg) walked up from the workspace and bound
    repo_root to the workspace's .git, causing `git rev-parse HEAD` to die on a fresh
    wiki vault. (todo 260530-hxy)
    """
    if workspace_arg:
        wiki, repo = resolve_wiki_and_repo(Path(workspace_arg).resolve())
    else:
        wiki, repo = resolve_wiki_and_repo()
    # workspace_root is wiki.parent (resolve_wiki_and_repo returns wiki_dir == workspace/wiki).
    # Mirror scan.py's `_workspace_root = wiki.parent` convention.
    # If repo is None (no .git found anywhere), fall back to cwd — same as scan.py:455-461.
    return repo if repo is not None else Path.cwd(), wiki.parent
