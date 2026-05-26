"""Query layer: find, callers, callees, imports, describe_package, describe_path."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import queries, resolve, store, upsert


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "code.db"
    c = store.connect(db, create=True)
    yield c
    c.close()


def _seed_call_chain(conn: sqlite3.Connection) -> None:
    nodes = [
        GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
        GraphNode(kind="function", name="alpha", path="a.py", line=1, attrs={}),
        GraphNode(kind="function", name="beta", path="a.py", line=5, attrs={}),
        GraphNode(kind="function", name="gamma", path="a.py", line=10, attrs={}),
    ]
    edges = [
        GraphEdge(src=("function", "alpha", "a.py"), dst=("function", "beta", None), kind="calls", attrs={}),
        GraphEdge(src=("function", "beta", "a.py"), dst=("function", "gamma", None), kind="calls", attrs={}),
    ]
    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
    resolve.sweep(conn)


def test_find_by_name(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="class", name="foo", path="b.py", line=2, attrs={}),
        ],
        edges=[],
    ))
    rows = queries.find(conn, name="foo")
    assert {(r.kind, r.path) for r in rows} == {("function", "a.py"), ("class", "b.py")}


def test_find_by_name_and_kind(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="class", name="foo", path="b.py", line=2, attrs={}),
        ],
        edges=[],
    ))
    rows = queries.find(conn, name="foo", kind="function")
    assert [(r.kind, r.path) for r in rows] == [("function", "a.py")]


def test_callers_depth_bounded(conn: sqlite3.Connection) -> None:
    _seed_call_chain(conn)
    rows = queries.callers(conn, name="gamma", depth=1)
    names = {r.name for r in rows}
    assert names == {"beta"}

    rows = queries.callers(conn, name="gamma", depth=3)
    names = {r.name for r in rows}
    assert names == {"alpha", "beta"}


def test_callees_depth_bounded(conn: sqlite3.Connection) -> None:
    _seed_call_chain(conn)
    rows = queries.callees(conn, name="alpha", depth=1)
    assert {r.name for r in rows} == {"beta"}

    rows = queries.callees(conn, name="alpha", depth=3)
    assert {r.name for r in rows} == {"beta", "gamma"}


def test_imports_returns_resolved_only(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "missing", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imports(conn, path="a.py")
    assert [r.path for r in rows] == ["b.py"]


def test_describe_package(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="package", name="alpha", path="alpha", line=None, attrs={"language": "python", "version": "0.1.0"}),
            GraphNode(kind="file", name="alpha/a.py", path="alpha/a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="alpha/a.py", line=1, attrs={}),
        ],
        edges=[
            GraphEdge(src=("package", "alpha", "alpha"), dst=("file", "alpha/a.py", "alpha/a.py"), kind="contains", attrs={}),
            GraphEdge(src=("file", "alpha/a.py", "alpha/a.py"), dst=("function", "foo", "alpha/a.py"), kind="contains", attrs={}),
        ],
    ))
    desc = queries.describe_package(conn, name="alpha")
    assert desc.name == "alpha"
    assert desc.language == "python"
    assert desc.version == "0.1.0"
    assert "alpha/a.py" in desc.files
    assert desc.counts["function"] == 1


def test_describe_path(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", "a.py"), kind="contains", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    desc = queries.describe_path(conn, path="a.py")
    assert desc.path == "a.py"
    assert any(c.name == "foo" for c in desc.children)
    assert any(i.path == "b.py" for i in desc.imports)


def test_describe_package_returns_none_for_missing(conn: sqlite3.Connection) -> None:
    assert queries.describe_package(conn, name="no-such-package") is None


def test_describe_path_returns_none_for_missing(conn: sqlite3.Connection) -> None:
    assert queries.describe_path(conn, path="no/such/path.py") is None


def test_imported_by_returns_importers_with_symbols(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="file", name="c.py", path="c.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="c.py", line=1, attrs={}),
            GraphNode(kind="function", name="bar", path="c.py", line=5, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "bar", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("function", "foo", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imported_by(conn, path="c.py")
    by_path = {r.path: r for r in rows}
    assert set(by_path) == {"a.py", "b.py"}
    assert by_path["a.py"].symbols == ("bar", "foo")
    assert by_path["b.py"].symbols == ("foo",)
    assert by_path["a.py"].depth == 1


def test_imported_by_symbol_filter_narrows(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="file", name="c.py", path="c.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="c.py", line=1, attrs={}),
            GraphNode(kind="function", name="bar", path="c.py", line=5, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("function", "bar", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imported_by(conn, path="c.py", symbol="foo")
    assert [r.path for r in rows] == ["a.py"]
    assert rows[0].symbols == ("foo",)


def test_imported_by_depth_walks_transitively(conn: sqlite3.Connection) -> None:
    # a.py imports b.py; b.py imports c.py — depth=2 from c.py reaches a.py.
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="file", name="c.py", path="c.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("file", "c.py", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    direct = queries.imported_by(conn, path="c.py", depth=1)
    assert {r.path for r in direct} == {"b.py"}
    transitive = queries.imported_by(conn, path="c.py", depth=2)
    by_path = {r.path: r for r in transitive}
    assert set(by_path) == {"a.py", "b.py"}
    assert by_path["b.py"].depth == 1
    assert by_path["a.py"].depth == 2


def test_imported_by_excludes_unresolved(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "b.py", None), kind="imports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("file", "missing", None), kind="imports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.imported_by(conn, path="b.py")
    assert [r.path for r in rows] == ["a.py"]


def test_exports_returns_exported_symbols(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=10, attrs={}),
            GraphNode(kind="function", name="bar", path="a.py", line=20, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="exports", attrs={}),
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "bar", None), kind="exports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.exports(conn, path="a.py")
    by_name = {r.name: r for r in rows}
    assert set(by_name) == {"foo", "bar"}
    assert by_name["foo"].kind == "function"
    assert by_name["foo"].line == 10


def test_exported_by_returns_owning_files(conn: sqlite3.Connection) -> None:
    upsert.upsert_records(conn, GraphRecords(
        nodes=[
            GraphNode(kind="file", name="a.py", path="a.py", line=None, attrs={}),
            GraphNode(kind="file", name="b.py", path="b.py", line=None, attrs={}),
            GraphNode(kind="function", name="foo", path="a.py", line=1, attrs={}),
            GraphNode(kind="function", name="foo", path="b.py", line=1, attrs={}),
        ],
        edges=[
            GraphEdge(src=("file", "a.py", "a.py"), dst=("function", "foo", None), kind="exports", attrs={}),
            GraphEdge(src=("file", "b.py", "b.py"), dst=("function", "foo", None), kind="exports", attrs={}),
        ],
    ))
    resolve.sweep(conn)
    rows = queries.exported_by(conn, name="foo")
    assert sorted(r.path for r in rows) == ["a.py", "b.py"]
    assert all(r.name == "foo" for r in rows)


# ============================================================================
# Phase 32 Wave 0: dataclass shapes, find() allow-list, fixture audit.
# ============================================================================

import dataclasses

from graph_io.queries import (
    DomainDescription,
    EntryPointDescription,
    PackageDescription,
    PathDescription,
    RepoDescription,
    SuiteDescription,
    _VALID_KINDS,
    find,
)


def test_dataclass_field_shapes() -> None:
    """Every new dataclass has the exact declared field set and is frozen."""
    expected = {
        RepoDescription: {"name", "uri", "owner", "url", "default_branch", "package_count"},
        DomainDescription: {"name", "uri", "parent", "description"},
        EntryPointDescription: {
            "name",
            "uri",
            "kind",
            "callable",
            "implemented_by_path",
            "source",
        },
        SuiteDescription: {"name", "uri", "kind", "file_count"},
    }
    for cls, want in expected.items():
        got = {f.name for f in dataclasses.fields(cls)}
        assert got == want, f"{cls.__name__}: expected {want}, got {got}"

    pkg_fields = {f.name for f in dataclasses.fields(PackageDescription)}
    assert {"domains", "entry_points", "test_suites"}.issubset(pkg_fields)

    path_fields = {f.name for f in dataclasses.fields(PathDescription)}
    assert "role_flags" in path_fields

    # frozen check
    repo = RepoDescription(
        name="r",
        uri="u",
        owner=None,
        url=None,
        default_branch=None,
        package_count=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        repo.name = "other"  # type: ignore[misc]


def test_find_unknown_kind_raises(empty_db: sqlite3.Connection) -> None:
    """find raises ValueError when kind is not in _VALID_KINDS."""
    with pytest.raises(ValueError) as exc:
        find(empty_db, name="x", kind="InvalidKind")
    msg = str(exc.value)
    assert "InvalidKind" in msg
    # Allow-list mentioned in message
    for kind in _VALID_KINDS:
        assert kind in msg


def test_find_requires_name_or_kind(empty_db: sqlite3.Connection) -> None:
    """find raises ValueError when neither name nor kind is provided."""
    with pytest.raises(ValueError) as exc:
        find(empty_db)
    msg = str(exc.value).lower()
    assert "name" in msg or "kind" in msg


def _count(conn: sqlite3.Connection, sql: str, *params) -> int:
    return conn.execute(sql, params).fetchone()[0]


def test_seeded_db_fixture_audit(seeded_db: sqlite3.Connection) -> None:
    """D-15 checklist: sample_monorepo fixture has the expected shape.

    Skips when Phase 31's domains.yaml has not yet shipped (the fixture
    will have zero Domain nodes). Fails when domains exist but other
    checklist items are missing — those are Phase 32's responsibility
    to back-fill.
    """
    n_domains = _count(
        seeded_db, "SELECT COUNT(*) FROM nodes WHERE kind='domain'"
    )
    if n_domains == 0:
        pytest.skip(
            "Phase 31 dependency: domains.yaml not present in "
            "sample_monorepo fixture — Phase 32 tests cannot run "
            "until Phase 31 ships."
        )

    missing: list[str] = []
    if n_domains < 2:
        missing.append(f"need >= 2 Domain nodes, found {n_domains}")

    n_dcd = _count(
        seeded_db,
        "SELECT COUNT(*) FROM edges WHERE kind='domain_contains_domain'",
    )
    if n_dcd < 1:
        missing.append("need >= 1 domain_contains_domain edge (parent-child)")

    n_cross = _count(
        seeded_db,
        "SELECT COUNT(*) FROM nodes n "
        "WHERE n.kind='package' AND NOT EXISTS ("
        "  SELECT 1 FROM edges e WHERE e.src=n.id AND e.kind='belongs_to_domain'"
        ") AND EXISTS ("
        "  SELECT 1 FROM edges r WHERE r.dst=n.id AND r.kind='references'"
        ")",
    )
    if n_cross < 1:
        missing.append("need >= 1 cross-cutting Package (zero domains, referenced)")

    n_ep_callable = _count(
        seeded_db,
        "SELECT COUNT(*) FROM nodes WHERE kind='entry_point' "
        "AND json_extract(attrs_json, '$.callable') IS NOT NULL",
    )
    if n_ep_callable < 1:
        missing.append("need >= 1 EntryPoint with non-null callable")

    n_ep_wildcard = _count(
        seeded_db,
        "SELECT COUNT(*) FROM nodes WHERE kind='entry_point' "
        "AND json_extract(attrs_json, '$.is_wildcard') = 1",
    )
    if n_ep_wildcard < 1:
        missing.append(
            "need >= 1 wildcard EntryPoint (jspkg/package.json exports with '*')"
        )

    n_suite_dom = _count(
        seeded_db,
        "SELECT COUNT(*) FROM edges e "
        "JOIN nodes s ON e.src=s.id "
        "JOIN nodes d ON e.dst=d.id "
        "WHERE e.kind='tests' AND s.kind='test_suite' AND d.kind='domain'",
    )
    if n_suite_dom < 1:
        missing.append(
            "need >= 1 single-domain TestSuite (direct TestSuite->Domain edge)"
        )

    # Multi-domain TestSuite: a TestSuite whose Package targets span 2+ Domains
    row = seeded_db.execute(
        "SELECT COUNT(*) FROM ("
        "  SELECT s.id, COUNT(DISTINCT bt.dst) AS doms "
        "  FROM nodes s "
        "  JOIN edges st ON st.src=s.id AND st.kind='tests' "
        "  JOIN nodes p ON st.dst=p.id AND p.kind='package' "
        "  LEFT JOIN edges bt ON bt.src=p.id AND bt.kind='belongs_to_domain' "
        "  WHERE s.kind='test_suite' "
        "  GROUP BY s.id "
        "  HAVING doms >= 2"
        ")"
    ).fetchone()
    if (row[0] if row else 0) < 1:
        missing.append(
            "need >= 1 multi-domain TestSuite (Package edges span 2+ Domains)"
        )

    assert not missing, (
        "sample_monorepo fixture is missing items required by D-15:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


# ============================================================================
# Phase 32 Wave 1: find per-kind, describe_*, list_*, extended describe_*.
# ============================================================================

from graph_io.queries import (
    describe_domain,
    describe_entry_point,
    describe_package,
    describe_path,
    describe_repository,
    describe_test_suite,
    list_domains,
    list_entry_points,
    list_packages,
    list_repositories,
    list_scripts,
    list_test_suites,
)


def _skip_if_phase31_missing(conn: sqlite3.Connection) -> None:
    """Skip when Phase 31's domains.yaml has not yet shipped."""
    n = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='domain'"
    ).fetchone()[0]
    if n == 0:
        pytest.skip(
            "Phase 31 dependency: domains.yaml not present in "
            "sample_monorepo fixture — Phase 32 tests cannot run "
            "until Phase 31 ships."
        )


