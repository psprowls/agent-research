"""Read-only queries over the code graph. All callers open a read-only conn."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

_VALID_KINDS = frozenset(
    {
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
        # Phase 43 (v1.8): admitted entity kinds for the wiki entity writer.
        "dependency",
        "plugin",
        # Phase 49 D-14: stdlib module imports (Python via sys.stdlib_module_names; Node via require('module').builtinModules)
        "builtin",
        # Phase 50 D-12: app-classified packages (scanner-derived kind)
        "app",
    }
)

# Phase 50 D-04: App framework kinds derived by classification.classify().
# Write-time gate — keep in sync with _FRAMEWORK_PRECEDENCE in
# graph_io/classification.py.
_VALID_APP_KINDS = frozenset({"cli", "expo", "nextjs", "spa"})

_RESOLVED_FILTER = (
    "(e.attrs_json IS NULL OR json_extract(e.attrs_json, '$.resolution') != 'unresolved')"
)

# Recursive CTE: yields the id of the named Domain and every descendant
# reachable via `domain_contains_domain` edges. The first ?-parameter is the
# domain name. `UNION` (not `UNION ALL`) provides defence-in-depth against a
# `domain_contains_domain` cycle — Phase 31 D-15 guarantees acyclicity, but
# explicit dedup costs nothing at the bounded sizes we expect.
_DOMAIN_DESCENDANTS_CTE = """
WITH RECURSIVE descendants(id) AS (
    SELECT id FROM nodes WHERE name = ? AND kind = 'domain'
    UNION
    SELECT e.dst FROM edges e
    JOIN descendants d ON e.src = d.id
    WHERE e.kind = 'domain_contains_domain'
)
"""


@dataclass(frozen=True)
class NodeRecord:
    kind: str
    name: str
    path: str | None
    line: int | None
    attrs: dict


@dataclass(frozen=True)
class CallRecord:
    name: str
    path: str | None
    line: int | None
    depth: int


@dataclass(frozen=True)
class ImportRecord:
    name: str
    path: str | None


@dataclass(frozen=True)
class RepoDescription:
    name: str
    uri: str
    owner: str | None
    url: str | None
    default_branch: str | None
    package_count: int


@dataclass(frozen=True)
class DomainDescription:
    name: str
    uri: str
    parent: str | None
    description: str | None


@dataclass(frozen=True)
class EntryPointDescription:
    name: str
    uri: str
    kind: str
    callable: str | None
    implemented_by_path: str | None
    source: str


@dataclass(frozen=True)
class SuiteDescription:
    name: str
    uri: str
    kind: str
    file_count: int


@dataclass(frozen=True)
class PackageDescription:
    name: str
    language: str
    version: str
    files: list[str]
    counts: dict[str, int]
    domains: list[str] = field(default_factory=list)
    entry_points: list[EntryPointDescription] = field(default_factory=list)
    test_suites: list[SuiteDescription] = field(default_factory=list)


@dataclass(frozen=True)
class AppDescription:
    """Description of an `app` node (Phase 50 APP-04 / APP-05).

    Mirrors `PackageDescription` field-for-field with two additions:
    `app_kind` (one of `_VALID_APP_KINDS`) and `app_signals` (the sorted
    list of signals that triggered classification).
    """
    name: str
    language: str
    version: str
    app_kind: str
    app_signals: list[str]
    files: list[str]
    counts: dict[str, int]
    domains: list[str] = field(default_factory=list)
    entry_points: list[EntryPointDescription] = field(default_factory=list)
    test_suites: list[SuiteDescription] = field(default_factory=list)


@dataclass(frozen=True)
class PathDescription:
    path: str
    children: list[NodeRecord]
    imports: list[NodeRecord]
    role_flags: dict[str, bool] | None = None


@dataclass(frozen=True)
class DependencyDescription:
    """Description of a `dependency` node (Phase 43 D-02 + D-05)."""
    ecosystem: str
    name: str
    uri: str
    versions_in_use: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BuiltinDescription:
    """Description of a `builtin` node (Phase 49 D-13 / D-15 / BUILTIN-04 / BUILTIN-06)."""
    language: str
    module_name: str
    uri: str
    used_by: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PluginDescription:
    """Description of a `plugin` node (Phase 43 D-03 + D-05)."""
    name: str
    uri: str
    ecosystem: str


def _row_to_node(row) -> NodeRecord:
    """Project a SQL row into a NodeRecord.

    Accepts both 5-column shape `(kind, name, path, line, attrs_json)` and
    6-column shape with `uri` appended. When `uri` is present, it is folded
    back into `attrs` under the `"uri"` key so callers can read it uniformly
    from `node.attrs["uri"]` (the upsert layer pops `uri` out of attrs and
    into a dedicated column at write time — projecting it back keeps the
    read surface symmetric for downstream code, e.g. wiki_io.entity_writer).
    """
    if len(row) == 6:
        kind, name, path, line, attrs_json, uri = row
    else:
        kind, name, path, line, attrs_json = row
        uri = None
    attrs = json.loads(attrs_json) if attrs_json else {}
    if uri:
        attrs["uri"] = uri
    return NodeRecord(kind=kind, name=name, path=path, line=line, attrs=attrs)


def _load_entry_point_description(row) -> EntryPointDescription:
    """Project a raw EntryPoint SQL row into a Description.

    Expected row shape: (name, uri, attrs_json, impl_path).
    attrs_json is parsed; `kind`, `callable`, `source` are read from it.
    `implemented_by_path` is the joined File.path (may be None).
    """
    name, uri, attrs_json, impl_path = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    # Phase 30 emits the kind as `entry_kind` in attrs_json; fall back to
    # `kind` for forward compatibility / projector-level unit tests.
    kind = attrs.get("entry_kind") or attrs.get("kind", "")
    return EntryPointDescription(
        name=name,
        uri=uri or "",
        kind=kind,
        callable=attrs.get("callable"),
        implemented_by_path=impl_path,
        source=attrs.get("source", ""),
    )


def _load_suite_description(row) -> SuiteDescription:
    """Project a TestSuite row into a SuiteDescription.

    Expected row shape: (name, uri, attrs_json, file_count).
    """
    name, uri, attrs_json, file_count = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    return SuiteDescription(
        name=name,
        uri=uri or "",
        kind=attrs.get("suite_kind", ""),
        file_count=int(file_count or 0),
    )


def find(
    conn: sqlite3.Connection,
    *,
    name: str | None = None,
    kind: str | None = None,
    in_package: str | None = None,
) -> list[NodeRecord]:
    """Find nodes by name, kind, and/or containing package.

    Filters AND-combine: passing multiple filters narrows results to nodes
    matching all of them. `in_package` matches the short package name
    (case-insensitive, exact) — i.e. the `name` column of the containing
    `package` node — and selects every node whose `path` is contained by
    that package via a `contains`-edge from package → file.

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.

    Raises:
        ValueError: when `kind` is provided but is not in `_VALID_KINDS`,
            or when all of `name`, `kind`, and `in_package` are None.
    """
    if kind is not None and kind not in _VALID_KINDS:
        raise ValueError(
            f"unknown kind {kind!r}; valid: {sorted(_VALID_KINDS)}"
        )
    if name is None and kind is None and in_package is None:
        raise ValueError(
            "find requires at least one of name, kind, or in_package"
        )

    where_parts: list[str] = []
    params: list = []
    if name is not None:
        where_parts.append("n.name = ?")
        params.append(name)
    if kind is not None:
        where_parts.append("n.kind = ?")
        params.append(kind)
    if in_package is not None:
        where_parts.append(
            "n.path IN ("
            "SELECT f.path FROM nodes p "
            "JOIN edges ce ON ce.src = p.id AND ce.kind='contains' "
            "JOIN nodes f ON ce.dst = f.id AND f.kind='file' "
            "WHERE p.kind='package' AND LOWER(p.name) = LOWER(?)"
            ")"
        )
        params.append(in_package)

    sql = (
        "SELECT kind, name, path, line, attrs_json FROM nodes n WHERE "
        + " AND ".join(where_parts)
    )
    # Preserve historical ORDER BY for kind-only queries — existing callers
    # (e.g. test_find_per_kind) rely on alphabetical ordering.
    if name is None and in_package is None and kind is not None:
        sql += " ORDER BY name"

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_node(r) for r in rows]


def callers(conn: sqlite3.Connection, *, name: str, depth: int = 3) -> list[CallRecord]:
    rows = conn.execute(
        f"""
        WITH RECURSIVE c(id, depth) AS (
            SELECT e.src, 1 FROM edges e
            JOIN nodes target ON e.dst = target.id
            WHERE e.kind='calls' AND target.name = ? AND target.path IS NOT NULL
              AND {_RESOLVED_FILTER}
            UNION
            SELECT e.src, c.depth + 1 FROM edges e
            JOIN c ON e.dst = c.id
            WHERE e.kind='calls' AND c.depth < ? AND {_RESOLVED_FILTER}
        )
        SELECT n.name, n.path, n.line, MIN(c.depth)
        FROM c JOIN nodes n ON c.id = n.id
        WHERE n.path IS NOT NULL
        GROUP BY n.id
        ORDER BY MIN(c.depth), n.name
        """,
        (name, depth),
    ).fetchall()
    return [CallRecord(name=r[0], path=r[1], line=r[2], depth=r[3]) for r in rows]


def callees(conn: sqlite3.Connection, *, name: str, depth: int = 3) -> list[CallRecord]:
    rows = conn.execute(
        f"""
        WITH RECURSIVE c(id, depth) AS (
            SELECT e.dst, 1 FROM edges e
            JOIN nodes src ON e.src = src.id
            WHERE e.kind='calls' AND src.name = ? AND src.path IS NOT NULL
              AND {_RESOLVED_FILTER}
            UNION
            SELECT e.dst, c.depth + 1 FROM edges e
            JOIN c ON e.src = c.id
            WHERE e.kind='calls' AND c.depth < ? AND {_RESOLVED_FILTER}
        )
        SELECT n.name, n.path, n.line, MIN(c.depth)
        FROM c JOIN nodes n ON c.id = n.id
        WHERE n.path IS NOT NULL
        GROUP BY n.id
        ORDER BY MIN(c.depth), n.name
        """,
        (name, depth),
    ).fetchall()
    return [CallRecord(name=r[0], path=r[1], line=r[2], depth=r[3]) for r in rows]


def imports(conn: sqlite3.Connection, *, path: str) -> list[ImportRecord]:
    rows = conn.execute(
        f"""
        SELECT n.name, n.path FROM edges e
        JOIN nodes src ON e.src = src.id
        JOIN nodes n ON e.dst = n.id
        WHERE src.path = ? AND e.kind='imports' AND n.path IS NOT NULL
          AND {_RESOLVED_FILTER}
        """,
        (path,),
    ).fetchall()
    return [ImportRecord(name=r[0], path=r[1]) for r in rows]


def describe_package(conn: sqlite3.Connection, *, name: str) -> PackageDescription | None:
    pkg = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='package' AND name = ?",
        (name,),
    ).fetchone()
    if not pkg:
        return None
    attrs = json.loads(pkg[0]) if pkg[0] else {}
    files = conn.execute(
        "SELECT n.path FROM edges e "
        "JOIN nodes p ON e.src = p.id JOIN nodes n ON e.dst = n.id "
        "WHERE p.kind='package' AND p.name = ? AND e.kind='contains' AND n.kind='file' "
        "ORDER BY n.path",
        (name,),
    ).fetchall()
    file_paths = [row[0] for row in files]
    counts: dict[str, int] = {}
    if file_paths:
        placeholders = ",".join("?" for _ in file_paths)
        rows = conn.execute(
            f"SELECT kind, COUNT(*) FROM nodes WHERE path IN ({placeholders}) "
            "AND kind != 'file' GROUP BY kind",
            file_paths,
        ).fetchall()
        counts = {kind: count for kind, count in rows}

    # Domains the package belongs to (D-01)
    domain_rows = conn.execute(
        "SELECT d.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "JOIN nodes d ON e.dst = d.id "
        "WHERE e.kind='belongs_to_domain' "
        "AND p.kind='package' AND p.name = ? "
        "ORDER BY d.name",
        (name,),
    ).fetchall()
    domain_names = [r[0] for r in domain_rows]

    # EntryPoints declared by the package
    ep_rows = conn.execute(
        "SELECT ep.name, ep.uri, ep.attrs_json, f.path "
        "FROM nodes pkg "
        "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
        "JOIN nodes ep ON ep.id = de.dst AND ep.kind='entry_point' "
        "LEFT JOIN edges ib ON ib.src = ep.id AND ib.kind='implemented_by' "
        "LEFT JOIN nodes f ON f.id = ib.dst AND f.kind='file' "
        "WHERE pkg.kind='package' AND pkg.name = ? "
        "ORDER BY ep.name",
        (name,),
    ).fetchall()
    entry_points = [_load_entry_point_description(r) for r in ep_rows]

    # TestSuites covering the package
    suite_rows = conn.execute(
        "SELECT ts.name, ts.uri, ts.attrs_json, "
        "(SELECT COUNT(*) FROM edges pc "
        " WHERE pc.src = ts.id AND pc.kind='physically_contains') AS fc "
        "FROM edges t "
        "JOIN nodes ts ON t.src = ts.id "
        "JOIN nodes p ON t.dst = p.id "
        "WHERE t.kind='tests' AND ts.kind='test_suite' "
        "AND p.kind='package' AND p.name = ? "
        "ORDER BY ts.name",
        (name,),
    ).fetchall()
    test_suites = [_load_suite_description(r) for r in suite_rows]

    return PackageDescription(
        name=name,
        language=attrs.get("language", ""),
        version=attrs.get("version", ""),
        files=file_paths,
        counts=counts,
        domains=domain_names,
        entry_points=entry_points,
        test_suites=test_suites,
    )


def describe_app(conn: sqlite3.Connection, *, name: str) -> AppDescription | None:
    """Return the named App's description, or None.

    Phase 50 D-10 / APP-04 / APP-05: mirrors `describe_package` with
    `kind='app'` substituted in node-side filters. Consumer-side filters
    that mirror `describe_package`'s `used_by` JOINs broaden to
    `p.kind IN ('package', 'app')` (RESEARCH Pitfall 7) so App consumers
    of a dependency remain discoverable. `conn` must be opened read-only.
    """
    pkg = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='app' AND name = ?",
        (name,),
    ).fetchone()
    if not pkg:
        return None
    attrs = json.loads(pkg[0]) if pkg[0] else {}
    files = conn.execute(
        "SELECT n.path FROM edges e "
        "JOIN nodes p ON e.src = p.id JOIN nodes n ON e.dst = n.id "
        "WHERE p.kind='app' AND p.name = ? AND e.kind='contains' AND n.kind='file' "
        "ORDER BY n.path",
        (name,),
    ).fetchall()
    file_paths = [row[0] for row in files]
    counts: dict[str, int] = {}
    if file_paths:
        placeholders = ",".join("?" for _ in file_paths)
        rows = conn.execute(
            f"SELECT kind, COUNT(*) FROM nodes WHERE path IN ({placeholders}) "
            "AND kind != 'file' GROUP BY kind",
            file_paths,
        ).fetchall()
        counts = {kind: count for kind, count in rows}

    # Domain memberships — App nodes belong to domains the same way packages do.
    domain_rows = conn.execute(
        "SELECT d.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "JOIN nodes d ON e.dst = d.id "
        "WHERE e.kind='belongs_to_domain' "
        "AND p.kind='app' AND p.name = ? "
        "ORDER BY d.name",
        (name,),
    ).fetchall()
    domain_names = [r[0] for r in domain_rows]

    # EntryPoints declared by the App.
    ep_rows = conn.execute(
        "SELECT ep.name, ep.uri, ep.attrs_json, f.path "
        "FROM nodes pkg "
        "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
        "JOIN nodes ep ON ep.id = de.dst AND ep.kind='entry_point' "
        "LEFT JOIN edges ib ON ib.src = ep.id AND ib.kind='implemented_by' "
        "LEFT JOIN nodes f ON f.id = ib.dst AND f.kind='file' "
        # Pitfall 7: broaden the consumer-side filter so App nodes that
        # are themselves consumers (via used_by-style joins) remain
        # discoverable from the App's declares_entry_point graph.
        "WHERE pkg.kind IN ('package', 'app') AND pkg.name = ? "
        "ORDER BY ep.name",
        (name,),
    ).fetchall()
    entry_points = [_load_entry_point_description(r) for r in ep_rows]

    # TestSuites covering the App.
    suite_rows = conn.execute(
        "SELECT ts.name, ts.uri, ts.attrs_json, "
        "(SELECT COUNT(*) FROM edges pc "
        " WHERE pc.src = ts.id AND pc.kind='physically_contains') AS fc "
        "FROM edges t "
        "JOIN nodes ts ON t.src = ts.id "
        "JOIN nodes p ON t.dst = p.id "
        "WHERE t.kind='tests' AND ts.kind='test_suite' "
        "AND p.kind='app' AND p.name = ? "
        "ORDER BY ts.name",
        (name,),
    ).fetchall()
    test_suites = [_load_suite_description(r) for r in suite_rows]

    return AppDescription(
        name=name,
        language=attrs.get("language", ""),
        version=attrs.get("version", ""),
        app_kind=attrs.get("app_kind", ""),
        app_signals=list(attrs.get("app_signals") or []),
        files=file_paths,
        counts=counts,
        domains=domain_names,
        entry_points=entry_points,
        test_suites=test_suites,
    )


def describe_path(conn: sqlite3.Connection, *, path: str) -> PathDescription | None:
    file_row = conn.execute(
        "SELECT kind, name, path, line, attrs_json FROM nodes WHERE kind='file' AND path = ?",
        (path,),
    ).fetchone()
    if not file_row:
        return None
    children_rows = conn.execute(
        f"""
        SELECT n.kind, n.name, n.path, n.line, n.attrs_json FROM edges e
        JOIN nodes src ON e.src = src.id
        JOIN nodes n ON e.dst = n.id
        WHERE src.kind='file' AND src.path = ? AND e.kind='contains'
          AND {_RESOLVED_FILTER}
        ORDER BY n.line
        """,
        (path,),
    ).fetchall()
    import_rows = conn.execute(
        f"""
        SELECT n.kind, n.name, n.path, n.line, n.attrs_json FROM edges e
        JOIN nodes src ON e.src = src.id
        JOIN nodes n ON e.dst = n.id
        WHERE src.kind='file' AND src.path = ? AND e.kind='imports'
          AND n.path IS NOT NULL AND {_RESOLVED_FILTER}
        ORDER BY n.path
        """,
        (path,),
    ).fetchall()
    # Project the 7 File role flags into a dict (D-05)
    file_attrs = json.loads(file_row[4]) if file_row[4] else {}
    role_flags: dict[str, bool] | None = {
        "is_importable": bool(file_attrs.get("is_importable", False)),
        "has_main": bool(file_attrs.get("has_main", False)),
        "is_test": bool(file_attrs.get("is_test", False)),
        "is_config": bool(file_attrs.get("is_config", False)),
        "is_generated": bool(file_attrs.get("is_generated", False)),
        "is_type_only": bool(file_attrs.get("is_type_only", False)),
        "is_executable": bool(file_attrs.get("is_executable", False)),
    }
    return PathDescription(
        path=path,
        children=[_row_to_node(r) for r in children_rows],
        imports=[_row_to_node(r) for r in import_rows],
        role_flags=role_flags,
    )


def describe_repository(conn: sqlite3.Connection) -> RepoDescription | None:
    """Return the single Repository node's description, or None if absent.

    Phase 29 D-01 guarantees exactly one Repository per DB. `conn` must
    be a `sqlite3.Connection` opened with `mode=ro`.
    """
    row = conn.execute(
        "SELECT name, uri, attrs_json FROM nodes "
        "WHERE kind='repository' LIMIT 1"
    ).fetchone()
    if not row:
        return None
    name, uri, attrs_json = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    pkg_count = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE kind='package'"
    ).fetchone()[0]
    return RepoDescription(
        name=name,
        uri=uri or "",
        owner=attrs.get("owner"),
        url=attrs.get("url"),
        default_branch=attrs.get("default_branch"),
        package_count=int(pkg_count or 0),
    )


def describe_domain(
    conn: sqlite3.Connection, *, name: str
) -> DomainDescription | None:
    """Return the named Domain's description, or None if not found.

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.
    """
    row = conn.execute(
        "SELECT id, name, uri, attrs_json FROM nodes "
        "WHERE kind='domain' AND name = ?",
        (name,),
    ).fetchone()
    if not row:
        return None
    dom_id, dom_name, uri, attrs_json = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    parent_row = conn.execute(
        "SELECT p.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "WHERE e.kind='domain_contains_domain' AND e.dst = ? "
        "LIMIT 1",
        (dom_id,),
    ).fetchone()
    return DomainDescription(
        name=dom_name,
        uri=uri or "",
        parent=parent_row[0] if parent_row else None,
        description=attrs.get("description"),
    )


def describe_entry_point(
    conn: sqlite3.Connection,
    *,
    package_name: str,
    entry_name: str,
) -> EntryPointDescription | None:
    """Return the named EntryPoint declared by the package, or None.

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.
    """
    row = conn.execute(
        "SELECT ep.name, ep.uri, ep.attrs_json, f.path "
        "FROM nodes pkg "
        "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
        "JOIN nodes ep ON ep.id = de.dst AND ep.kind='entry_point' "
        "LEFT JOIN edges ib ON ib.src = ep.id AND ib.kind='implemented_by' "
        "LEFT JOIN nodes f ON f.id = ib.dst AND f.kind='file' "
        # Phase 50 D-04: apps declare entry points the same way packages do.
        "WHERE pkg.kind IN ('package', 'app') AND pkg.name = ? AND ep.name = ?",
        (package_name, entry_name),
    ).fetchone()
    if not row:
        return None
    return _load_entry_point_description(row)


def describe_test_suite(
    conn: sqlite3.Connection, *, suite_name: str
) -> SuiteDescription | None:
    """Return the named TestSuite description, or None.

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.
    """
    row = conn.execute(
        "SELECT id, name, uri, attrs_json FROM nodes "
        "WHERE kind='test_suite' AND name = ?",
        (suite_name,),
    ).fetchone()
    if not row:
        return None
    suite_id, name, uri, attrs_json = row
    fc = conn.execute(
        "SELECT COUNT(*) FROM edges WHERE src = ? AND kind='physically_contains'",
        (suite_id,),
    ).fetchone()[0]
    return _load_suite_description((name, uri, attrs_json, fc))


def describe_dependency(
    conn: sqlite3.Connection, *, ecosystem: str, name: str
) -> DependencyDescription | None:
    """Return the description of a dependency node identified by (ecosystem, name).

    Reads `versions_in_use` from the node's attrs, and populates `used_by`
    from inbound `used_by` edges originating from `package` nodes (sorted
    alphabetically by consumer package name). `conn` must be opened
    read-only.
    """
    row = conn.execute(
        "SELECT id, name, attrs_json, uri FROM nodes "
        "WHERE kind='dependency' AND name = ? "
        "AND json_extract(attrs_json, '$.ecosystem') = ?",
        (name, ecosystem),
    ).fetchone()
    if not row:
        return None
    dep_id, dep_name, attrs_json, uri = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    used_by_rows = conn.execute(
        "SELECT p.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "WHERE e.kind='used_by' AND e.dst = ? AND p.kind='package' "
        "ORDER BY p.name",
        (dep_id,),
    ).fetchall()
    used_by = [r[0] for r in used_by_rows]
    versions = attrs.get("versions_in_use") or []
    if not isinstance(versions, list):
        versions = []
    return DependencyDescription(
        ecosystem=attrs.get("ecosystem", ecosystem),
        name=dep_name,
        uri=uri or "",
        versions_in_use=list(versions),
        used_by=used_by,
    )


def describe_builtin(
    conn: sqlite3.Connection, *, language: str, module_name: str
) -> BuiltinDescription | None:
    """Return the description of a Builtin node identified by (language, module_name).

    Populates `used_by` from inbound `used_by` edges originating from `package`
    nodes, sorted alphabetically by consumer package name. `conn` must be opened
    read-only.

    Phase 49 D-13 / BUILTIN-06: mirrors `describe_dependency` with `language` /
    `module_name` substituting for `ecosystem` / `name`.
    """
    row = conn.execute(
        "SELECT id, name, attrs_json, uri FROM nodes "
        "WHERE kind='builtin' AND name = ? AND path = ?",
        (module_name, language),
    ).fetchone()
    if not row:
        return None
    builtin_id, _name, attrs_json, uri = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    used_by_rows = conn.execute(
        "SELECT p.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "WHERE e.kind='used_by' AND e.dst = ? AND p.kind='package' "
        "ORDER BY p.name",
        (builtin_id,),
    ).fetchall()
    used_by = [r[0] for r in used_by_rows]
    return BuiltinDescription(
        language=attrs.get("language", language),
        module_name=attrs.get("module_name", module_name),
        uri=uri or "",
        used_by=used_by,
    )


def describe_plugin(
    conn: sqlite3.Connection, *, name: str
) -> PluginDescription | None:
    """Return the description of a plugin node, or None.

    `conn` must be opened read-only.
    """
    row = conn.execute(
        "SELECT name, attrs_json, uri FROM nodes "
        "WHERE kind='plugin' AND name = ?",
        (name,),
    ).fetchone()
    if not row:
        return None
    plugin_name, attrs_json, uri = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    return PluginDescription(
        name=plugin_name,
        uri=uri or "",
        ecosystem=attrs.get("ecosystem", ""),
    )


def _list_by_kind(conn: sqlite3.Connection, kind: str) -> list[NodeRecord]:
    rows = conn.execute(
        "SELECT kind, name, path, line, attrs_json, uri FROM nodes "
        "WHERE kind = ? ORDER BY name",
        (kind,),
    ).fetchall()
    return [_row_to_node(r) for r in rows]


def list_repositories(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Repository nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "repository")


def list_packages(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Package nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "package")


def list_entry_points(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all EntryPoint nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "entry_point")


def list_test_suites(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all TestSuite nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "test_suite")


def list_domains(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Domain nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "domain")


def list_dependencies(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Dependency nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "dependency")


def list_builtins(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Builtin nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "builtin")


def list_apps(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all App nodes alphabetically (Phase 50 D-09 / APP-05). `conn` must be read-only."""
    return _list_by_kind(conn, "app")


