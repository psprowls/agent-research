"""Tests for the public graph_io.render module."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from graph_io import render


@dataclass(frozen=True)
class Row:
    kind: str
    name: str
    path: str
    line: int


# ── Public module existence ────────────────────────────────────────────────────


def test_render_module_has_all_format_functions() -> None:
    for name in ["format_package", "format_path", "format_repo", "format_domain", "format_entry_point", "format_suite"]:
        assert hasattr(render, name), f"render.{name} missing"


# ── render() works identically when called from render module directly ─────────


def test_render_json_via_public_module() -> None:
    rows = [Row("function", "foo", "a.py", 10)]
    out = render.render(rows, fmt="json")
    assert json.loads(out) == [{"kind": "function", "name": "foo", "path": "a.py", "line": 10}]


def test_render_human_via_public_module() -> None:
    rows = [Row("function", "foo", "a.py", 10)]
    out = render.render(rows, fmt="human")
    assert "function" in out
    assert "foo" in out


def test_render_invalid_format_via_public_module() -> None:
    with pytest.raises(ValueError):
        render.render([], fmt="xml")


# ── format_* output spot-checks (not byte-identical — that's in test_cli_describe.py) ──


def test_format_package_human_contains_expected_keys() -> None:
    """format_package human output includes the standard key labels."""
    from graph_io.queries import PackageDescription

    desc = PackageDescription(
        name="mypkg",
        language="python",
        version="1.0",
        files=["a.py", "b.py"],
        counts={"function": 2},
        internal_dependencies=["other"],
        internal_dependents=[],
    )
    out = render.format_package(desc, fmt="human")
    assert "package: mypkg" in out
    assert "language: python" in out
    assert "files:    2" in out
    assert "internal deps:       other" in out
    assert "internal dependents: -" in out


def test_format_package_json_is_asdict() -> None:
    import dataclasses

    from graph_io.queries import PackageDescription

    desc = PackageDescription(
        name="mypkg",
        language="python",
        version="1.0",
        files=["a.py"],
        counts={},
        internal_dependencies=[],
        internal_dependents=[],
    )
    out = render.format_package(desc, fmt="json")
    assert json.loads(out) == dataclasses.asdict(desc)


def test_format_suite_label_is_suite_not_test_suite() -> None:
    """format_suite must use 'suite:' label, not 'test_suite:' (D-03 byte-identical)."""
    from graph_io.queries import SuiteDescription

    desc = SuiteDescription(name="mytest", uri="test://x", kind="pytest", file_count=3)
    out = render.format_suite(desc, fmt="human")
    assert out.startswith("suite:  mytest")
    assert "test_suite:" not in out


def test_format_domain_accepts_packages_subdomains_args() -> None:
    """format_domain signature: (desc, packages, subdomains, fmt) — packages/subdomains NOT in DomainDescription."""
    from graph_io.queries import DomainDescription

    desc = DomainDescription(name="core", uri="dom://core", parent=None, description="Core domain")
    out = render.format_domain(desc, packages=["pkgA"], subdomains=[], fmt="human")
    assert "domain:        core" in out
    assert "  - pkgA" in out
    assert "  (none)" in out  # subdomains section


def test_format_domain_json_merges_packages_subdomains() -> None:
    """format_domain json merges packages and subdomains keys into asdict(desc)."""

    from graph_io.queries import DomainDescription

    desc = DomainDescription(name="core", uri="dom://core", parent=None, description="Core")
    out = render.format_domain(desc, packages=["pkgA", "pkgB"], subdomains=["sub"], fmt="json")
    parsed = json.loads(out)
    assert parsed["packages"] == ["pkgA", "pkgB"]
    assert parsed["subdomains"] == ["sub"]
    assert parsed["name"] == "core"


# ============================================================================
# Task 3: format_symbol / format_matches
# ============================================================================


def test_format_symbol_human() -> None:
    from graph_io.queries import CallRecord, SymbolDescription

    desc = SymbolDescription(
        kind="function",
        name="process",
        path="foo/a.py",
        line=42,
        package="foo",
        domain="ingest",
        exported_from="foo/__init__.py",
        callers=[CallRecord(name="run_scan", path="foo/a.py", line=1, depth=1)],
        callees=[CallRecord(name="validate", path="foo/a.py", line=80, depth=1)],
    )
    out = render.format_symbol(desc, "human")
    assert "function process" in out
    assert "path: foo/a.py:42" in out
    assert "package: foo" in out
    assert "domain: ingest" in out
    assert "exported: yes (from foo/__init__.py)" in out
    assert "callers (depth 1): run_scan" in out
    assert "callees (depth 1): validate" in out
    assert "gw graph callers process --depth 3" in out


def test_format_symbol_graceful_omissions() -> None:
    from graph_io.queries import SymbolDescription

    desc = SymbolDescription(
        kind="class",
        name="Widget",
        path="foo/a.py",
        line=5,
        package=None,
        domain=None,
        exported_from=None,
        callers=[],
        callees=[],
    )
    out = render.format_symbol(desc, "human")
    assert "class Widget" in out
    assert "exported: no" in out
    assert "callees" not in out  # omitted gracefully
    assert "domain:" not in out


def test_format_symbol_json() -> None:
    import json

    from graph_io.queries import SymbolDescription

    desc = SymbolDescription(
        kind="type",
        name="Foo",
        path="a.ts",
        line=3,
        package="p",
        domain=None,
        exported_from=None,
        callers=[],
        callees=[],
    )
    parsed = json.loads(render.format_symbol(desc, "json"))
    assert parsed["kind"] == "type"
    assert parsed["name"] == "Foo"
    assert parsed["callees"] == []


def test_format_matches_human_and_json() -> None:
    import json

    from graph_io.queries import MatchRecord

    rows = [
        MatchRecord(
            kind="function", address="foo/a.py:10", command="gw graph describe run --kind function --in-package foo"
        ),
        MatchRecord(kind="class", address="foo/a.py:20", command="gw graph describe run --kind class --in-package foo"),
    ]
    human = render.format_matches(rows, "human")
    assert "function" in human and "foo/a.py:10" in human
    assert "gw graph describe run --kind class --in-package foo" in human
    parsed = json.loads(render.format_matches(rows, "json"))
    assert [r["kind"] for r in parsed] == ["function", "class"]


def test_format_path_human_shows_imports_and_exports() -> None:
    from graph_io.queries import ExportRecord, NodeRecord, PathDescription

    desc = PathDescription(
        path="foo/a.py",
        children=[NodeRecord(kind="function", name="alpha", path="foo/a.py", line=10, attrs={})],
        imports=[NodeRecord(kind="file", name="b.py", path="foo/b.py", line=None, attrs={})],
        role_flags=None,
        exports=[ExportRecord(name="alpha", kind="function", line=10)],
    )
    out = render.format_path(desc, "human")
    assert "imports:" in out
    assert "b.py  foo/b.py" in out
    assert "exports:" in out
    assert "function  alpha  line 10" in out


def test_format_path_json_includes_exports() -> None:
    import json

    from graph_io.queries import ExportRecord, PathDescription

    desc = PathDescription(
        path="a.py",
        children=[],
        imports=[],
        role_flags=None,
        exports=[ExportRecord(name="alpha", kind="function", line=10)],
    )
    parsed = json.loads(render.format_path(desc, "json"))
    assert parsed["exports"] == [{"name": "alpha", "kind": "function", "line": 10}]
