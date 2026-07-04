"""Backend selector for graph-wiki plugin shims.

Resolves the workspace via `workspace_io.resolve()` (the same resolver every
other surface uses — `GRAPH_WIKI_WORKSPACE` is the only external-workspace
pointer; a legacy repo-side `.graph-wiki.local.yaml` `workspace-directory` key
is inert) and reads the `[plugin]` block from `<workspace>/.graph-wiki.yaml`.
Returns 'claude' (default) or 'bedrock'.
"""

from __future__ import annotations


def backend_for(command: str, repo_root: str | None = None) -> str:
    """Return 'claude' or 'bedrock' for the given command.

    Resolution order:
    1. plugin.backend_overrides[command]  (per-command override)
    2. plugin.backend_default             (global default)
    3. 'claude'                           (hard fallback — always safe)

    The `[plugin]` block is read from the resolved workspace manifest
    (`<workspace>/.graph-wiki.yaml`), NOT from cwd. `repo_root`, when given,
    seeds workspace discovery (walk-up for `.git`; the legacy
    `.graph-wiki.local.yaml` `workspace-directory` key is not consulted).
    """
    try:
        from pathlib import Path

        import workspace_io.manifest as _manifest
        from workspace_io import resolve

        cfg = resolve(cwd=Path(repo_root) if repo_root else None)
        plugin = _manifest.read(cfg.workspace / ".graph-wiki.yaml").get("plugin", {}) or {}
        overrides = plugin.get("backend_overrides", {}) or {}
        if command in overrides:
            return overrides[command]
        return plugin.get("backend_default", "claude")
    except Exception:
        return "claude"