def list_plugins(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Plugin nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "plugin")


def list_scripts(conn: sqlite3.Connection) -> list[NodeRecord]:
    """Union of executable Files and executable EntryPoints.

    UNION (not UNION ALL) dedups identical rows. In practice the two
    SELECTs target different `kind` columns ('file' vs 'entry_point')
    so dedup is conservative. Matches Phase 33 SC#4 expectation.

    Note: Phase 30 emits the EntryPoint kind in attrs_json under the
    `entry_kind` key (not `kind`), so we filter on that. `conn` must be
    read-only.
    """
    rows = conn.execute(
        "SELECT kind, name, path, line, attrs_json FROM nodes "
        "WHERE kind='file' "
        "AND json_extract(attrs_json, '$.is_executable') = 1 "
        "UNION "
        "SELECT kind, name, path, line, attrs_json FROM nodes "
        "WHERE kind='entry_point' "
        "AND json_extract(attrs_json, '$.entry_kind') = 'executable' "
        "ORDER BY name"
    ).fetchall()
    return [_row_to_node(r) for r in rows]


@dataclass(frozen=True)
class ImporterRecord:
    path: str
    symbols: tuple[str, ...]
    depth: int


@dataclass(frozen=True)
class ExportRecord:
    name: str
    kind: str
    line: int | None


