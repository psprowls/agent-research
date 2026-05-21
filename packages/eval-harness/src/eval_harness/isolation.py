"""Workspace isolation layer for eval sweeps.

EvalWorktree copies the source wiki into a fresh tmpdir laid out as a
graph-wiki workspace (wiki content under ``<tmp>/wiki``) on enter and
removes the tmpdir on exit. This matches the post-Phase-22 API contract
(D-09: wiki is always derived as workspace_path/wiki) so callers can pass
``workspace_path=wt.path`` directly.

The copy includes .graph-wiki/ (BM25 index + SQLite embedding DB) so indexes
travel with the wiki. No index rebuild is needed at sweep time.

Threat mitigation T-4-01: source_wiki is anchored to caller-supplied
Path; no user input is interpolated into the copy operation.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


class EvalWorktree:
    """Async context manager that materialises a workspace tmpdir.

    Usage:
        async with EvalWorktree(source_wiki) as wt:
            result = await run_query(query, workspace_path=wt.path)

    ``wt.path`` is the workspace root; the wiki content lives at
    ``wt.path / "wiki"``. The tmpdir (and all contents) is removed on
    __aexit__, even on error. Two concurrent EvalWorktrees always get
    distinct paths.
    """

    def __init__(self, source_wiki: Path) -> None:
        self._source = source_wiki
        self.path: Path | None = None
        self._tmp: str | None = None

    async def __aenter__(self) -> EvalWorktree:
        self._tmp = tempfile.mkdtemp(prefix="eval-wt-")
        self.path = Path(self._tmp)
        shutil.copytree(self._source, self.path / "wiki", dirs_exist_ok=False)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._tmp and Path(self._tmp).exists():
            shutil.rmtree(Path(self._tmp), ignore_errors=True)
