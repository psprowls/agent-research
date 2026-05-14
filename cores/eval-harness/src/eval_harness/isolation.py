"""Vault isolation layer for eval sweeps.

EvalWorktree copies the source vault to a fresh tmpdir on enter and removes
the tmpdir on exit. This ensures each sweep run is isolated — trace JSONL
files from different runs don't collide, and no run can corrupt the fixture
vault source.

The copy includes .code-wiki/ (BM25 index + SQLite embedding DB) so indexes
travel with the vault. No index rebuild is needed at sweep time.

Threat mitigation T-4-01: source_vault is anchored to caller-supplied
Path; no user input is interpolated into the copy operation.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


class EvalWorktree:
    """Async context manager that copies a vault into a fresh tmpdir.

    Usage:
        async with EvalWorktree(source_vault) as wt:
            result = await run_query(query, vault_path=wt.path)

    The tmpdir (and all contents) is removed on __aexit__, even on error.
    Two concurrent EvalWorktrees always get distinct paths.
    """

    def __init__(self, source_vault: Path) -> None:
        self._source = source_vault
        self.path: Path | None = None
        self._tmp: str | None = None

    async def __aenter__(self) -> EvalWorktree:
        self._tmp = tempfile.mkdtemp(prefix="eval-wt-")
        self.path = Path(self._tmp) / "vault"
        shutil.copytree(self._source, self.path, dirs_exist_ok=False)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._tmp and Path(self._tmp).exists():
            shutil.rmtree(Path(self._tmp), ignore_errors=True)