@dataclass(frozen=True)
class ExporterRecord:
    path: str
    name: str


def imported_by(
    conn: sqlite3.Connection,
    *,
    path: str,
    symbol: str | None = None,
    depth: int = 1,
) -> list[ImporterRecord]:
    symbol_filter = "AND dst.name = ?" if symbol is not None else ""
    base_params: list = [path]
    if symbol is not None:
        base_params.append(symbol)

    if depth <= 1:
        rows = conn.execute(
            f"""
            SELECT src.path, dst.name
            FROM edges e
            JOIN nodes src ON e.src = src.id
            JOIN nodes dst ON e.dst = dst.id
            WHERE e.kind='imports' AND dst.path = ? {symbol_filter}
              AND src.path IS NOT NULL
              AND {_RESOLVED_FILTER}
            """,
            base_params,
        ).fetchall()
        grouped: dict[str, list[str]] = {}
        for src_path, sym in rows:
            grouped.setdefault(src_path, []).append(sym)
        return [
            ImporterRecord(path=p, symbols=tuple(sorted(syms)), depth=1)
            for p, syms in sorted(grouped.items())
        ]

    rows = conn.execute(
        f"""
        WITH RECURSIVE walk(file_id, depth) AS (
            SELECT src.id, 1 FROM edges e
            JOIN nodes src ON e.src = src.id
            JOIN nodes dst ON e.dst = dst.id
            WHERE e.kind='imports' AND dst.path = ? {symbol_filter}
              AND src.path IS NOT NULL
              AND {_RESOLVED_FILTER}
            UNION
            SELECT e.src, walk.depth + 1 FROM edges e
            JOIN walk ON e.dst = walk.file_id
            WHERE e.kind='imports' AND walk.depth < ? AND {_RESOLVED_FILTER}
        )
        SELECT n.path, MIN(walk.depth)
        FROM walk JOIN nodes n ON walk.file_id = n.id
        WHERE n.path IS NOT NULL
        GROUP BY n.id
        ORDER BY MIN(walk.depth), n.path
        """,
        [*base_params, depth],
    ).fetchall()

    # Separate pass to collect symbol names for depth-1 importers: the CTE only tracks
    # (file_id, depth) and cannot carry symbol names through recursive hops.
    direct_rows = conn.execute(
        f"""
        SELECT src.path, dst.name
        FROM edges e
        JOIN nodes src ON e.src = src.id
        JOIN nodes dst ON e.dst = dst.id
        WHERE e.kind='imports' AND dst.path = ? {symbol_filter}
          AND src.path IS NOT NULL
          AND {_RESOLVED_FILTER}
        """,
        base_params,
    ).fetchall()
    direct_symbols: dict[str, list[str]] = {}
    for src_path, sym in direct_rows:
        direct_symbols.setdefault(src_path, []).append(sym)

    return [
        ImporterRecord(
            path=p,
            symbols=tuple(sorted(direct_symbols.get(p, []))),
            depth=d,
        )
        for p, d in rows
    ]


