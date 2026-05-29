"""Tests for the public graph_io.render module (promoted from graph_io.cli._format).

RED phase: these tests will fail until render.py is created.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from graph_io import render
from graph_io.cli import _format
from graph_io.queries import ImporterRecord


@dataclass(frozen=True)
class Row:
    kind: str
    name: str
    path: str
    line: int


# ── Shim identity ──────────────────────────────────────────────────────────────

def test_format_shim_render_is_render_module_render() -> None:
    """_format.render must be the same object as render.render (shim identity, D-02)."""
    assert _format.render is render.render


# ── Public module existence ────────────────────────────────────────────────────

def test_render_module_has_all_format_functions() -> None:
    for name in ["format_package", "format_path", "format_repo", "format_domain",
                 "format_entry_point", "format_suite"]:
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
    from graph_io.queries import PackageDescription
    import dataclasses
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
    import dataclasses
    desc = DomainDescription(name="core", uri="dom://core", parent=None, description="Core")
    out = render.format_domain(desc, packages=["pkgA", "pkgB"], subdomains=["sub"], fmt="json")
    parsed = json.loads(out)
    assert parsed["packages"] == ["pkgA", "pkgB"]
    assert parsed["subdomains"] == ["sub"]
    assert parsed["name"] == "core"
