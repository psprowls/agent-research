"""Workspace resolution: cwd -> GraphWikiConfig.

Discovery walks up from cwd looking for `.git`. Once the repo root is
found, `.graph-wiki.local.yaml` is consulted for the `graph-wiki-directory`
key. Falls back to `<repo>/graph-wiki` when the key is absent.

Environment variable `GRAPH_WIKI_WORKSPACE` overrides discovery and pins
a workspace directory directly (used by tests and tools that need explicit
workspace injection).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from workspace_io import _local_config

LOCAL_CONFIG_FILENAME = ".graph-wiki.local.yaml"
LATTICE_DIRECTORY_KEY = "graph-wiki-directory"
DEFAULT_WORKSPACE_NAME = "graph-wiki"


@dataclass(frozen=True)
class GraphWikiConfig:
    workspace: Path
    repo_root: Path


def _find_repo_root(start: Path) -> Path | None:
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _resolve_workspace(repo_root: Path) -> Path:
    local = _local_config.read(repo_root / LOCAL_CONFIG_FILENAME)
    raw = local.get(LATTICE_DIRECTORY_KEY, "").strip()
    if not raw:
        return (repo_root / DEFAULT_WORKSPACE_NAME).resolve()
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (repo_root / expanded).resolve()


def resolve(cwd: Path | None = None) -> GraphWikiConfig:
    """Resolve the GraphWikiConfig for the given working directory.

    Checks GRAPH_WIKI_WORKSPACE env var first for explicit override (used by tests).
    Falls back to discovery from cwd; raises RuntimeError if no `.graph-wiki.yaml`
    is found in the resolved workspace (D-03: strict).
    """
    # Check env var override first (does NOT enforce strict-manifest check;
    # env override must work even before a manifest is written so tests can
    # use it).
    env_workspace = os.environ.get("GRAPH_WIKI_WORKSPACE", "").strip()
    if env_workspace:
        workspace = Path(env_workspace).expanduser().resolve()
        # Still find repo_root by walking up from workspace
        repo_root = _find_repo_root(workspace) or workspace.parent.resolve()
        return GraphWikiConfig(workspace=workspace, repo_root=repo_root)

    # Normal discovery path
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    repo_root = _find_repo_root(cwd) or cwd.resolve()
    workspace = _resolve_workspace(repo_root)
    # D-03: strict — raise if no .graph-wiki.yaml present in the resolved workspace.
    manifest = workspace / ".graph-wiki.yaml"
    if not manifest.exists():
        raise RuntimeError(
            f"No .graph-wiki.yaml found in {workspace}. "
            f"Run: code-wiki-agent init <path>"
        )
    return GraphWikiConfig(workspace=workspace, repo_root=repo_root)


def _main() -> int:
    print(resolve().workspace)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
