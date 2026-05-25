"""cg sync-wiki — link package nodes to wiki overview pages via `documents` edges.

Resolves each `kind='package'` node to its wiki overview page by trying three
filesystem conventions in order. Upserts `kind='wiki_page'` nodes and
`kind='documents'` edges. Cleans up `wiki_page` nodes whose files no longer
exist on disk. Returns a structured report of what changed.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import store, upsert


@dataclass(frozen=True)
class DriftReport:
    """Report of wiki synchronization changes and drift.

    newly_linked: (pkg_name, wiki_path) pairs for packages that gained a
        `documents` edge this run (didn't have one before).
    undocumented: package names with no `documents` edge after the run.
        Includes packages with `ambiguous` wiki matches (multiple matches
        across domain folders).
    stale: workspace-relative wiki paths whose `wiki_page` nodes were
        removed this run (file no longer exists on disk).
    ambiguous: package names with multiple matching wiki paths across
        different domain folders (glob collision). These are included in
        `undocumented` but not linked.
    """

    newly_linked: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    undocumented: tuple[str, ...] = field(default_factory=tuple)
    stale: tuple[str, ...] = field(default_factory=tuple)
    ambiguous: tuple[str, ...] = field(default_factory=tuple)


def _resolve_wiki_path(name: str, workspace: Path) -> tuple[str | None, bool]:
    """Return (workspace-relative path, ambiguous?). Path is None when not found."""
    direct_candidates = [
        Path("wiki") / "packages" / name / f"{name}.md",
        Path("wiki") / "apps" / name / f"{name}.md",
    ]
    for rel in direct_candidates:
        if (workspace / rel).is_file():
            return rel.as_posix(), False

    domain_matches = (
        sorted((workspace / "wiki" / "domains").glob(f"*/packages/{name}/{name}.md"))
        if (workspace / "wiki" / "domains").is_dir()
        else []
    )
    if len(domain_matches) == 1:
        return domain_matches[0].relative_to(workspace).as_posix(), False
    if len(domain_matches) > 1:
        return None, True
    return None, False


def _existing_documents_sources(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT p.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "WHERE e.kind = 'documents' AND p.kind = 'package'"
    ).fetchall()
    return {row[0] for row in rows}


def _existing_wiki_pages(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    rows = conn.execute("SELECT id, name FROM nodes WHERE kind = 'wiki_page'").fetchall()
    return [(row[0], row[1]) for row in rows]


def _packages(conn: sqlite3.Connection) -> list[tuple[str, str | None]]:
    rows = conn.execute("SELECT name, path FROM nodes WHERE kind = 'package' ORDER BY name").fetchall()
    return [(row[0], row[1]) for row in rows]


def _link_package(conn: sqlite3.Connection, pkg_name: str, pkg_path: str | None, wiki_rel: str) -> None:
    upsert.upsert_records(
        conn,
        GraphRecords(
            nodes=[
                GraphNode(
                    kind="wiki_page",
                    name=wiki_rel,
                    path=wiki_rel,
                    line=None,
                    attrs={},
                )
            ],
            edges=[
                GraphEdge(
                    src=("package", pkg_name, pkg_path),
                    dst=("wiki_page", wiki_rel, wiki_rel),
                    kind="documents",
                    attrs={},
                )
            ],
        ),
    )


def _cleanup_stale(conn: sqlite3.Connection, workspace: Path) -> list[str]:
    removed: list[str] = []
    for node_id, wiki_rel in _existing_wiki_pages(conn):
        if not (workspace / wiki_rel).is_file():
            conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            removed.append(wiki_rel)
    return sorted(removed)


def run(*, workspace: Path, conn: sqlite3.Connection) -> DriftReport:
    """Sync package → wiki_page links and return a drift report.

    All writes happen in a single transaction.
    """
    workspace = Path(workspace)
    before = _existing_documents_sources(conn)
    newly_linked: list[tuple[str, str]] = []
    undocumented: list[str] = []
    ambiguous: list[str] = []

    with store.transaction(conn):
        for pkg_name, pkg_path in _packages(conn):
            wiki_rel, is_ambiguous = _resolve_wiki_path(pkg_name, workspace)
            if is_ambiguous:
                print(
                    f"warning: multiple wiki overview matches for package {pkg_name!r}; skipping",
                    file=sys.stderr,
                )
                ambiguous.append(pkg_name)
                undocumented.append(pkg_name)
                continue
            if wiki_rel is None:
                undocumented.append(pkg_name)
                continue
            _link_package(conn, pkg_name, pkg_path, wiki_rel)
            if pkg_name not in before:
                newly_linked.append((pkg_name, wiki_rel))

        stale = _cleanup_stale(conn, workspace)

    return DriftReport(
        newly_linked=tuple(sorted(newly_linked)),
        undocumented=tuple(sorted(undocumented)),
        stale=tuple(stale),
        ambiguous=tuple(sorted(ambiguous)),
    )
