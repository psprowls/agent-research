"""Backend selector for graph-wiki plugin shims.

Reads the [plugin] block from .graph-wiki.yaml via workspace_io.manifest.read().
Returns 'claude' (default) or 'bedrock' for a given command.
"""
from __future__ import annotations


def backend_for(command: str, repo_root: str | None = None) -> str:
    """Return 'claude' or 'bedrock' for the given command.

    Resolution order:
    1. plugin.backend_overrides[command]  (per-command override)
    2. plugin.backend_default             (global default)
    3. 'claude'                           (hard fallback — always safe)
    """
    try:
        from pathlib import Path
        import workspace_io.manifest as _manifest

        root = Path(repo_root) if repo_root else Path.cwd()
        cfg = _manifest.read(root)
        plugin = cfg.get("plugin", {})
        overrides = plugin.get("backend_overrides", {}) or {}
        if command in overrides:
            return overrides[command]
        return plugin.get("backend_default", "claude")
    except Exception:
        return "claude"