def exports(conn: sqlite3.Connection, *, path: str) -> list[ExportRecord]:
    rows = conn.execute(
        f"""
        SELECT dst.name, dst.kind, dst.line
        FROM edges e
        JOIN nodes src ON e.src = src.id
        JOIN nodes dst ON e.dst = dst.id
        WHERE e.kind='exports' AND src.path = ?
          AND {_RESOLVED_FILTER}
        ORDER BY dst.line, dst.name
        """,
        (path,),
    ).fetchall()
    return [ExportRecord(name=r[0], kind=r[1], line=r[2]) for r in rows]


def exported_by(conn: sqlite3.Connection, *, name: str) -> list[ExporterRecord]:
    rows = conn.execute(
        f"""
        SELECT DISTINCT src.path, dst.name
        FROM edges e
        JOIN nodes src ON e.src = src.id
        JOIN nodes dst ON e.dst = dst.id
        WHERE e.kind='exports' AND dst.name = ?
          AND src.path IS NOT NULL
          AND {_RESOLVED_FILTER}
        ORDER BY src.path
        """,
        (name,),
    ).fetchall()
    return [ExporterRecord(path=r[0], name=r[1]) for r in rows]


# ============================================================================
# Phase 32 Wave 2: bubble-up and cross-cutting helpers.
# ============================================================================


