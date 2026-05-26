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
    }
)

_RESOLVED_FILTER = (
    "(e.attrs_json IS NULL OR json_extract(e.attrs_json, '$.resolution') != 'unresolved')"
)


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
class PathDescription:
    path: str
    children: list[NodeRecord]
    imports: list[NodeRecord]
    role_flags: dict[str, bool] | None = None


def _row_to_node(row) -> NodeRecord:
    kind, name, path, line, attrs_json = row
    attrs = json.loads(attrs_json) if attrs_json else {}
    return NodeRecord(kind=kind, name=name, path=path, line=line, attrs=attrs)


def find(
    conn: sqlite3.Connection,
    *,
    name: str | None = None,
    kind: str | None = None,
) -> list[NodeRecord]:
    """Find nodes by name and/or kind.

    `conn` must be a `sqlite3.Connection` opened with `mode=ro`.

    Raises:
        ValueError: when `kind` is provided but is not in `_VALID_KINDS`,
            or when both `name` and `kind` are None.
    """
    if kind is not None and kind not in _VALID_KINDS:
        raise ValueError(
            f"unknown kind {kind!r}; valid: {sorted(_VALID_KINDS)}"
        )
    if name is None and kind is None:
        raise ValueError("find requires at least one of name or kind")
    if name is not None and kind is None:
        rows = conn.execute(
            "SELECT kind, name, path, line, attrs_json FROM nodes WHERE name = ?",
            (name,),
        ).fetchall()
    elif name is not None and kind is not None:
        rows = conn.execute(
            "SELECT kind, name, path, line, attrs_json FROM nodes WHERE name = ? AND kind = ?",
            (name, kind),
        ).fetchall()
    else:  # name is None and kind is not None
        rows = conn.execute(
            "SELECT kind, name, path, line, attrs_json FROM nodes WHERE kind = ? ORDER BY name",
            (kind,),
        ).fetchall()
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
    return PackageDescription(
        name=name,
        language=attrs.get("language", ""),
        version=attrs.get("version", ""),
        files=file_paths,
        counts=counts,
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
    return PathDescription(
        path=path,
        children=[_row_to_node(r) for r in children_rows],
        imports=[_row_to_node(r) for r in import_rows],
    )


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
