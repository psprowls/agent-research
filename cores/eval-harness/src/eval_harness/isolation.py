from __future__ import annotations

"""EvalWorktree: isolated copy of a vault for one eval run.

Creates a temporary directory, copies the source vault into it via
shutil.copytree, and cleans up on __aexit__. The .code-wiki/ subdirectory
(pre-built BM25 + SQLite indexes) is included in the copy so each run
starts with a fully-initialized vault.

This is a simplified port of lattice-evals/isolation.py — the OAuth,
git-worktree, and CLAUDE_CONFIG_DIR management sections are dropped
because the code-wiki-agent eval uses --plugin-dir flags instead.

Threat mitigation T-4-01: source_vault is anchored to caller-supplied
Path; no user input is interpolated into the copy operation.
"""

import shutil
import tempfile
from pathlib import Path


class EvalWorktree:
    """Isolated copy of a vault for one eval run.

    Uses shutil.copytree into a tempdir — not a git worktree.
    Sufficient for read-heavy query eval where git history is irrelevant.
    Cleans up on __aexit__.

    Usage::

        async with EvalWorktree(vault_path) as wt:
            result = run_headless(prompt=..., worktree_path=wt.path, ...)
    """

    def __init__(self, source_vault: Path) -> None:
        self._source = source_vault
        self.path: Path | None = None
        self._tmp: Path | None = None

    async def __aenter__(self) -> EvalWorktree:
        self._tmp = Path(tempfile.mkdtemp(prefix="eval-wt-"))
        self.path = self._tmp / "vault"
        shutil.copytree(self._source, self.path, dirs_exist_ok=False)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._tmp and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
