"""Librarian grounding tools — 5 @tool callables wrapping graph_io.queries.

Built via `build_graph_tools(conn)` factory that captures the connection in
closure scope (LIBTOOLS-03). All tools return strings (LIBTOOLS-02) and route
results through `graph_io.render.render(...)` with a 50-row cap.

Decision references: D-01..D-12 in .planning/phases/37-librarian-grounding-tools/37-CONTEXT.md.
"""

from __future__ import annotations

import sqlite3

from graph_io import queries
from graph_io import render as _render
from langchain_core.tools import BaseTool, tool

_DESCRIBE_KINDS = (
    "package",
    "path",
    "repository",
    "domain",
    "entry_point",
    "test_suite",
)

_ROW_CAP = 50


def _missing(kind: str, identifier: str) -> str:
    """The recoverable not-found signal (D-12) — wording preserved verbatim."""
    return f"error: no {kind} named '{identifier}' found in graph"


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
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_describe(kind: str, identifier: str) -> str:
        """Describe a graph entity by kind and identifier.

        Args:
            kind: one of package|path|repository|domain|entry_point|test_suite.
            identifier: string; ignored when kind=repository.
        """
        if kind not in _DESCRIBE_KINDS:
            valid = ", ".join(_DESCRIBE_KINDS)
            return f"error: invalid kind '{kind}'; valid: {valid}"
        if kind == "repository":
            result = queries.describe_repository(conn)
            if result is None:
                return _missing(kind, identifier)
            return _render.format_repo(result, fmt="human")
        if kind == "package":
            result = queries.describe_package(conn, name=identifier)
            return _render.format_package(result, fmt="human") if result else _missing(kind, identifier)
        if kind == "path":
            result = queries.describe_path(conn, path=identifier)
            return _render.format_path(result, fmt="human") if result else _missing(kind, identifier)
        if kind == "test_suite":
            result = queries.describe_test_suite(conn, suite_name=identifier)
            return _render.format_suite(result, fmt="human") if result else _missing(kind, identifier)
        if kind == "domain":
            result = queries.describe_domain(conn, name=identifier)
            if result is None:
                return _missing(kind, identifier)
            packages, subdomains = queries.domain_members(conn, identifier)
            return _render.format_domain(result, packages, subdomains, fmt="human")
        # entry_point: needs "<package>:<entry>". Reject other shapes with the
        # standard not-found string so the LLM gets a recoverable signal (D-12)
        # rather than an exception.
        if ":" not in identifier:
            return _missing(kind, identifier)
        package_name, _, entry_name = identifier.partition(":")
        result = queries.describe_entry_point(conn, package_name=package_name, entry_name=entry_name)
        return _render.format_entry_point(result, fmt="human") if result else _missing(kind, identifier)

    @tool
    def cg_callers(name: str, depth: int = 3) -> str:
        """Find callers of a function/method up to `depth` levels deep.

        Args:
            name: required symbol name.
            depth: default 3, integer.
        """
        rows = queries.callers(conn, name=name, depth=depth)
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_callees(name: str, depth: int = 3) -> str:
        """Find callees of a function/method up to `depth` levels deep.

        Args:
            name: required symbol name.
            depth: default 3, integer.
        """
        rows = queries.callees(conn, name=name, depth=depth)
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_imports(path: str) -> str:
        """List modules imported by a source file (repo-relative path).

        Args:
            path: required, repo-relative.
        """
        rows = queries.imports(conn, path=path)
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    return [cg_find, cg_describe, cg_callers, cg_callees, cg_imports]