def tests_for_package(
    conn: sqlite3.Connection, *, package_name: str
) -> list[SuiteDescription]:
    """Return TestSuites that cover the package via `tests` edges.

    Returns [] when the package has no matching edges. Honors
    `_RESOLVED_FILTER` (D-17): suites whose `tests` edge has
    resolution='unresolved' are excluded.

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.
    """
    # _RESOLVED_FILTER uses alias `e`; substitute alias `t` for our query.
    tests_resolved_filter = _RESOLVED_FILTER.replace("e.", "t.")
    rows = conn.execute(
        f"SELECT ts.name, ts.uri, ts.attrs_json, "
        f"(SELECT COUNT(*) FROM edges pc "
        f" WHERE pc.src = ts.id AND pc.kind='physically_contains') AS fc "
        f"FROM edges t "
        f"JOIN nodes ts ON t.src = ts.id "
        f"JOIN nodes p ON t.dst = p.id "
        f"WHERE t.kind='tests' AND ts.kind='test_suite' "
        f"AND p.kind='package' AND p.name = ? "
        f"AND {tests_resolved_filter} "
        f"ORDER BY ts.name",
        (package_name,),
    ).fetchall()
    return [_load_suite_description(r) for r in rows]


def entry_points_for_package(
    conn: sqlite3.Connection, *, package_name: str
) -> list[EntryPointDescription]:
    """Return EntryPoints declared by the package, sorted by name.

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.
    """
    rows = conn.execute(
        "SELECT ep.name, ep.uri, ep.attrs_json, f.path "
        "FROM nodes pkg "
        "JOIN edges de ON de.src = pkg.id AND de.kind='declares_entry_point' "
        "JOIN nodes ep ON ep.id = de.dst AND ep.kind='entry_point' "
        "LEFT JOIN edges ib ON ib.src = ep.id AND ib.kind='implemented_by' "
        "LEFT JOIN nodes f ON f.id = ib.dst AND f.kind='file' "
        "WHERE pkg.kind='package' AND pkg.name = ? "
        "ORDER BY ep.name",
        (package_name,),
    ).fetchall()
    return [_load_entry_point_description(r) for r in rows]


