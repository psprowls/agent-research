"""Workspace path resolution for wiki-io.

Thin delegation shim over ``workspace_io.config.resolve()``. Resolution priority:

1. ``workspace_path`` argument — short-circuit (MCP boundary contract, Phase 11 SC#3).
   When an explicit path is supplied (e.g., from an MCP tool call) we trust it
   and skip workspace-io's manifest walk-up entirely.
2. ``workspace_io.config.resolve()`` — honors the ``GRAPH_WIKI_WORKSPACE`` env
   var, otherwise walks up from cwd looking for ``.graph-wiki.yaml``.
3. On failure, ``workspace_io.config.resolve()`` raises ``RuntimeError`` with a
   message naming ``gw bootstrap <path>`` as the bootstrap command.
"""

from __future__ import annotations

from pathlib import Path

from workspace_io import config as _ws_config
from workspace_io import paths as _ws_paths
from workspace_io.config import _find_repo_root, _repo_directory_override


def resolve_wiki_and_repo(
    workspace_path: Path | None = None,
    repo_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. ``workspace_path`` argument if provided — short-circuit. When ``repo_path``
       is not supplied, walk up from ``Path.cwd()`` to find the repo root, then
       apply any ``repo-directory:`` pin from ``<workspace>/.graph-wiki.yaml``.
    2. ``GRAPH_WIKI_WORKSPACE`` env var (via ``workspace_io.config.resolve``).
    3. ``.graph-wiki.yaml`` walk-up from cwd (via ``workspace_io.config.resolve``).
    4. Raises ``RuntimeError`` — names ``gw bootstrap <path>`` as fix.

    ``repo_path`` always overrides the discovered repo root when provided,
    regardless of which branch resolved the workspace. Callers that pass
    ``repo_path`` (e.g. ``run_init``) get symmetric semantics — the override
    is never silently dropped.
    """
    if workspace_path is not None:
        if repo_path is not None:
            # Explicit override always wins — do not apply pin over it.
            return _ws_paths.wiki_dir(workspace_path), repo_path
        cwd_repo = _find_repo_root(Path.cwd())
        # Honor repo-directory: pin in <workspace>/.graph-wiki.yaml.
        # _repo_directory_override requires a non-None default; use workspace itself
        # as a sentinel when cwd repo discovery returned None, then check afterwards.
        sentinel = workspace_path if cwd_repo is None else cwd_repo
        resolved = _repo_directory_override(workspace_path, sentinel)
        # If both cwd_repo and pin are absent (resolved == sentinel == workspace), treat as None.
        repo = None if (cwd_repo is None and resolved == workspace_path) else resolved
        return _ws_paths.wiki_dir(workspace_path), repo
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), repo_path or cfg.repo_root
