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


def test_format_package_human_spine() -> None:
    from graph_io.queries import PackageDescription

    desc = PackageDescription(
        name="mypkg",
        language="python",
        version="1.0",
        files=["a.py", "b.py"],
        counts={"function": 2},
        domains=["core"],
        entry_points=[],
        test_suites=[],
        internal_dependencies=["other"],
        internal_dependents=[],
    )
    out = render.format_package(desc, fmt="human")
    assert out.startswith("package mypkg\n  uri: pkg:mypkg")
    assert "  language: python" in out
    assert "  files:    2" in out
    assert "  counts:   2 functions" in out
    assert "  internal deps:" in out and "other" in out
    assert "  domains:" in out and "core" in out
    # internal dependents empty → omitted as a relationship line
    assert "internal dependents:" not in out
    assert "→ gw graph what-tests mypkg" in out
    assert "→ gw graph list-entry-points mypkg" in out


def test_format_package_json_spine() -> None:
    from graph_io.queries import PackageDescription

    desc = PackageDescription(
        name="mypkg",
        language="python",
        version="1.0",
        files=["a.py"],
        counts={"function": 1},
        domains=["core"],
        entry_points=[],
        test_suites=[],
        internal_dependencies=["other"],
        internal_dependents=[],
    )
    parsed = json.loads(render.format_package(desc, fmt="json"))
    assert parsed["kind"] == "package"
    assert parsed["name"] == "mypkg"
    assert parsed["uri"] == "pkg:mypkg"
    assert parsed["attributes"]["files"] == 1
    assert parsed["attributes"]["counts"] == {"function": 1}
    assert parsed["relationships"]["internal_dependencies"] == ["other"]
    assert parsed["relationships"]["domains"] == ["core"]


def test_format_app_human_and_json() -> None:
    from graph_io.queries import AppDescription

    desc = AppDescription(
        name="my-cli",
        language="python",
        version="0.1",
        app_kind="cli",
        app_signals=["console_scripts"],
        files=["cli.py"],
        counts={"function": 3},
        domains=[],
        entry_points=[],
        test_suites=[],
    )
    human = render.format_app(desc, fmt="human")
    assert human.startswith("app my-cli\n  uri: app:my-cli")
    assert "  app_kind: cli" in human
    assert "  signals:  console_scripts" in human
    parsed = json.loads(render.format_app(desc, fmt="json"))
    assert parsed["uri"] == "app:my-cli"
    assert parsed["attributes"]["app_kind"] == "cli"
    assert parsed["attributes"]["signals"] == ["console_scripts"]


def test_format_suite_spine() -> None:
    from graph_io.queries import SuiteDescription

    desc = SuiteDescription(name="mytest", uri="test://x", kind="pytest", file_count=3)
    out = render.format_suite(desc, fmt="human")
    assert out.startswith("test_suite mytest\n  uri: test://x")
    assert "  kind:  pytest" in out
    assert "  files: 3" in out


def test_format_repo_spine() -> None:
    from graph_io.queries import RepoDescription

    desc = RepoDescription(
        name="agent-research",
        uri="repo://agent-research",
        owner="pat",
        url="git@x",
        default_branch="develop",
        package_count=11,
    )
    human = render.format_repo(desc, fmt="human")
    assert human.startswith("repository agent-research\n  uri: repo://agent-research")
    assert "  owner:" in human and "pat" in human
    assert "package_count:" in human and "11" in human
    assert "→ gw graph list --kind package" in human
    assert "→ gw graph list --kind app" in human
    parsed = json.loads(render.format_repo(desc, fmt="json"))
    assert parsed["uri"] == "repo://agent-research"
    assert parsed["attributes"]["package_count"] == 11


def test_format_dependency_spine() -> None:
    from graph_io.queries import DependencyDescription

    desc = DependencyDescription(
        ecosystem="pypi", name="boto3", uri="dependency:pypi/boto3", versions_in_use=["1.38"], used_by=["demo"]
    )
    human = render.format_dependency(desc, fmt="human")
    assert human.startswith("dependency boto3\n  uri: dependency:pypi/boto3")
    assert "  ecosystem:       pypi" in human
    assert "  versions_in_use: 1.38" in human
    assert "  used_by:" in human and "demo" in human
    parsed = json.loads(render.format_dependency(desc, fmt="json"))
    assert parsed["attributes"]["versions_in_use"] == ["1.38"]
    assert parsed["relationships"]["used_by"] == ["demo"]


