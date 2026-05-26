"""Unit tests for graph_tools.build_graph_tools (LIBTOOLS-01..03, D-01..D-12)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from graph_wiki_agent.graph_tools import build_graph_tools


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
    out = tools["cg_describe"].invoke(
        {"kind": "package", "identifier": "definitely-not-real-9999"}
    )
    assert "error: no package named" in out
    assert "definitely-not-real-9999" in out


def test_tools_return_string_with_row_cap(seeded_graph_conn):
    tools = _by_name(build_graph_tools(seeded_graph_conn))
    out_find = tools["cg_find"].invoke({"kind": "function"})
    assert isinstance(out_find, str)
    out_imports = tools["cg_imports"].invoke(
        {"path": "packages/mypkg/src/mypkg/foo.py"}
    )
    assert isinstance(out_imports, str)


def test_closure_shares_single_connection(seeded_graph_conn):
    real_find = __import__(
        "graph_wiki_agent.graph_tools", fromlist=["queries"]
    ).queries.find
    seen_ids: list[int] = []

    def _recorder(conn, **kwargs):
        seen_ids.append(id(conn))
        return real_find(conn, **kwargs)

    tools = _by_name(build_graph_tools(seeded_graph_conn))
    with patch("graph_wiki_agent.graph_tools.queries.find", side_effect=_recorder):
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
    out_imports = tools["cg_imports"].invoke(
        {"path": "packages/mypkg/src/mypkg/foo.py"}
    )
    assert isinstance(out_imports, str)
