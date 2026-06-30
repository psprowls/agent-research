"""Workspace isolation layer for eval sweeps.

EvalWorktree copies the source wiki into a fresh tmpdir laid out as a
graph-wiki workspace (wiki content under ``<tmp>/wiki``) on enter and
removes the tmpdir on exit. This matches the post-Phase-22 API contract
(D-09: wiki is always derived as workspace_path/wiki) so callers can pass
``workspace_path=wt.path`` directly.

The source vault's ``.graph-wiki/`` (BM25 index + SQLite embedding DB + traces)
is relocated to the workspace-level ``<tmp>/.graph-wiki/`` so the consolidated
resolver finds the indexes — they travel with the wiki and no rebuild is needed
at sweep time. An empty, schema-valid graph DB is also provisioned at
``<tmp>/.graph-wiki/code.db`` so the ingestor can open it without raising
IngestorGraphNotInitializedError.

Threat mitigation T-4-01: source_wiki is anchored to caller-supplied
Path; no user input is interpolated into the copy operation.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import graph_io
from workspace_io.paths import graph_dir


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
        # Current fixtures store machine state at <workspace>/.graph-wiki. Keep
        # the legacy <wiki>/.graph-wiki fallback for older external eval corpora.
        source_ws_meta = graph_dir(self._source.parent)
        if source_ws_meta.exists():
            shutil.copytree(source_ws_meta, graph_dir(self.path), dirs_exist_ok=True)
        wiki_meta = self.path / "wiki" / ".graph-wiki"
        ws_meta = graph_dir(self.path)
        if wiki_meta.exists():
            shutil.move(str(wiki_meta), str(ws_meta))
        ws_meta.mkdir(parents=True, exist_ok=True)
        graph_io.open_writer(self.path, create=True).close()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._tmp and Path(self._tmp).exists():
            shutil.rmtree(Path(self._tmp), ignore_errors=True)
