"""Workspace resolution: cwd -> GraphWikiConfig.

Discovery walks up from cwd looking for `.git`. Once the repo root is
found, `.graph-wiki.local.yaml` is consulted for the `workspace-directory`
key. Falls back to `<repo>/graph-wiki` when the key is absent.

Environment variable `GRAPH_WIKI_WORKSPACE` overrides discovery and pins
a workspace directory directly (used by tests and tools that need explicit
workspace injection).

The workspace manifest (`.graph-wiki.yaml`, layered with
`.graph-wiki.local.yaml` on top) may also declare a `repo-directory:` key
to pin the repo root explicitly — useful when the workspace itself lives
in its own git repo (e.g. a separate wiki repo describing a source repo
elsewhere on disk), where `.git`-discovery would otherwise bind to the
wiki's own repo.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from workspace_io import _local_config

LOCAL_CONFIG_FILENAME = ".graph-wiki.local.yaml"
WORKSPACE_DIRECTORY_KEY = "workspace-directory"
REPO_DIRECTORY_KEY = "repo-directory"
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


def _repo_directory_override(workspace: Path, repo_root_default: Path) -> Path:
    """Consult `<workspace>/.graph-wiki.yaml` + `.graph-wiki.local.yaml` for `repo-directory:`.

    Local overrides committed manifest (same precedence as `workspace-directory`).
    `~` is expanded; relative paths resolve against `workspace`. Returns
    `repo_root_default` unchanged when the key is absent or blank.
    """
    committed = _local_config.read(workspace / ".graph-wiki.yaml")
    local = _local_config.read(workspace / LOCAL_CONFIG_FILENAME)
    merged = {**committed, **local}
    raw = merged.get(REPO_DIRECTORY_KEY, "").strip()
    if not raw:
        return repo_root_default
    expanded = Path(raw).expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (workspace / expanded).resolve()


def resolve_workspace(repo_root: Path) -> Path:
    local = _local_config.read(repo_root / LOCAL_CONFIG_FILENAME)
    raw = local.get(WORKSPACE_DIRECTORY_KEY, "").strip()
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
        # Default: walk up from workspace for .git, then let the workspace
        # manifest's `repo-directory:` (if set) override.
        repo_root = _find_repo_root(workspace) or workspace.parent.resolve()
        repo_root = _repo_directory_override(workspace, repo_root)
        return GraphWikiConfig(workspace=workspace, repo_root=repo_root)

    # Normal discovery path
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    repo_root = _find_repo_root(cwd) or cwd.resolve()
    workspace = resolve_workspace(repo_root)
    # D-03: strict — raise if no .graph-wiki.yaml present in the resolved workspace.
    manifest = workspace / ".graph-wiki.yaml"
    if not manifest.exists():
        raise RuntimeError(
            f"No .graph-wiki.yaml found in {workspace}. "
            f"Run: graph-wiki-agent bootstrap <path>"
        )
    # Workspace manifest may pin a different repo_root explicitly.
    repo_root = _repo_directory_override(workspace, repo_root)
    return GraphWikiConfig(workspace=workspace, repo_root=repo_root)


def _main() -> int:
    print(resolve().workspace)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
