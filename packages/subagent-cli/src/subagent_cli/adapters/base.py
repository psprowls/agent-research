"""Adapter protocol, run context, and the prepared-invocation payload."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

from graph_io import store


@dataclass
class RunContext:
    """Resolved workspace paths plus a lazily-opened read-only graph connection."""

    workspace: Path
    repo_root: Path
    wiki: Path
    db_path: Path
    _conn: sqlite3.Connection | None = field(default=None, repr=False)

    def graph_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = store.read_only_connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


@dataclass
class Prepared:
    """One subagent invocation's real inputs: the genuine prompt + parser."""

    item_id: str
    system: str
    human: str
    parse: Callable[[str], Any] | None = None
    note: str | None = None


@runtime_checkable
class Adapter(Protocol):
    name: str
    role: str  # model-adapter role → resolves the model
    selector: str  # "file" | "package" | "query"
    supports_all: bool  # True only for worklist adapters

    async def prepare(self, ctx: RunContext, item: str) -> Prepared: ...

    def items(self, ctx: RunContext) -> list[str]:
        """Real worklist for --all; raises for single-query adapters."""
        ...
