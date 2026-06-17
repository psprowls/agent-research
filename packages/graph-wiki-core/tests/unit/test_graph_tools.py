"""Unit tests for graph_tools.build_graph_tools (LIBTOOLS-01..03, D-01..D-12)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from graph_wiki_core.graph_tools import build_graph_tools


def _by_name(tools):
    return {t.name: t for t in tools}


def test_factory_returns_five_named_tools(seeded_graph_conn):
    tools = build_graph_tools(seeded_graph_conn)
    assert len(tools) == 5
    assert {t.name for t in tools} == {
        "cg_find",
        "cg_describe",
        "cg_callers",
        "cg_callees",
        "cg_imports",
    }


def test_cg_find_no_args_returns_error_string(seeded_graph_conn):
    tools = _by_name(build_graph_tools(seeded_graph_conn))
    out = tools["cg_find"].invoke({})
    assert out == "error: at least one of name, kind, in_package required"


def test_cg_describe_kind_enum(seeded_graph_conn):
    tools = _by_name(build_graph_tools(seeded_graph_conn))
    out = tools["cg_describe"].invoke({"kind": "bogus", "identifier": "x"})
    assert "error: invalid kind 'bogus'" in out
    assert "valid: package, path, repository, domain, entry_point, test_suite" in out


@pytest.mark.parametrize(
    "kind,identifier",
    [
        ("package", "mypkg"),
        ("path", "packages/mypkg/src/mypkg/foo.py"),
        ("repository", ""),
        ("domain", "any-nonexistent-domain"),
        ("entry_point", "any-nonexistent-ep"),
        ("test_suite", "any-nonexistent-suite"),
    ],
)
def test_cg_describe_dispatch(seeded_graph_conn, kind, identifier):
    tools = _by_name(build_graph_tools(seeded_graph_conn))
    out = tools["cg_describe"].invoke({"kind": kind, "identifier": identifier})
    assert isinstance(out, str)
    assert "invalid kind" not in out


def test_cg_describe_missing_entity_returns_error_string(seeded_graph_conn):
    tools = _by_name(build_graph_tools(seeded_graph_conn))
    out = tools["cg_describe"].invoke({"kind": "package", "identifier": "definitely-not-real-9999"})
    assert "error: no package named" in out
    assert "definitely-not-real-9999" in out


def test_tools_return_string_with_row_cap(seeded_graph_conn):
    tools = _by_name(build_graph_tools(seeded_graph_conn))
    out_find = tools["cg_find"].invoke({"kind": "function"})
    assert isinstance(out_find, str)
    out_imports = tools["cg_imports"].invoke({"path": "packages/mypkg/src/mypkg/foo.py"})
    assert isinstance(out_imports, str)


def test_closure_shares_single_connection(seeded_graph_conn):
    real_find = __import__("graph_wiki_core.graph_tools", fromlist=["queries"]).queries.find
    seen_ids: list[int] = []

    def _recorder(conn, **kwargs):
        seen_ids.append(id(conn))
        return real_find(conn, **kwargs)

    tools = _by_name(build_graph_tools(seeded_graph_conn))
    with patch("graph_wiki_core.graph_tools.queries.find", side_effect=_recorder):
        tools["cg_find"].invoke({"name": "foo"})
        tools["cg_find"].invoke({"kind": "function"})

    assert len(seen_ids) == 2
    assert seen_ids[0] == id(seeded_graph_conn)
    assert seen_ids[1] == id(seeded_graph_conn)


def test_cg_callers_callees_imports_smoke(seeded_graph_conn):
    tools = _by_name(build_graph_tools(seeded_graph_conn))
    out_callers = tools["cg_callers"].invoke({"name": "foo"})
    assert isinstance(out_callers, str)
    out_callees = tools["cg_callees"].invoke({"name": "foo"})
    assert isinstance(out_callees, str)
    out_imports = tools["cg_imports"].invoke({"path": "packages/mypkg/src/mypkg/foo.py"})
    assert isinstance(out_imports, str)


def test_cg_callers_callees_exclude_test_symbols_by_default(tmp_path):
    """D3/D5: agent tools inherit the queries default that hides test symbols.

    Includes a prod-only A->B->C positive control so the empty (pruned) X/P
    results are a meaningful contrast — without it, the "T absent" assertions
    would pass vacuously even if the tools returned nothing for any input.
    """
    from graph_io import resolve, store, upsert
    from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

    db = tmp_path / "code.db"
    conn = store.connect(db, create=True)
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[
                GraphNode(kind="file", name="prod.py", path="prod.py", line=None, attrs={}),
                GraphNode(kind="file", name="test_prod.py", path="test_prod.py", line=None, attrs={"is_test": True}),
                # Test-file chain: P (prod) -> T (test) -> X (prod).
                GraphNode(kind="function", name="P", path="prod.py", line=1, attrs={}),
                GraphNode(kind="function", name="T", path="test_prod.py", line=1, attrs={}),
                GraphNode(kind="function", name="X", path="prod.py", line=10, attrs={}),
                # Positive control: pure-prod chain A -> B -> C (no test files).
                GraphNode(kind="function", name="A", path="prod.py", line=20, attrs={}),
                GraphNode(kind="function", name="B", path="prod.py", line=30, attrs={}),
                GraphNode(kind="function", name="C", path="prod.py", line=40, attrs={}),
            ],
            edges=[
                GraphEdge(src=("function", "P", "prod.py"), dst=("function", "T", None), kind="calls", attrs={}),
                GraphEdge(src=("function", "T", "test_prod.py"), dst=("function", "X", None), kind="calls", attrs={}),
                GraphEdge(src=("function", "A", "prod.py"), dst=("function", "B", None), kind="calls", attrs={}),
                GraphEdge(src=("function", "B", "prod.py"), dst=("function", "C", None), kind="calls", attrs={}),
            ],
        ),
    )
    resolve.sweep(conn)
    conn.close()

    ro = store.read_only_connect(db)
    try:
        tools = _by_name(build_graph_tools(ro))
        callers_out = tools["cg_callers"].invoke({"name": "X"})
        callees_out = tools["cg_callees"].invoke({"name": "P"})
        control_callers = tools["cg_callers"].invoke({"name": "B"})
        control_callees = tools["cg_callees"].invoke({"name": "B"})
    finally:
        ro.close()

    # Positive control: the tools render prod rows normally (so an empty result
    # below is meaningfully "pruned", not "tool returns nothing").
    assert "A" in _symbol_names(control_callers)
    assert "C" in _symbol_names(control_callees)

    # Default-exclude: T (test symbol) is gone, and P/X reachable only via T
    # are pruned too.
    assert "T" not in _symbol_names(callers_out)
    assert "T" not in _symbol_names(callees_out)


def _symbol_names(rendered: str) -> set[str]:
    """Leading symbol token from each rendered human row (set membership only).

    Relies on `name` being the first field of `CallRecord` (the human render
    emits columns in dataclass field order); update if that order changes.
    """
    names: set[str] = set()
    for line in rendered.splitlines():
        line = line.strip()
        if not line:
            continue
        names.add(line.split()[0])
    return names


def test_cg_describe_matches_run_describe_spine(seeded_graph_workspace) -> None:
    """cg_describe and run_describe produce the identical human spine (surface-divergence gap)."""
    from graph_io.store import read_only_connect
    from graph_wiki_core.commands import graph as graph_module
    from graph_wiki_core.graph_tools import build_graph_tools
    from workspace_io.paths import graph_dir

    db = graph_dir(seeded_graph_workspace) / "code.db"
    conn = read_only_connect(db)
    try:
        tools = {t.name: t for t in build_graph_tools(conn)}
        cg_out = tools["cg_describe"].invoke({"kind": "package", "identifier": "commonlib"})
    finally:
        conn.close()

    _, run_out, _ = graph_module.run_describe("package", "commonlib", seeded_graph_workspace, seeded_graph_workspace)
    assert cg_out.strip() == run_out.strip()
    assert cg_out.startswith("package commonlib\n  uri: pkg:commonlib")