def test_format_builtin_spine() -> None:
    from graph_io.queries import BuiltinDescription

    desc = BuiltinDescription(language="python", module_name="pathlib", uri="builtin:python/pathlib", used_by=["demo"])
    human = render.format_builtin(desc, fmt="human")
    assert human.startswith("builtin pathlib\n  uri: builtin:python/pathlib")
    assert "  language:    python" in human
    assert "  module_name: pathlib" in human
    assert "  used_by:" in human
    parsed = json.loads(render.format_builtin(desc, fmt="json"))
    assert parsed["name"] == "pathlib"
    assert parsed["relationships"]["used_by"] == ["demo"]


def test_format_agent_plugin_spine() -> None:
    from graph_io.queries import AgentPluginDescription

    desc = AgentPluginDescription(
        name="graph-wiki",
        uri="agent_plugin:graph-wiki",
        ecosystem="claude-code",
        version="0.1.1",
        description="x",
        commands=[{"id": "a"}],
        agents=[],
        skills=[{"id": "s"}],
        scripts=[],
        hooks=[],
        mcp_servers=[],
    )
    human = render.format_agent_plugin(desc, fmt="human")
    assert human.startswith("agent_plugin graph-wiki\n  uri: agent_plugin:graph-wiki")
    assert "  ecosystem:   claude-code" in human
    assert "  commands:    1" in human
    assert "  skills:      1" in human
    assert "→ gw graph list --kind agent_plugin" in human
    parsed = json.loads(render.format_agent_plugin(desc, fmt="json"))
    assert parsed["attributes"]["commands"] == 1
    assert parsed["attributes"]["mcp_servers"] == 0


def test_format_domain_spine() -> None:
    from graph_io.queries import DomainDescription

    desc = DomainDescription(name="core", uri="dom://core", parent=None, description="Core domain")
    human = render.format_domain(desc, packages=["pkgA"], subdomains=[], fmt="human")
    assert human.startswith("domain core\n  uri: dom://core")
    assert "  parent:      (none)" in human
    assert "  description: Core domain" in human
    assert "  packages: pkgA" in human
    assert "subdomains:" not in human  # empty relationship omitted
    parsed = json.loads(render.format_domain(desc, packages=["pkgA", "pkgB"], subdomains=["sub"], fmt="json"))
    assert parsed["uri"] == "dom://core"
    assert parsed["relationships"]["packages"] == ["pkgA", "pkgB"]
    assert parsed["relationships"]["subdomains"] == ["sub"]


def test_format_entry_point_spine() -> None:
    from graph_io.queries import EntryPointDescription

    desc = EntryPointDescription(
        name="gw",
        uri="ep://gw",
        kind="console_script",
        callable="mod:main",
        implemented_by_path="src/mod.py",
        source="pyproject",
    )
    human = render.format_entry_point(desc, fmt="human")
    assert human.startswith("entry_point gw\n  uri: ep://gw")
    assert "  callable: mod:main" in human
    assert "  path:     src/mod.py" in human
    assert "→ gw graph describe src/mod.py" in human


def test_format_entry_point_no_nav_when_no_path() -> None:
    from graph_io.queries import EntryPointDescription

    desc = EntryPointDescription(
        name="gw", uri="ep://gw", kind="console_script", callable=None, implemented_by_path=None, source="pyproject"
    )
    human = render.format_entry_point(desc, fmt="human")
    assert "  callable: (none)" in human
    assert "→" not in human


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


def _symbol_desc(token_count):
    from graph_io.queries import SymbolDescription

    return SymbolDescription(
        kind="function",
        name="foo",
        path="a.py",
        line=1,
        package=None,
        domain=None,
        exported_from=None,
        token_count=token_count,
    )


def test_format_symbol_human_includes_tokens() -> None:
    out = render.format_symbol(_symbol_desc(42), fmt="human")
    assert "tokens: 42" in out


def test_format_symbol_human_omits_tokens_when_none() -> None:
    out = render.format_symbol(_symbol_desc(None), fmt="human")
    assert "tokens" not in out


def test_format_symbol_json_includes_token_count() -> None:
    out = render.format_symbol(_symbol_desc(42), fmt="json")
    assert json.loads(out)["token_count"] == 42


def test_format_path_human_includes_file_and_child_tokens() -> None:
    from graph_io.queries import NodeRecord, PathDescription

    desc = PathDescription(
        path="a.py",
        children=[NodeRecord(kind="function", name="foo", path="a.py", line=1, attrs={"token_count": 7})],
        imports=[],
        role_flags=None,
        token_count=20,
    )
    out = render.format_path(desc, fmt="human")
    assert "tokens: 20" in out
    assert "(7 tokens)" in out