def tests_for_domain(
    conn: sqlite3.Connection, *, domain_name: str
) -> list[SuiteDescription]:
    """Return TestSuites covering the domain or any descendant.

    D-09 UNION:
      (a) direct `TestSuite -> Domain` edge (Phase 31 D-12 single-domain).
      (b) indirect via `TestSuite -> Package -> belongs_to_domain`
          (Phase 31 D-13 multi-domain inferred at query time).

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.
    """
    sql = _DOMAIN_DESCENDANTS_CTE + """
        SELECT ts_name, ts_uri, ts_attrs, fc FROM (
            SELECT ts.id AS ts_id, ts.name AS ts_name, ts.uri AS ts_uri,
                   ts.attrs_json AS ts_attrs,
                   (SELECT COUNT(*) FROM edges pc
                    WHERE pc.src = ts.id AND pc.kind='physically_contains') AS fc
            FROM edges e
            JOIN descendants d ON e.dst = d.id
            JOIN nodes ts ON e.src = ts.id
            WHERE e.kind='tests' AND ts.kind='test_suite'
            UNION
            SELECT ts.id AS ts_id, ts.name AS ts_name, ts.uri AS ts_uri,
                   ts.attrs_json AS ts_attrs,
                   (SELECT COUNT(*) FROM edges pc
                    WHERE pc.src = ts.id AND pc.kind='physically_contains') AS fc
            FROM edges st
            JOIN nodes p ON st.dst = p.id AND p.kind='package'
            JOIN edges bt ON bt.src = p.id AND bt.kind='belongs_to_domain'
            JOIN descendants d ON bt.dst = d.id
            JOIN nodes ts ON st.src = ts.id
            WHERE st.kind='tests' AND ts.kind='test_suite'
        )
        ORDER BY ts_name
    """
    rows = conn.execute(sql, (domain_name,)).fetchall()
    return [_load_suite_description(r) for r in rows]