@pytest.mark.parametrize(
    "kind",
    [
        "function",
        "class",
        "method",
        "file",
        "package",
        "repository",
        "subpackage",
        "entry_point",
        "test_suite",
        "domain",
    ],
)
def test_find_per_kind(seeded_db: sqlite3.Connection, kind: str) -> None:
    if kind == "domain":
        _skip_if_phase31_missing(seeded_db)
    rows = find(seeded_db, kind=kind)
    assert isinstance(rows, list)
    if kind in {"file", "package", "repository"}:
        assert rows, f"expected non-empty result for kind={kind!r}"
    for r in rows:
        assert r.kind == kind


def test_describe_repository(seeded_db: sqlite3.Connection) -> None:
    repo = describe_repository(seeded_db)
    assert repo is not None
    assert isinstance(repo, RepoDescription)
    assert repo.name
    assert repo.package_count >= 1


def test_describe_repository_returns_none_on_empty_db(
    empty_db: sqlite3.Connection,
) -> None:
    assert describe_repository(empty_db) is None


def test_describe_domain(seeded_db: sqlite3.Connection) -> None:
    _skip_if_phase31_missing(seeded_db)
    domains = list_domains(seeded_db)
    assert domains, "expected at least one Domain in seeded_db"
    first = domains[0].name
    dom = describe_domain(seeded_db, name=first)
    assert dom is not None
    assert isinstance(dom, DomainDescription)
    assert dom.name == first


