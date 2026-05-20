"""Workspace path resolution for vault-io.

Thin delegation shim over ``workspace_io.config.resolve()``. Resolution priority:

1. ``vault_path`` argument — short-circuit (MCP boundary contract, Phase 11 SC#3).
   When an explicit path is supplied (e.g., from an MCP tool call) we trust it
   and skip workspace-io's manifest walk-up entirely.
2. ``workspace_io.config.resolve()`` — honors the ``GRAPH_WIKI_WORKSPACE`` env
   var, otherwise walks up from cwd looking for ``.graph-wiki.yaml``.
3. On failure, ``workspace_io.config.resolve()`` raises ``RuntimeError`` with a
   message naming ``graph-wiki-agent init <path>`` as the bootstrap command.
"""

from __future__ import annotations

from pathlib import Path

from workspace_io import config as _ws_config
from workspace_io import paths as _ws_paths
from workspace_io.config import _find_repo_root


def resolve_wiki_and_repo(
    vault_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. ``vault_path`` argument if provided — short-circuit. ``repo_root`` is
       discovered by walking up from ``vault_path`` looking for ``.git``.
    2. ``GRAPH_WIKI_WORKSPACE`` env var (via ``workspace_io.config.resolve``).
    3. ``.graph-wiki.yaml`` walk-up from cwd (via ``workspace_io.config.resolve``).
    4. Raises ``RuntimeError`` — names ``graph-wiki-agent init <path>`` as fix.
    """
    if vault_path is not None:
        return vault_path.resolve(), _find_repo_root(vault_path)
    cfg = _ws_config.resolve()
    return _ws_paths.wiki_dir(cfg.workspace), cfg.repo_root
