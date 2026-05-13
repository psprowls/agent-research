"""Workspace path resolution for vault-io.

In deep-agents, the vault path is always supplied explicitly via the
CODE_WIKI_REAL_VAULT_PATH environment variable or as a direct Path argument.
There is no lattice-workspace discovery in this codebase.
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_wiki_and_repo(
    vault_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. ``vault_path`` argument if provided
    2. ``CODE_WIKI_REAL_VAULT_PATH`` env var
    3. Raises RuntimeError — no fallback heuristic (avoids wrong-path silent failures).

    repo_root is always None in v1; Phase 5 may extend this to discover the
    repo root from the vault path layout, but for now consumers should pass
    repo paths explicitly when they need them.
    """
    if vault_path is not None:
        return vault_path.resolve(), None
    env = os.environ.get("CODE_WIKI_REAL_VAULT_PATH")
    if env:
        return Path(env).resolve(), None
    raise RuntimeError(
        "Vault path not specified. "
        "Set CODE_WIKI_REAL_VAULT_PATH or pass vault_path explicitly."
    )