def test_format_path_json_includes_token_count() -> None:
    from graph_io.queries import PathDescription

    desc = PathDescription(path="a.py", children=[], imports=[], role_flags=None, token_count=20)
    out = render.format_path(desc, fmt="json")
    assert json.loads(out)["token_count"] == 20


# ── Task 1: describe_block spine builder ────────────────────────────────────


def test_pluralize_rules() -> None:
    assert render._pluralize("function", 2) == "functions"
    assert render._pluralize("class", 4) == "classes"
    assert render._pluralize("method", 7) == "methods"
    assert render._pluralize("type", 3) == "types"
    assert render._pluralize("function", 1) == "function"  # singular at n==1


def test_counts_human_breakdown() -> None:
    out = render._counts_human({"function": 12, "class": 4, "method": 7})
    assert out == "12 functions · 4 classes · 7 methods"
    assert render._counts_human({}) == "(none)"


def test_describe_block_human_full() -> None:
    out = render.describe_block(
        kind="package",
        name="graph-io",
        identity_label="uri",
        identity_value="pkg:graph-io",
        attributes=[
            render.Attr.scalar("language", "language", "python"),
            render.Attr.scalar("version", "version", "1.8.0"),
            render.Attr.scalar("files", "files", 23),
            render.Attr("counts", "counts", "12 functions · 4 classes", {"function": 12, "class": 4}),
        ],
        relationships=[
            render.Rel("internal deps", "internal_dependencies", ["workspace-io", "source-parser"]),
            render.Rel("internal dependents", "internal_dependents", ["graph-wiki-core"]),
        ],
        nav=["gw graph what-tests graph-io", "gw graph list-entry-points graph-io"],
        fmt="human",
    )
    expected = (
        "package graph-io\n"
        "  uri: pkg:graph-io\n"
        "\n"
        "attributes\n"
        "  language: python\n"
        "  version:  1.8.0\n"
        "  files:    23\n"
        "  counts:   12 functions · 4 classes\n"
        "\n"
        "relationships\n"
        "  internal deps:       workspace-io, source-parser\n"
        "  internal dependents: graph-wiki-core\n"
        "\n"
        "→ gw graph what-tests graph-io\n"
        "→ gw graph list-entry-points graph-io"
    )
    assert out == expected


def test_describe_block_human_omits_empty_sections() -> None:
    out = render.describe_block(
        kind="test_suite",
        name="graph-io-tests",
        identity_label="uri",
        identity_value="test://graph-io-tests",
        attributes=[render.Attr.scalar("kind", "kind", "pytest")],
        relationships=[],
        nav=[],
        fmt="human",
    )
    assert out == ("test_suite graph-io-tests\n  uri: test://graph-io-tests\n\nattributes\n  kind: pytest")
    assert "relationships" not in out
    assert "→" not in out


def test_describe_block_json_mirrors_spine() -> None:
    out = render.describe_block(
        kind="package",
        name="graph-io",
        identity_label="uri",
        identity_value="pkg:graph-io",
        attributes=[
            render.Attr.scalar("files", "files", 23),
            render.Attr("counts", "counts", "ignored-in-json", {"function": 12}),
        ],
        relationships=[render.Rel("domains", "domains", ["graph"])],
        nav=["gw graph what-tests graph-io"],
        fmt="json",
    )
    assert json.loads(out) == {
        "kind": "package",
        "name": "graph-io",
        "uri": "pkg:graph-io",
        "attributes": {"files": 23, "counts": {"function": 12}},
        "relationships": {"domains": ["graph"]},
        "nav": ["gw graph what-tests graph-io"],
    }


def test_describe_block_json_empty_sections_present() -> None:
    out = render.describe_block(
        kind="repository",
        name="r",
        identity_label="uri",
        identity_value="repo://r",
        attributes=[],
        relationships=[],
        nav=[],
        fmt="json",
    )
    parsed = json.loads(out)
    assert parsed["attributes"] == {} and parsed["relationships"] == {} and parsed["nav"] == []


def test_describe_block_scalar_none_renders_none() -> None:
    out = render.describe_block(
        kind="domain",
        name="d",
        identity_label="uri",
        identity_value="dom://d",
        attributes=[render.Attr.scalar("parent", "parent", None)],
        relationships=[],
        nav=[],
        fmt="human",
    )
    assert "  parent: (none)" in out


def test_describe_block_invalid_fmt() -> None:
    with pytest.raises(ValueError):
        render.describe_block(
            kind="x",
            name="y",
            identity_label="uri",
            identity_value="z",
            attributes=[],
            relationships=[],
            nav=[],
            fmt="xml",
        )
