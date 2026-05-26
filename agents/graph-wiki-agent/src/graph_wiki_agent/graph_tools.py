"""Librarian grounding tools — 5 @tool callables wrapping graph_io.queries.

Built via `build_graph_tools(conn)` factory that captures the connection in
closure scope (LIBTOOLS-03). All tools return strings (LIBTOOLS-02) and route
results through `graph_io.cli._format.render(...)` with a 50-row cap.

Decision references: D-01..D-12 in .planning/phases/37-librarian-grounding-tools/37-CONTEXT.md.
"""

from __future__ import annotations

import sqlite3
from typing import Callable

from graph_io import queries
from graph_io.cli._format import render
from langchain_core.tools import BaseTool, tool

_DESCRIBE_KINDS = (
    "package",
    "path",
    "repository",
    "domain",
    "entry_point",
    "test_suite",
)

_DESCRIBE_DISPATCH: dict[str, Callable] = {
    "package": queries.describe_package,
    "path": queries.describe_path,
    "repository": queries.describe_repository,
    "domain": queries.describe_domain,
    "entry_point": queries.describe_entry_point,
    "test_suite": queries.describe_test_suite,
}

_ROW_CAP = 50


def build_graph_tools(conn: sqlite3.Connection) -> list[BaseTool]:
    """Return the 5 librarian @tool callables, each closed over `conn`.

    Connection lifetime is the caller's responsibility: open via
    `graph_io.store.read_only_connect()` at command entry, pass into this
    factory, close in `finally` (LIBTOOLS-03).
    """

    @tool
    def cg_find(
        name: str | None = None,
        kind: str | None = None,
        in_package: str | None = None,
    ) -> str:
        """Find nodes by name and/or kind and/or containing package.

        Args:
            name: optional symbol name (exact match).
            kind: optional; one of class|function|file|module|package|domain|entry_point|test_suite.
            in_package: optional case-insensitive package name.
        """
        if name is None and kind is None and in_package is None:
            return "error: at least one of name, kind, in_package required"
        try:
            rows = queries.find(conn, name=name, kind=kind, in_package=in_package)
        except ValueError as exc:
            return f"error: {exc}"
        return render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_describe(kind: str, identifier: str) -> str:
        """Describe a graph entity by kind and identifier.

        Args:
            kind: one of package|path|repository|domain|entry_point|test_suite.
            identifier: string; ignored when kind=repository.
        """
        if kind not in _DESCRIBE_DISPATCH:
            valid = ", ".join(_DESCRIBE_KINDS)
            return f"error: invalid kind '{kind}'; valid: {valid}"
        fn = _DESCRIBE_DISPATCH[kind]
        if kind == "repository":
            result = fn(conn)
        elif kind == "path":
            result = fn(conn, path=identifier)
        else:
            result = fn(conn, name=identifier)
        if result is None:
            return f"error: no {kind} named '{identifier}' found in graph"
        return render([result], fmt="human", cap=_ROW_CAP)

    @tool
    def cg_callers(name: str, depth: int = 3) -> str:
        """Find callers of a function/method up to `depth` levels deep.

        Args:
            name: required symbol name.
            depth: default 3, integer.
        """
        rows = queries.callers(conn, name=name, depth=depth)
        return render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_callees(name: str, depth: int = 3) -> str:
        """Find callees of a function/method up to `depth` levels deep.

        Args:
            name: required symbol name.
            depth: default 3, integer.
        """
        rows = queries.callees(conn, name=name, depth=depth)
        return render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_imports(path: str) -> str:
        """List modules imported by a source file (repo-relative path).

        Args:
            path: required, repo-relative.
        """
        rows = queries.imports(conn, path=path)
        return render(rows, fmt="human", cap=_ROW_CAP)

    return [cg_find, cg_describe, cg_callers, cg_callees, cg_imports]
