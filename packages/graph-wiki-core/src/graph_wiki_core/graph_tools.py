"""Librarian grounding tools — 5 @tool callables wrapping a graph_io.GraphReader.

Built via `build_graph_tools(reader)` factory that captures the reader in
closure scope (LIBTOOLS-03). All tools return strings (LIBTOOLS-02). The
multi-row tools (`cg_find`/`cg_callers`/`cg_callees`/`cg_imports`) route results
through `graph_io.render.render(...)` with a 50-row cap; `cg_describe` renders
each entity via the per-kind `graph_io.render.format_<kind>` spine formatters
(the sectioned spine).

Decision references: D-01..D-12 in .planning/phases/37-librarian-grounding-tools/37-CONTEXT.md.
"""

from __future__ import annotations

from graph_io import GraphReader
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


def build_graph_tools(reader: GraphReader) -> list[BaseTool]:
    """Return the 5 librarian @tool callables, each closed over `reader`.

    Reader lifetime is the caller's responsibility: open via
    `graph_io.open_reader(workspace)` at command entry, pass into this factory,
    close in `finally` (LIBTOOLS-03).
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
            rows = reader.find(name=name, kind=kind, in_package=in_package)
        except ValueError as exc:
            return f"error: {exc}"
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_describe(kind: str, identifier: str) -> str:
        """Describe a graph entity by kind and identifier.

        Args:
            kind: one of package|path|repository|domain|entry_point|test_suite.
            identifier: string; ignored when kind=repository. For
                entry_point, the qualified ``package:entry`` form is required
                (bare entry names are not resolved here — the CLI/core router
                handles bare names; this grounding tool requires the qualified
                form).
        """
        if kind not in _DESCRIBE_KINDS:
            valid = ", ".join(_DESCRIBE_KINDS)
            return f"error: invalid kind '{kind}'; valid: {valid}"
        if kind == "repository":
            result = reader.describe_repository()
            if result is None:
                return _missing(kind, identifier)
            children, eff = reader.children_for(kind="repository", name=result.name, depth=None)
            return _render.format_repo(result, fmt="human", children=children, effective_depth=eff)
        if kind == "package":
            result = reader.describe_package(name=identifier)
            if result is None:
                return _missing(kind, identifier)
            children, eff = reader.children_for(kind="package", name=result.name, depth=None)
            return _render.format_package(result, fmt="human", children=children, effective_depth=eff)
        if kind == "path":
            result = reader.describe_path(path=identifier)
            if result is None:
                return _missing(kind, identifier)
            children, eff = reader.children_for(kind="file", path=result.path, depth=None)
            return _render.format_path(result, fmt="human", children=children, effective_depth=eff)
        if kind == "test_suite":
            result = reader.describe_test_suite(suite_name=identifier)
            if result is None:
                return _missing(kind, identifier)
            children, eff = reader.children_for(kind="test_suite", name=result.name, depth=None)
            return _render.format_suite(result, fmt="human", children=children, effective_depth=eff)
        if kind == "domain":
            result = reader.describe_domain(name=identifier)
            if result is None:
                return _missing(kind, identifier)
            packages, subdomains = reader.domain_members(identifier)
            children, eff = reader.children_for(kind="domain", name=result.name, depth=None)
            return _render.format_domain(
                result, packages, subdomains, fmt="human", children=children, effective_depth=eff
            )
        if kind == "entry_point":
            # entry_point: needs "<package>:<entry>". Reject other shapes with the
            # standard not-found string so the LLM gets a recoverable signal (D-12)
            # rather than an exception.
            if ":" not in identifier:
                return _missing(kind, identifier)
            package_name, _, entry_name = identifier.partition(":")
            result = reader.describe_entry_point(package_name=package_name, entry_name=entry_name)
            return _render.format_entry_point(result, fmt="human") if result else _missing(kind, identifier)
        # Unreachable today (every _DESCRIBE_KINDS value has a branch above); guards
        # against a future kind added to the enum without a matching branch leaking None.
        return f"error: unhandled kind '{kind}'"

    @tool
    def cg_callers(name: str, depth: int = 3) -> str:
        """Find callers of a function/method up to `depth` levels deep.

        Args:
            name: required symbol name.
            depth: default 3, integer.
        """
        rows = reader.callers(name=name, depth=depth)
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_callees(name: str, depth: int = 3) -> str:
        """Find callees of a function/method up to `depth` levels deep.

        Args:
            name: required symbol name.
            depth: default 3, integer.
        """
        rows = reader.callees(name=name, depth=depth)
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    @tool
    def cg_imports(path: str) -> str:
        """List modules imported by a source file (repo-relative path).

        Args:
            path: required, repo-relative.
        """
        rows = reader.imports(path=path)
        return _render.render(rows, fmt="human", cap=_ROW_CAP)

    return [cg_find, cg_describe, cg_callers, cg_callees, cg_imports]