def domain_references(
    conn: sqlite3.Connection, *, domain_name: str
) -> list[tuple[str, int, int]]:
    """Bubble-up package references from the domain + its descendants.

    Returns rows of `(package_name, total_usage_count, distinct_domain_count)`
    ordered by total_usage_count DESC then package_name ASC. `conn` must be
    a `sqlite3.Connection` opened with `mode=ro`.
    """
    sql = _DOMAIN_DESCENDANTS_CTE + """
        SELECT n.name,
               COALESCE(SUM(CAST(
                 json_extract(e.attrs_json, '$.usage_count') AS INTEGER
               )), 0) AS total_usage,
               COUNT(DISTINCT e.src) AS distinct_domains
        FROM edges e
        JOIN descendants d ON e.src = d.id
        JOIN nodes n ON e.dst = n.id
        WHERE e.kind='references' AND n.kind='package'
        GROUP BY n.name
        ORDER BY total_usage DESC, n.name ASC
    """
    rows = conn.execute(sql, (domain_name,)).fetchall()
    return [(r[0], int(r[1] or 0), int(r[2] or 0)) for r in rows]


def domain_depends_on(
    conn: sqlite3.Connection, *, domain_name: str
) -> list[tuple[str, int]]:
    """Bubble-up domain dependencies from the domain + its descendants.

    Excludes self-loops (any descendant depending on any other descendant
    of the same root) via `NOT IN (SELECT id FROM descendants)`. Returns
    rows of `(target_domain_name, total_usage_count)` ordered by usage
    DESC then name ASC. `conn` must be opened with `mode=ro`.
    """
    sql = _DOMAIN_DESCENDANTS_CTE + """
        SELECT n.name,
               COALESCE(SUM(CAST(
                 json_extract(e.attrs_json, '$.usage_count') AS INTEGER
               )), 0) AS total_usage
        FROM edges e
        JOIN descendants d ON e.src = d.id
        JOIN nodes n ON e.dst = n.id
        WHERE e.kind='depends_on' AND n.kind='domain'
        AND n.id NOT IN (SELECT id FROM descendants)
        GROUP BY n.name
        ORDER BY total_usage DESC, n.name ASC
    """
    rows = conn.execute(sql, (domain_name,)).fetchall()
    return [(r[0], int(r[1] or 0)) for r in rows]