def test_describe_domain_returns_none_on_missing(
    seeded_db: sqlite3.Connection,
) -> None:
    assert describe_domain(seeded_db, name="__nonexistent__") is None


def test_describe_entry_point(seeded_db: sqlite3.Connection) -> None:
    eps = list_entry_points(seeded_db)
    if not eps:
        pytest.skip("seeded_db has no EntryPoint nodes")
    first = eps[0]
    pkg_row = seeded_db.execute(
        "SELECT p.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "WHERE e.kind='declares_entry_point' AND e.dst = ("
        "  SELECT id FROM nodes WHERE kind='entry_point' AND name = ?"
        ") LIMIT 1",
        (first.name,),
    ).fetchone()
    assert pkg_row is not None
    ep = describe_entry_point(
        seeded_db,
        package_name=pkg_row[0],
        entry_name=first.name,
    )
    assert ep is not None
    assert isinstance(ep, EntryPointDescription)
    assert ep.name == first.name
    assert ep.kind in {"executable", "library"}


def test_describe_entry_point_returns_none_on_missing(
    empty_db: sqlite3.Connection,
) -> None:
    assert (
        describe_entry_point(empty_db, package_name="x", entry_name="y") is None
    )


def test_describe_test_suite(seeded_db: sqlite3.Connection) -> None:
    suites = list_test_suites(seeded_db)
    if not suites:
        pytest.skip("seeded_db has no TestSuite nodes")
    first = suites[0]
    s = describe_test_suite(seeded_db, suite_name=first.name)
    assert s is not None
    assert isinstance(s, SuiteDescription)
    assert s.name == first.name


def test_describe_test_suite_returns_none_on_missing(
    empty_db: sqlite3.Connection,
) -> None:
    assert describe_test_suite(empty_db, suite_name="x") is None


@pytest.mark.parametrize(
    "fn, kind",
    [
        (list_repositories, "repository"),
        (list_packages, "package"),
        (list_entry_points, "entry_point"),
        (list_test_suites, "test_suite"),
        (list_domains, "domain"),
    ],
)
def test_list_returns_sorted_node_records(
    seeded_db: sqlite3.Connection, fn, kind: str
) -> None:
    if kind == "domain":
        _skip_if_phase31_missing(seeded_db)
    rows = fn(seeded_db)
    assert isinstance(rows, list)
    assert all(r.kind == kind for r in rows)
    names = [r.name for r in rows]
    assert names == sorted(names), f"{fn.__name__} not alphabetical"


def test_list_returns_empty_on_empty_db(empty_db: sqlite3.Connection) -> None:
    for fn in [
        list_repositories,
        list_packages,
        list_entry_points,
        list_test_suites,
        list_domains,
        list_scripts,
    ]:
        assert fn(empty_db) == []


def test_list_scripts(seeded_db: sqlite3.Connection) -> None:
    scripts = list_scripts(seeded_db)
    assert isinstance(scripts, list)
    for r in scripts:
        assert r.kind in {"file", "entry_point"}
        if r.kind == "file":
            assert r.attrs.get("is_executable") is True
        else:
            assert r.attrs.get("entry_kind") == "executable"


def test_describe_package_extended(seeded_db: sqlite3.Connection) -> None:
    pkgs = list_packages(seeded_db)
    assert pkgs, "expected packages in seeded_db"
    name = pkgs[0].name
    desc = describe_package(seeded_db, name=name)
    assert desc is not None
    assert isinstance(desc.domains, list)
    assert isinstance(desc.entry_points, list)
    assert isinstance(desc.test_suites, list)
    for ep in desc.entry_points:
        assert isinstance(ep, EntryPointDescription)
    for ts in desc.test_suites:
        assert isinstance(ts, SuiteDescription)


def test_describe_package_returns_none_on_missing(
    empty_db: sqlite3.Connection,
) -> None:
    assert describe_package(empty_db, name="__nonexistent__") is None


def test_describe_path_role_flags(seeded_db: sqlite3.Connection) -> None:
    row = seeded_db.execute(
        "SELECT path FROM nodes WHERE kind='file' LIMIT 1"
    ).fetchone()
    assert row is not None, "expected a File node"
    desc = describe_path(seeded_db, path=row[0])
    assert desc is not None
    assert isinstance(desc.role_flags, dict)
    assert set(desc.role_flags.keys()) == {
        "is_importable",
        "has_main",
        "is_test",
        "is_config",
        "is_generated",
        "is_type_only",
        "is_executable",
    }
    for k, v in desc.role_flags.items():
        assert isinstance(v, bool), f"{k}: {v!r} not a bool"


def test_describe_path_returns_none_on_missing_empty_db(
    empty_db: sqlite3.Connection,
) -> None:
    assert describe_path(empty_db, path="nonexistent/path.py") is None