def cross_cutting_packages(
    conn: sqlite3.Connection,
) -> list[tuple[PackageDescription, int]]:
    """Packages with zero `belongs_to_domain` edges, ranked.

    Ranked by SUM of `usage_count` across incoming `references` edges
    (D-11). This is a deliberate divergence from ontology spec §11.4
    ('ranked by incoming references count from distinct domains'): the
    rendering choice prioritises 'how heavily depended on' over 'how
    broadly depended on'. This is a query-layer rendering choice, NOT a
    spec amendment — ONTOLOGY-SPEC.md stays as written.

    Returns list of (PackageDescription, score) sorted by score
    descending, ties broken alphabetically by package name (D-12).
    `conn` must be opened with `mode=ro`.
    """
    rows = conn.execute(
        "SELECT n.id, n.name, "
        "COALESCE(SUM(CAST("
        "  json_extract(e.attrs_json, '$.usage_count') AS INTEGER"
        ")), 0) AS score "
        "FROM nodes n "
        "LEFT JOIN edges e ON e.dst = n.id AND e.kind='references' "
        "WHERE n.kind='package' "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM edges bt "
        "  WHERE bt.src = n.id AND bt.kind='belongs_to_domain'"
        ") "
        "GROUP BY n.id, n.name "
        "ORDER BY score DESC, n.name ASC"
    ).fetchall()
    out: list[tuple[PackageDescription, int]] = []
    for _id, name, score in rows:
        desc = describe_package(conn, name=name)
        if desc is None:
            continue  # defensive — shouldn't happen
        out.append((desc, int(score or 0)))
    return out
